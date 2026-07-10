"""LLM factory — builds ChatOpenAI instances pointing at the configured provider.

Import LOCAL_MODEL and _build_llm from here instead of defining them in agent code.
"""

from langchain_openai import ChatOpenAI

from .config import get_llm_base_url, get_llm_api_key, get_local_model


# Resolved at import time; reflects the env var value when the module is first loaded.
LOCAL_MODEL: str = get_local_model()


def _build_llm(*, streaming: bool = True, temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI instance pointing at the configured OpenAI-compatible endpoint.

    Values are read from env at call time so that tests can patch env vars freely.
    """
    return ChatOpenAI(
        model=get_local_model(),
        base_url=get_llm_base_url(),
        api_key=get_llm_api_key(),
        temperature=temperature,
        streaming=streaming,
    )
