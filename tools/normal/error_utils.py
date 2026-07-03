import json

import httpx

from .logging_utils import _log


def _product_error_message(error: Exception) -> str:
    """Map low-level exception to a user-friendly error message."""
    _log("ERROR_HANDLER", f"Caught error: {type(error).__name__}: {error}")
    if isinstance(error, httpx.HTTPStatusError):
        return f"Lỗi HTTP {error.response.status_code} khi cố gắng truy vấn database. Vui lòng thử lại sau."
    if isinstance(error, httpx.TimeoutException):
        return "Yêu cầu truy vấn bị quá thời gian chờ. Vui lòng thử lại."
    if isinstance(error, httpx.RequestError):
        return "Lỗi mạng khi cố gắng truy vấn database. Vui lòng kiểm tra kết nối và thử lại."
    return f"Đã xảy ra lỗi không mong muốn: {type(error).__name__}. Vui lòng thử lại."


def _error_json(message: str) -> str:
    """Return JSON error payload that the agent can surface to users."""
    return json.dumps({"status": "error", "message": message, "products": []}, ensure_ascii=False)
