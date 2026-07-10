"""Database host/connection utilities — shared by search tools and any future DB tools."""

from typing import List


def _normalize_db_host(raw_host: str) -> str:
    """Normalize host value loaded from env (trim spaces/quotes and strip scheme/path)."""
    host = (raw_host or "").strip().strip("\"'")
    if not host:
        return ""
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    return host.strip()


def _candidate_db_hosts(host: str) -> List[str]:
    """Build candidate hosts, including Neon canonical fallback from '*-pooler.<host>' form."""
    candidates: List[str] = []
    base = _normalize_db_host(host)
    if base:
        candidates.append(base)
    if "-pooler." in base:
        neon_canonical = base.split("-pooler.", 1)[1].strip()
        if neon_canonical and neon_canonical not in candidates:
            candidates.append(neon_canonical)
    return candidates


def _derive_neon_endpoint_id(host: str) -> str:
    """Derive Neon endpoint id from hostname first label as-is.

    Neon expects the project option to match the SNI-inferred project name exactly,
    including the '-pooler' suffix when using pooler hostnames.
    """
    base = _normalize_db_host(host)
    if not base:
        return ""
    first_label = base.split(".", 1)[0].strip()
    return first_label
