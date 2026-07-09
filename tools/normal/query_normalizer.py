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

    if not _is_truthy(getenv("ENABLE_LLM_QUERY_NORMALIZATION", "true")):
        return fallback_query

    cache_key = raw_query.strip().lower()
    if cache_key in _QUERY_NORMALIZATION_CACHE:
        return _QUERY_NORMALIZATION_CACHE[cache_key]

    base_url = getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    api_key = getenv("OPENAI_API_KEY", "ollama")
    model = getenv("LOCAL_MODEL", "llama3.1:8b")
    timeout_sec = float(getenv("QUERY_NORMALIZER_TIMEOUT_SEC", "4.0"))

    system_prompt = """
        Bạn là bộ chuẩn hóa truy vấn tìm kiếm sản phẩm.

        Mục tiêu:
        - Chỉ chuẩn hóa truy vấn, KHÔNG thay đổi ý định tìm kiếm.

        Quy tắc:
        1. Sửa lỗi chính tả.
        2. Chuẩn hóa dấu tiếng Việt.
        3. Loại bỏ ký tự thừa, khoảng trắng thừa.
        4. Chuẩn hóa cách viết giá tiền.
        Ví dụ:
        - 1tr -> 1 triệu
        - 2 củ -> 2 triệu
        - 10k -> 10 nghìn
        5. Giữ nguyên tất cả tên sản phẩm, thương hiệu, model, mã sản phẩm.
        6. Không dịch hoặc thay thế thuật ngữ.
        Ví dụ:
        - card màn hình -> card màn hình
        - main -> main
        - VGA -> VGA
        - CPU -> CPU
        7. Không thêm thông tin mà người dùng không đề cập.
        8. Nếu câu đã đúng thì trả lại nguyên văn.
        9. Với các câu follow-up ngắn (ví dụ: "còn sản phẩm nào khác ko", "loại nào tốt hơn", "giá sao"), chỉ sửa lỗi chính tả nếu có, tuyệt đối không diễn đạt lại.

        Đầu ra:
        - Chỉ trả về đúng 1 câu truy vấn đã chuẩn hóa.
        - Không giải thích.
        - Không thêm dấu ngoặc, markdown hoặc ký tự khác.
    """

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
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
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
