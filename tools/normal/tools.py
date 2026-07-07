"""Backward-compatible facade for normal search tools.

This module keeps existing imports stable while delegating implementation
across smaller modules for cleaner architecture.
"""

from .error_utils import _error_json, _product_error_message
from .intent_filters import (
    _build_metadata_filter_clauses,
    _build_search_intent,
    _deduplicate_products,
    _expand_query_with_product_type_aliases,
    _extract_amount_from_text,
    _extract_known_brand,
    _extract_product_type,
    _filter_products_by_intent,
    _filter_products_with_specific_price,
    _is_price_comparison_query,
    _normalize_query_text,
    _parse_price_intent,
    _parse_price_text_to_vnd,
    _price_token_to_vnd,
    _product_matches_text_intent,
)
from .logging_utils import _log
from .models import ProductMemory, SearchIntent
from .retrieval import _get_query_embedding, _rrf_merge
from .search_tool import SearchProductsArgs, search_products

__all__ = [
    "ProductMemory",
    "SearchIntent",
    "SearchProductsArgs",
    "search_products",
    "_log",
    "_get_query_embedding",
    "_rrf_merge",
    "_deduplicate_products",
    "_is_price_comparison_query",
    "_filter_products_with_specific_price",
    "_expand_query_with_product_type_aliases",
    "_normalize_query_text",
    "_extract_known_brand",
    "_extract_product_type",
    "_price_token_to_vnd",
    "_extract_amount_from_text",
    "_parse_price_intent",
    "_build_search_intent",
    "_build_metadata_filter_clauses",
    "_parse_price_text_to_vnd",
    "_product_matches_text_intent",
    "_filter_products_by_intent",
    "_product_error_message",
    "_error_json",
]
