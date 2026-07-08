from os import getenv
import re
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


def _contains_card_monitor_phrase(text: str) -> bool:
    value = (text or "").lower()
    return bool(
        re.search(r"\bcard\s+màn\s+hình\b", value)
        or re.search(r"\bcard\s+man\s+hinh\b", value)
    )


def _preserve_domain_terms(raw_query: str, normalized_query: str) -> str:
    normalized = (normalized_query or "").strip()
    if not normalized:
        return normalized

    if _contains_card_monitor_phrase(raw_query):
        # Keep the user's domain term; avoid LLM translating it to 'thẻ màn hình'.
        normalized = re.sub(r"\bthẻ\s+màn\s+hình\b", "card màn hình", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bthe\s+man\s+hinh\b", "card màn hình", normalized, flags=re.IGNORECASE)

        if re.search(r"\bcard\s+màn\s+hình\b", raw_query, flags=re.IGNORECASE):
            normalized = re.sub(r"\bcard\s+màn\s+hình\b", "Card màn hình", normalized, flags=re.IGNORECASE)

    return normalized


async def normalize_query_with_llm(raw_query: str, fallback_query: str) -> str:
    """Optional LLM-based query normalization with safe fallback.

    Enabled only when ENABLE_LLM_QUERY_NORMALIZATION is truthy.
    """
    if not raw_query.strip():
        return fallback_query

    if not _is_truthy(getenv("ENABLE_LLM_QUERY_NORMALIZATION", "true")):
        return fallback_query

    cache_key = raw_query.strip().lower()
    if cache_key in _QUERY_NORMALIZATION_CACHE:
        return _QUERY_NORMALIZATION_CACHE[cache_key]

    base_url = getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    api_key = getenv("OPENAI_API_KEY", "ollama")
    model = getenv("LOCAL_MODEL", "llama3.1:8b")
    timeout_sec = float(getenv("QUERY_NORMALIZER_TIMEOUT_SEC", "4.0"))

    system_prompt = (
        "Bạn là bộ chuẩn hóa truy vấn tìm kiếm sản phẩm. "
        "Nhiệm vụ: sửa lỗi chính tả, chuẩn hóa dấu tiếng Việt, loại bỏ nhiễu, "
        "chuẩn hóa cách diễn đạt giá tiền nhưng giữ nguyên ý định người dùng. "
        "Chỉ trả về DUY NHẤT 1 câu truy vấn đã chuẩn hóa, không giải thích."
    )

    user_prompt = (
        "Query gốc: "
        f"{raw_query}\n"
        "Hãy trả về query đã chuẩn hóa để phục vụ tìm kiếm sản phẩm."
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
            normalized = _preserve_domain_terms(raw_query, normalized)
            if normalized:
                _QUERY_NORMALIZATION_CACHE[cache_key] = normalized
                _log("NORMALIZE", f"llm_normalized='{normalized}'")
                return normalized
    except Exception as exc:
        _log("NORMALIZE", f"LLM normalize skipped/fallback: {exc}")

    _QUERY_NORMALIZATION_CACHE[cache_key] = fallback_query
    return fallback_query
