"""Agent runner — helpers, result type, and CLI-oriented run_agent_query.

This is the canonical implementation. agent_handler.py (root) is a backward-compatible shim.

For the Streamlit streaming runner (with on_stream_chunk callback) see src/ui/agent_runner.py.
"""

import json
import re
from typing import Callable, Optional

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    ToolMessage,
)

from ..models import ProductMemory
from .graph import orchestrator_agent
from .memory import ProductMemoryManager


_PRICE_SKIP_KEYWORDS = [
    "liên hệ",
    "báo giá",
    "n/a",
    "unknown",
]


def _is_price_query(text: str) -> bool:
    q = (text or "").lower()
    patterns = [
        r"\bgiá\b",
        r"\bgia\b",
        r"bao\s+nhiêu",
        r"bao\s+nhieu",
        r"bao\s+tiền",
        r"bao\s+tien",
    ]
    return any(re.search(p, q) for p in patterns)


def _is_link_query(text: str) -> bool:
    q = (text or "").lower()
    patterns = [
        r"\blink\b",
        r"đường\s*link",
        r"duong\s*link",
        r"trang\s*sản\s*phẩm",
        r"trang\s*san\s*pham",
        r"url",
    ]
    return any(re.search(p, q) for p in patterns)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _select_best_product(products: list, query: str) -> dict:
    if not products:
        return {}

    query_norm = _normalize_for_match(query)
    query_tokens = [tok for tok in query_norm.split() if len(tok) >= 3]

    best = products[0]
    best_score = -1
    for product in products:
        name = str(product.get("tên") or "")
        name_norm = _normalize_for_match(name)
        score = 0

        if name_norm and name_norm in query_norm:
            score += 100

        for token in query_tokens:
            if token in name_norm:
                score += 2
            if any(ch.isdigit() for ch in token) and token in name_norm:
                score += 4

        if score > best_score:
            best = product
            best_score = score

    return best


def _build_grounded_link_response(products: list, query: str) -> str:
    if not products:
        return ""

    candidate = _select_best_product(products, query)
    name = str(candidate.get("tên") or "Sản phẩm").strip()
    link = str(candidate.get("link_sản_phẩm") or "").strip().rstrip(".")

    if link and link.lower().startswith(("http://", "https://")):
        return f"Link sản phẩm của {name} là: {link}"
    return "Không có thông tin này trong dữ liệu hiện tại."


def _has_specific_price(price_text: str) -> bool:
    price = (price_text or "").strip().lower()
    if not price:
        return False
    if any(skip in price for skip in _PRICE_SKIP_KEYWORDS):
        return False
    return bool(re.search(r"\d", price))


def _response_mentions_any_product(response: str, products: list) -> bool:
    response_lower = (response or "").lower()
    if not response_lower:
        return False
    for product in products or []:
        name = str(product.get("tên") or "").strip().lower()
        if name and name in response_lower:
            return True
    return False


def _build_grounded_price_response(products: list) -> str:
    if not products:
        return ""
    priced_products = [p for p in products if _has_specific_price(str(p.get("giá") or ""))]
    candidate = priced_products[0] if priced_products else products[0]
    name = str(candidate.get("tên") or "Sản phẩm").strip()
    price = str(candidate.get("giá") or "Chưa có thông tin giá").strip()
    return f"{name} có giá {price}."


def extract_current_product(tool_content: str) -> Optional[str]:
    """Extract first product name from tool result JSON."""
    try:
        data = json.loads(tool_content)
        products = data.get("products") or []
        if products:
            return products[0].get("tên") or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def extract_product_memory_from_tool_call(tool_call_dict: dict) -> Optional[ProductMemory]:
    """Extract ProductMemory from a search_products tool call dict."""
    if not isinstance(tool_call_dict, dict):
        return None
    if tool_call_dict.get("name") != "search_products":
        return None
    args = tool_call_dict.get("args", {})
    if not isinstance(args, dict):
        return None
    try:
        return ProductMemory(
            product_type=args.get("product_type"),
            brand=args.get("brand"),
            series=args.get("series"),
            model=args.get("model"),
            cpu=args.get("cpu"),
            ram=args.get("ram"),
            storage=args.get("storage"),
            capacity=args.get("capacity"),
            interface=args.get("interface"),
            price_range=args.get("price_range"),
            product_link=args.get("product_link"),
        )
    except Exception:
        return None


def extract_balanced_json(text: str, start_idx: int = 0) -> Optional[str]:
    """Extract first balanced JSON object starting at/after start_idx."""
    open_idx = (text or "").find("{", max(0, start_idx))
    if open_idx == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx: idx + 1]
    return None


def extract_pseudo_search_products_args(text: str) -> Optional[dict]:
    """Detect pseudo tool-call text and extract search_products args JSON."""
    marker = "to=search_products"
    marker_idx = (text or "").find(marker)
    if marker_idx == -1:
        return None
    raw_json = extract_balanced_json(text, marker_idx)
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class AgentQueryResult:
    """Result from running agent query (CLI version)."""

    def __init__(self) -> None:
        self.response: str = ""
        self.tool_calls_made: list = []
        self.tool_results_received: dict = {}
        self.current_product: Optional[str] = None
        self.final_messages: list = []
        self.product_memory: Optional[ProductMemory] = None


async def run_agent_query(
    query: str,
    messages: list,
    current_product: Optional[str],
    product_memory_manager: Optional[ProductMemoryManager] = None,
    verbose_logs: bool = False,
    log_func: Optional[Callable[[str], None]] = None,
) -> AgentQueryResult:
    """Run agent query with streaming and return a complete AgentQueryResult.

    Used by the CLI (main.py). For the Streamlit streaming runner see
    src/ui/agent_runner.py which adds on_stream_chunk and UI-specific logging.
    """
    if log_func is None:
        log_func = print
    if product_memory_manager is None:
        product_memory_manager = ProductMemoryManager()

    result = AgentQueryResult()

    messages = messages.copy()
    messages.append(HumanMessage(content=query))

    context_msg = product_memory_manager.get_context_message()
    if context_msg:
        messages.insert(-1, context_msg)

    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        msg_preview = msg.content[:80] if hasattr(msg, "content") else str(msg)[:80]
        log_func(f"  Message {i}: {msg_type} - {msg_preview}")

    log_func("🔄 Starting agent stream...")

    response_chunks: list = []
    saw_text_chunk = False
    chunk_count = 0
    latest_products: list = []

    async for mode, data in orchestrator_agent.astream(
        {"messages": messages},
        stream_mode=["values", "messages"],
    ):
        chunk_count += 1

        if mode == "messages":
            chunk = data[0] if isinstance(data, tuple) and data else data
            chunk_type = type(chunk).__name__  # noqa: F841 (used for debugging)

            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    response_chunks.append(chunk.content)
                    saw_text_chunk = True
                for tc in getattr(chunk, "tool_call_chunks", None) or []:
                    if tc.get("name"):
                        result.tool_calls_made.append(tc["name"])

            elif isinstance(chunk, AIMessage) and not isinstance(chunk, AIMessageChunk):
                if chunk.content and not saw_text_chunk:
                    response_chunks.append(chunk.content)
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        extracted_memory = extract_product_memory_from_tool_call(tc)
                        if extracted_memory:
                            product_memory_manager.current_memory = extracted_memory

            elif isinstance(chunk, ToolMessage):
                if chunk.name == "search_products":
                    try:
                        result_data = json.loads(chunk.content or "{}")
                        product_count = len(result_data.get("products", []))
                        result.tool_results_received[chunk.name] = product_count
                        latest_products = result_data.get("products", []) or []
                        extracted = extract_current_product(chunk.content or "")
                        if extracted:
                            result.current_product = extracted
                        product_memory_manager.update_with_previous(chunk.content or "")
                    except json.JSONDecodeError:
                        pass

        elif mode == "values":
            result.final_messages = data.get("messages", [])

    # Build final response
    if result.final_messages:
        last = result.final_messages[-1]
        if isinstance(last, AIMessage) and isinstance(last.content, str):
            result.response = last.content.strip()
    if not result.response:
        result.response = "".join(response_chunks).strip()

    # Ground price response to tool results when LLM response drifts
    if latest_products and _is_price_query(query) and not _response_mentions_any_product(result.response, latest_products):
        result.response = _build_grounded_price_response(latest_products)

    # Ground link response to tool results when LLM drifts to generic guidance
    if latest_products and _is_link_query(query) and "http" not in (result.response or "").lower():
        result.response = _build_grounded_link_response(latest_products, query)

    # Handle fallback for pseudo tool calls
    if not result.tool_calls_made and not result.tool_results_received:
        pseudo_args = extract_pseudo_search_products_args(result.response)
        if pseudo_args is not None:
            extracted_memory = extract_product_memory_from_tool_call(
                {"name": "search_products", "args": pseudo_args}
            )
            if extracted_memory:
                product_memory_manager.current_memory = extracted_memory
                result.product_memory = extracted_memory

    product_memory_manager.persist_current()
    return result
