"""Backward-compatible shim - implementation moved to src.agent.runner."""

from src.agent.runner import (
    AgentQueryResult,
    run_agent_query,
    extract_current_product,
    extract_product_memory_from_tool_call,
    extract_balanced_json,
    extract_pseudo_search_products_args,
    _is_price_query,
    _has_specific_price,
    _response_mentions_any_product,
    _build_grounded_price_response,
)

__all__ = [
    "AgentQueryResult",
    "run_agent_query",
    "extract_current_product",
    "extract_product_memory_from_tool_call",
    "extract_balanced_json",
    "extract_pseudo_search_products_args",
    "_is_price_query",
    "_has_specific_price",
    "_response_mentions_any_product",
    "_build_grounded_price_response",
]