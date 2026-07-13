"""Model provider configuration — env-based settings for LLM and embedding.

All model/provider settings are read from environment variables here so that
the rest of the codebase imports from a single source of truth.
"""

from os import getenv


def get_llm_base_url() -> str:
    """OpenAI-compatible API base URL (default: Ollama local)."""
    return getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")


def get_llm_api_key() -> str:
    """API key for OpenAI-compatible endpoint."""
    return getenv("OPENAI_API_KEY", "ollama")


def get_local_model() -> str:
    """Chat/completion model name."""
    return getenv("LOCAL_MODEL", "llama3.1:8b")


def get_embedding_model() -> str:
    """Embedding model name."""
    return getenv("EMBEDDING_MODEL", "nomic-embed-text")


def get_query_normalizer_timeout() -> float:
    """Timeout (seconds) for the LLM query-normalizer call."""
    return float(getenv("QUERY_NORMALIZER_TIMEOUT_SEC", "4.0"))

# Module-level convenience constants (resolved once at import time).
# Use the get_* functions when you need a value that reflects runtime env changes.
LOCAL_MODEL: str = get_local_model()
EMBEDDING_MODEL: str = get_embedding_model()
LLM_BASE_URL: str = get_llm_base_url()
LLM_API_KEY: str = get_llm_api_key()
