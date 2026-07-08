"""Utilities module - logging, error handling, database helpers."""

# Re-export from old location for now (compatibility)
from tools.normal.logging_utils import _log
from tools.normal.error_utils import _error_json, _product_error_message
from tools.normal.db_pool import get_db_pool, close_db_pool
from tools.normal.query_normalizer import normalize_query_with_llm
from tools.normal.retrieval import _get_query_embedding, _rrf_merge
from tools.normal.intent_filters import (
    _normalize_user_query,
    _normalize_query_text,
    _extract_known_brand,
    _extract_product_type,
    _expand_query_with_product_type_aliases,
    _parse_price_intent,
    _build_search_intent,
    _build_metadata_filter_clauses,
    _filter_products_by_intent,
    _filter_products_with_specific_price,
    _is_price_comparison_query,
    _deduplicate_products,
)

__all__ = [
    "_log",
    "_error_json",
    "_product_error_message",
    "get_db_pool",
    "close_db_pool",
    "normalize_query_with_llm",
    "_get_query_embedding",
    "_rrf_merge",
    "_normalize_user_query",
    "_normalize_query_text",
    "_extract_known_brand",
    "_extract_product_type",
    "_expand_query_with_product_type_aliases",
    "_parse_price_intent",
    "_build_search_intent",
    "_build_metadata_filter_clauses",
    "_filter_products_by_intent",
    "_filter_products_with_specific_price",
    "_is_price_comparison_query",
    "_deduplicate_products",
]
