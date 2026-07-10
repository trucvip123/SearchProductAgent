"""Backward-compatible shim — implementation moved under src.tools and src.utils."""

from src.tools.schemas import SearchProductsArgs
from src.tools.search_tool import search_products
from src.utils import (
    _is_vector_trace_enabled,
    _vector_preview,
    _normalize_db_host,
    _candidate_db_hosts,
    _derive_neon_endpoint_id,
    _SPEC_QUERY_PATTERNS,
    _extract_query_spec_terms,
)

__all__ = [
    "SearchProductsArgs",
    "search_products",
    "_is_vector_trace_enabled",
    "_vector_preview",
    "_normalize_db_host",
    "_candidate_db_hosts",
    "_derive_neon_endpoint_id",
    "_SPEC_QUERY_PATTERNS",
    "_extract_query_spec_terms",
]

