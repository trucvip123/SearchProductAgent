"""Vector search utilities — trace flag and preview helper."""

from os import getenv
from typing import List


def _is_vector_trace_enabled() -> bool:
    """Return True when VECTOR_TRACE_LOGS env var is truthy (default on)."""
    return getenv("VECTOR_TRACE_LOGS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _vector_preview(vec: List[float], max_items: int = 8) -> str:
    """Return a compact string preview of a float vector."""
    if not vec:
        return "[]"
    preview = ", ".join(f"{x:.4f}" for x in vec[:max_items])
    suffix = ", ..." if len(vec) > max_items else ""
    return f"[{preview}{suffix}]"
