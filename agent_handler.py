"""
Shared agent handling logic for both main.py and streamlit_app.py
Consolidates streaming, message processing, and ProductMemory management
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

from agent import orchestrator_agent
from tools.normal.models import ProductMemory


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


def _has_specific_price(price_text: str) -> bool:
    price = (price_text or "").strip().lower()
    if not price:
        return False
    if any(skip in price for skip in _PRICE_SKIP_KEYWORDS):
        return False
    return bool(re.search(r"\d", price))


def _response_mentions_any_product(response: str, products: list[dict]) -> bool:
    response_lower = (response or "").lower()
    if not response_lower:
        return False
    for product in products or []:
        name = str(product.get("tên") or "").strip().lower()
        if name and name in response_lower:
            return True
    return False


def _build_grounded_price_response(products: list[dict]) -> str:
    if not products:
        return ""

    priced_products = [p for p in products if _has_specific_price(str(p.get("giá") or ""))]
    candidate = priced_products[0] if priced_products else products[0]

    name = str(candidate.get("tên") or "Sản phẩm").strip()
    price = str(candidate.get("giá") or "Chưa có thông tin giá").strip()
    return f"{name} có giá {price}."


# ============================================================================
# UTILITY FUNCTIONS (used by both main.py and streamlit_app.py)
# ============================================================================

def extract_current_product(tool_content: str) -> Optional[str]:
    """Extract first product name from tool result JSON.
    
    Returns None if parse error or no products found.
    """
    try:
        data = json.loads(tool_content)
        products = data.get("products") or []
        if products:
            return products[0].get("tên") or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def extract_product_memory_from_tool_call(tool_call_dict: dict) -> Optional[ProductMemory]:
    """Extract ProductMemory from tool call parameters.
    
    Tool call dict format:
    {
        "name": "search_products",
        "args": {
            "product_type": "...",
            "brand": "...",
            "price_range": "...",
            ...
        }
    }
    """
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


def extract_balanced_json(text: str, start_idx: int) -> Optional[str]:
    """Extract first balanced JSON object starting at/after start_idx."""
    open_idx = text.find("{", start_idx)
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
    marker_idx = text.find(marker)
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


# ============================================================================
# MAIN AGENT QUERY RUNNER
# ============================================================================

class AgentQueryResult:
    """Result from running agent query"""
    def __init__(self):
        self.response: str = ""
        self.tool_calls_made: list[str] = []
        self.tool_results_received: dict[str, int] = {}
        self.current_product: Optional[str] = None
        self.final_messages: list = []
        self.product_memory: Optional[ProductMemory] = None


async def run_agent_query(
    query: str,
    messages: list,
    current_product: Optional[str],
    product_memory_manager,  # ProductMemoryManager instance from caller
    verbose_logs: bool = False,
    log_func: Optional[Callable[[str], None]] = None,
) -> "AgentQueryResult":
    """
    Run agent query with streaming and return complete result.
    
    This is the centralized function used by both main.py and streamlit_app.py.
    
    Args:
        query: User input query
        messages: Conversation message history
        current_product: Current product context
        product_memory_manager: ProductMemoryManager instance
        verbose_logs: Enable detailed logging
        log_func: Optional logging function (default: print)
    
    Returns:
        AgentQueryResult with response, tool calls, etc.
    """
    if log_func is None:
        log_func = print
    
    result = AgentQueryResult()
    
    # Prepare messages
    messages = messages.copy()
    messages.append(HumanMessage(content=query))
    
    # Add context message about previous ProductMemory
    context_msg = product_memory_manager.get_context_message()
    if context_msg:
        messages.insert(-1, context_msg)
    
    # Log all messages before sending
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        msg_preview = msg.content[:80] if hasattr(msg, 'content') else str(msg)[:80]
        log_func(f"  Message {i}: {msg_type} - {msg_preview}")
    
    log_func("🔄 Starting agent stream...")
    
    # Stream agent
    response_chunks: list[str] = []
    saw_text_chunk = False
    chunk_count = 0
    latest_products: list[dict] = []
    
    async for mode, data in orchestrator_agent.astream(
        {"messages": messages},
        stream_mode=["values", "messages"],
    ):
        chunk_count += 1
        
        if mode == "messages":
            # data is a tuple of message objects, extract the first one
            if isinstance(data, tuple) and len(data) > 0:
                chunk = data[0]
            else:
                chunk = data
            
            chunk_type = type(chunk).__name__
            
            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    response_chunks.append(chunk.content)
                    saw_text_chunk = True
                    # if verbose_logs:
                    #     log_func(f"  ✓ AIMessageChunk: {len(chunk.content)} chars")
                
                # Extract tool calls from chunks
                for tc in getattr(chunk, "tool_call_chunks", None) or []:
                    if tc.get("name"):
                        tool_name = tc['name']
                        result.tool_calls_made.append(tool_name)
            
            elif isinstance(chunk, AIMessage) and not isinstance(chunk, AIMessageChunk):
                # Handle full AIMessage objects
                # Avoid duplicate text when backend emits both chunks and final AIMessage.
                if chunk.content and not saw_text_chunk:
                    response_chunks.append(chunk.content)
                    if verbose_logs:
                        log_func(f"  ✓ AIMessage: {len(chunk.content)} chars")
                
                # Extract ProductMemory from tool_calls in AIMessage
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
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
                        
                        # Update current product
                        extracted = extract_current_product(chunk.content or "")
                        if extracted:
                            result.current_product = extracted
                        
                        # Update ProductMemory from search results
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

    # Ground final text to tool result for price questions, avoiding unrelated hallucinated products.
    if latest_products and _is_price_query(query) and not _response_mentions_any_product(result.response, latest_products):
        result.response = _build_grounded_price_response(latest_products)
    
    # Handle fallback for pseudo tool calls
    if not result.tool_calls_made and not result.tool_results_received:
        pseudo_args = extract_pseudo_search_products_args(result.response)
        if pseudo_args is not None:
            extracted_memory = extract_product_memory_from_tool_call({
                "name": "search_products",
                "args": pseudo_args
            })
            if extracted_memory:
                product_memory_manager.current_memory = extracted_memory
                result.product_memory = extracted_memory
    
    # Update memory manager with final state
    product_memory_manager.persist_current()
    
    return result
