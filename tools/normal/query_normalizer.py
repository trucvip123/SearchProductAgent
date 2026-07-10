from typing import Dict

import httpx

from .logging_utils import _log
from src.prompts import QUERY_NORMALIZER_SYSTEM_PROMPT, build_query_normalizer_user_prompt
from src.models import (
    get_llm_base_url,
    get_llm_api_key,
    get_local_model,
    get_query_normalizer_timeout,
    is_llm_query_normalization_enabled,
)


_QUERY_NORMALIZATION_CACHE: Dict[str, str] = {}


def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_llm_query_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.strip("`\"' ")
    # Keep one line to avoid prompt leakage/noise.
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ""
    return cleaned


async def normalize_query_with_llm(raw_query: str, fallback_query: str) -> str:
    """Optional LLM-based query normalization with safe fallback.

    Enabled only when ENABLE_LLM_QUERY_NORMALIZATION is truthy.
    """
    if not raw_query.strip():
        return fallback_query

    if not is_llm_query_normalization_enabled():
        return fallback_query

    cache_key = raw_query.strip().lower()
    if cache_key in _QUERY_NORMALIZATION_CACHE:
        return _QUERY_NORMALIZATION_CACHE[cache_key]

    base_url = get_llm_base_url()
    api_key = get_llm_api_key()
    model = get_local_model()
    timeout_sec = get_query_normalizer_timeout()

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": QUERY_NORMALIZER_SYSTEM_PROMPT},
                        {"role": "user", "content": build_query_normalizer_user_prompt(raw_query)},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            _log("NORMALIZE", f"llm_raw='{content}'")
            normalized = _clean_llm_query_text(content)
            if normalized:
                _QUERY_NORMALIZATION_CACHE[cache_key] = normalized
                _log("NORMALIZE", f"llm_normalized='{normalized}'")
                return normalized
    except Exception as exc:
        _log("NORMALIZE", f"LLM normalize skipped/fallback: {exc}")

    _QUERY_NORMALIZATION_CACHE[cache_key] = fallback_query
    return fallback_query
