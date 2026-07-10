"""Agent module - LLM orchestration, state management, memory, and execution."""

from .graph import (
    LOCAL_MODEL,
    OrchestratorState,
    orchestrator_agent,
    product_agent,
    _build_llm,
    _is_product_query,
)
from .memory import ProductMemoryManager
from .runner import (
    AgentQueryResult,
    run_agent_query,
    extract_current_product,
    extract_product_memory_from_tool_call,
    extract_balanced_json,
    extract_pseudo_search_products_args,
)
from src.prompts import ORCHESTRATOR_PROMPT, GENERAL_ASSISTANT_PROMPT

__all__ = [
    # graph
    "LOCAL_MODEL",
    "OrchestratorState",
    "orchestrator_agent",
    "product_agent",
    "_build_llm",
    "_is_product_query",
    # memory
    "ProductMemoryManager",
    # runner
    "AgentQueryResult",
    "run_agent_query",
    "extract_current_product",
    "extract_product_memory_from_tool_call",
    "extract_balanced_json",
    "extract_pseudo_search_products_args",
    # prompts (re-exported for convenience)
    "ORCHESTRATOR_PROMPT",
    "GENERAL_ASSISTANT_PROMPT",
]

