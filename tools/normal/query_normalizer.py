from os import getenv
from typing import Dict

import httpx

from .logging_utils import _log


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

    if not _is_truthy(getenv("ENABLE_LLM_QUERY_NORMALIZATION", "false")):
        return fallback_query

    cache_key = raw_query.strip().lower()
    if cache_key in _QUERY_NORMALIZATION_CACHE:
        return _QUERY_NORMALIZATION_CACHE[cache_key]

    base_url = getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    api_key = getenv("OPENAI_API_KEY", "ollama")
    model = getenv("LOCAL_MODEL", "llama3.1:8b")
    timeout_sec = float(getenv("QUERY_NORMALIZER_TIMEOUT_SEC", "4.0"))

    system_prompt = (
        "Ban la bo chuan hoa truy van tim kiem san pham. "
        "Nhiem vu: sua loi chinh ta, bo dau/no-dau, chuan hoa don vi gia tien, "
        "giu nguyen y nghia truy van. "
        "Chi tra ve DUY NHAT 1 dong query da chuan hoa, khong giai thich."
    )

    user_prompt = (
        "Query goc: "
        f"{raw_query}\n"
        "Hay tra ve query da chuan hoa de phuc vu tim kiem san pham."
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            normalized = _clean_llm_query_text(content)
            if normalized:
                _QUERY_NORMALIZATION_CACHE[cache_key] = normalized
                _log("NORMALIZE", f"llm_normalized='{normalized}'")
                return normalized
    except Exception as exc:
        _log("NORMALIZE", f"LLM normalize skipped/fallback: {exc}")

    _QUERY_NORMALIZATION_CACHE[cache_key] = fallback_query
    return fallback_query
