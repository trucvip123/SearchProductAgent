"""Agent module - LLM orchestration and routing."""

# Re-export from old location for now (compatibility)
from agent import (
    orchestrator_agent,
    LOCAL_MODEL,
    OrchestratorState,
    ORCHESTRATOR_PROMPT,
    GENERAL_ASSISTANT_PROMPT,
)

__all__ = [
    "orchestrator_agent",
    "LOCAL_MODEL",
    "OrchestratorState",
    "ORCHESTRATOR_PROMPT",
    "GENERAL_ASSISTANT_PROMPT",
]
