"""Database runtime helpers for search tools.

This module isolates env-driven DB config loading, DNS/host resolution,
pool option derivation, and schema column inspection used by product search.
"""

import re
import socket
from os import getenv
from typing import Optional

import asyncpg

from tools.normal.logging_utils import _log

from .db_utils import _normalize_db_host, _candidate_db_hosts, _derive_neon_endpoint_id


def _load_db_config() -> dict:
    db_host = _normalize_db_host(getenv("POSTGRES_HOST", "localhost"))
    db_port = int(getenv("POSTGRES_PORT", "5432"))
    db_name = getenv("POSTGRES_DB", "server_products")
    db_user = getenv("POSTGRES_USER", "postgres")
    db_password = getenv("POSTGRES_PASSWORD", "")
    db_ssl_mode = getenv("POSTGRES_SSLMODE", "require").strip().lower()
    db_endpoint_id = getenv("POSTGRES_ENDPOINT_ID", "").strip()
    db_table = getenv("POSTGRES_TABLE", "products")

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", db_table):
        raise ValueError(f"Tên bảng không hợp lệ: '{db_table}'")

    safe_pw = "***" if db_password else "(empty)"
    _log(
        "CONFIG",
        (
            f"Connecting PostgreSQL host={db_host} port={db_port} db={db_name} "
            f"user={db_user} table={db_table} password={safe_pw} sslmode={db_ssl_mode}"
        ),
    )

    return {
        "host": db_host,
        "port": db_port,
        "database": db_name,
        "user": db_user,
        "password": db_password,
        "ssl_mode": db_ssl_mode,
        "endpoint_id": db_endpoint_id,
        "table": db_table,
    }


def _resolve_db_connection_settings(db_config: dict) -> dict:
    db_host = db_config["host"]
    db_port = db_config["port"]

    candidate_hosts = _candidate_db_hosts(db_host)
    if not candidate_hosts:
        raise ValueError("POSTGRES_HOST đang rỗng hoặc không hợp lệ.")

    selected_host: Optional[str] = None
    for candidate in candidate_hosts:
        try:
            addr_infos = socket.getaddrinfo(candidate, db_port, type=socket.SOCK_STREAM)
            resolved_addresses = sorted({info[4][0] for info in addr_infos if info and len(info) >= 5 and info[4]})
            sample = ", ".join(resolved_addresses[:3]) if resolved_addresses else "(no addresses)"
            _log("DNS", f"Resolved host '{candidate}' -> {sample}")
            selected_host = candidate
            break
        except socket.gaierror as error:
            _log("DNS", f"Resolve failed for host '{candidate}': {error}")

    if not selected_host:
        raise socket.gaierror(f"Không phân giải được tên máy chủ DB '{db_host}'.")

    if selected_host != db_host:
        _log("DNS", f"Using fallback host '{selected_host}' instead of '{db_host}'")
        db_host = selected_host

    derived_neon_endpoint_id = _derive_neon_endpoint_id(db_host) if "neon.tech" in db_host else ""
    effective_endpoint_id = db_config["endpoint_id"] or derived_neon_endpoint_id
    connection_options = f"endpoint={effective_endpoint_id}" if effective_endpoint_id else ""
    if connection_options:
        _log("CONFIG", f"Using PostgreSQL connection options '{connection_options}'")

    resolved_config = dict(db_config)
    resolved_config["host"] = db_host
    resolved_config["connection_options"] = connection_options
    resolved_config["pool_min_size"] = int(getenv("POSTGRES_POOL_MIN_SIZE", "1"))
    resolved_config["pool_max_size"] = int(getenv("POSTGRES_POOL_MAX_SIZE", "10"))
    return resolved_config


async def _fetch_table_columns(conn: asyncpg.Connection, db_table: str) -> set[str]:
    col_rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        db_table,
    )
    columns = {row["column_name"] for row in col_rows}
    if not columns:
        raise ValueError(f"Bảng '{db_table}' không tồn tại hoặc không có cột nào.")
    _log("SCHEMA", f"Detected columns in '{db_table}': {sorted(columns)}")
    return columns