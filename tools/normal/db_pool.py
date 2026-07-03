import asyncio
from typing import Optional, Tuple

import asyncpg

from .logging_utils import _log


_pool: Optional[asyncpg.Pool] = None
_pool_key: Optional[Tuple[str, int, str, str, str]] = None
_pool_lock = asyncio.Lock()


def _build_pool_key(host: str, port: int, database: str, user: str, password: str) -> Tuple[str, int, str, str, str]:
    return (host, port, database, user, password)


async def get_db_pool(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    min_size: int = 1,
    max_size: int = 10,
    command_timeout: int = 30,
) -> asyncpg.Pool:
    """Return a reusable asyncpg pool; recreate only when DB config changes."""
    global _pool, _pool_key

    key = _build_pool_key(host, port, database, user, password)

    async with _pool_lock:
        if _pool is not None and _pool_key == key:
            return _pool

        if _pool is not None:
            _log("POOL", "DB config changed, closing old pool")
            await _pool.close()
            _pool = None
            _pool_key = None

        _pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=min_size,
            max_size=max_size,
            command_timeout=command_timeout,
        )
        _pool_key = key
        _log("POOL", f"Created asyncpg pool min={min_size} max={max_size}")
        return _pool


async def close_db_pool() -> None:
    """Close the global pool (useful for graceful shutdown/tests)."""
    global _pool, _pool_key

    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _log("POOL", "Closed asyncpg pool")
            _pool = None
            _pool_key = None
