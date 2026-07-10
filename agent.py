"""Backward-compatible shim - implementation moved to src.agent.graph."""

from src.agent.graph import (
    LOCAL_MODEL,
    OrchestratorState,
    orchestrator_agent,
    product_agent,
    _build_llm,
    _is_product_query,
    _latest_user_content,
    _route_node,
    _route_next,
    _general_node,
)

__all__ = [
    "LOCAL_MODEL",
    "OrchestratorState",
    "orchestrator_agent",
    "product_agent",
    "_build_llm",
    "_is_product_query",
    "_latest_user_content",
    "_route_node",
    "_route_next",
    "_general_node",
]