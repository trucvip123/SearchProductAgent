"""Agent query runner with streaming and logging."""

import json
import os
import re
from datetime import datetime
from typing import Callable, Optional

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    ToolMessage,
    SystemMessage,
)

from agent import orchestrator_agent
from product_memory import ProductMemoryManager
from .logging_utils import print_log
from .query_utils import extract_current_product, is_topic_change, build_effective_query


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


async def run_agent_query(
    query: str,
    messages: list,
    current_product: Optional[str],
    product_memory_manager: Optional[ProductMemoryManager] = None,
    verbose_logs: bool = False,
    on_stream_chunk: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Chạy agent query và trả về kết quả, trạng thái mới.
    
    Returns:
        {
            "response": str,          # câu trả lời cuối
            "messages": list,         # messages mới (cập nhật)
            "current_product": str | None,  # sản phẩm được detect
            "topic_changed": bool,    # có topic change?
            "tool_calls": list,       # danh sách tool được gọi
            "tool_results": dict,     # tool → kết quả
            "logs": list              # logs từ quá trình run
        }
    """
    if product_memory_manager is None:
        product_memory_manager = ProductMemoryManager()
    
    logs = []
    tool_calls_made = []
    tool_results_received = {}
    response_chunks = []
    saw_text_chunk = False
    new_current_product = current_product
    latest_products: list[dict] = []

    def _log_msg(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{ts}] {msg}"
        logs.append(log_entry)
        print_log(msg)  # Print to terminal AND file

    # Topic detection
    topic_changed = is_topic_change(query, current_product)
    if topic_changed:
        _log_msg(f"✓ Topic change detected: resetting context")
        new_current_product = None
        product_memory_manager.reset()  # Reset ProductMemory on topic change
    else:
        _log_msg(f"✓ Same topic: keeping context")

    # Build effective query
    effective_query = build_effective_query(query, current_product)
    if effective_query != query:
        _log_msg(f"✓ Query enriched: '{effective_query}'")
    else:
        _log_msg(f"✓ Query unchanged")

    os.environ["RUN_USER_QUERY"] = effective_query
    messages.append(HumanMessage(content=query))
    
    # Add context message about previous ProductMemory
    context_msg = product_memory_manager.get_context_message()
    if context_msg:
        messages.insert(-1, context_msg)
        _log_msg(f"✓ Added ProductMemory context message")
    
    # Add enrichment message if query was enriched
    if effective_query != query:
        enrichment_note = f"[Ngữ cảnh: {effective_query}]\n\nDựa trên ngữ cảnh trên, hãy tìm kiếm sản phẩm."
        messages.insert(-1, SystemMessage(content=enrichment_note))
        _log_msg(f"✓ Added query enrichment context")
    
    _log_msg(f"Running agent with {len(messages)} messages...")
    
    # Log all messages before sending
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        msg_preview = msg.content[:80] if hasattr(msg, 'content') else str(msg)[:80]
        _log_msg(f"  Message {i}: {msg_type} - {msg_preview}")

    # Stream agent
    _log_msg(f"🔄 Streaming from orchestrator_agent...")
    chunk_count = 0
    async for mode, data in orchestrator_agent.astream(
        {"messages": messages},
        stream_mode=["values", "messages"],
    ):
        # _log_msg(f"Streaming mode: {mode}, data type: {type(data).__name__}, data: {str(data)[:80]}")
        chunk_count += 1
        if mode == "messages":
            # data is a tuple of message objects, extract the first one
            if isinstance(data, tuple) and len(data) > 0:
                chunk = data[0]
            else:
                chunk = data
            chunk_type = type(chunk).__name__
            # _log_msg(f"  [Chunk {chunk_count}] Type: {chunk_type}, ID: {id(chunk)}")
            
            # ALWAYS log chunk details regardless of type
            # if hasattr(chunk, 'content'):
            #     content_val = chunk.content if hasattr(chunk, 'content') else None
                # content_len = len(str(content_val)) if content_val else 0
                # Log full content for errors, truncate for normal content
                # if content_val and isinstance(content_val, str) and '"status": "error"' in content_val:
                #     _log_msg(f"       Has 'content' attr: len={content_len}, FULL_ERROR={repr(content_val)}")
                # else:
                #     _log_msg(f"       Has 'content' attr: len={content_len}, value={repr(content_val)[:80]}")
            
            # if hasattr(chunk, 'tool_call_chunks'):
            #     _log_msg(f"       Has 'tool_call_chunks' attr: {hasattr(chunk, 'tool_call_chunks')}")
            
            if isinstance(chunk, AIMessageChunk):
                # _log_msg(f"  ✅ Confirmed AIMessageChunk instance")
                if chunk.content:
                    response_chunks.append(chunk.content)
                    saw_text_chunk = True
                    # _log_msg(f"       Added to response: {chunk.content[:100] if len(chunk.content) > 100 else chunk.content}")
                    if on_stream_chunk:
                        try:
                            on_stream_chunk("".join(response_chunks))
                        except Exception as callback_error:
                            _log_msg(f"⚠ Stream callback error: {callback_error}")
                
                if verbose_logs:
                    for tc in getattr(chunk, "tool_call_chunks", None) or []:
                        if tc.get("name"):
                            tool_name = tc['name']
                            tool_calls_made.append(tool_name)
                            _log_msg(f"📞 TOOL_CALL: {tool_name}")
            
            elif isinstance(chunk, AIMessage) and not isinstance(chunk, AIMessageChunk):
                # Handle full AIMessage objects (not chunks)
                _log_msg(f"  ✅ AIMessage (full) - content len: {len(chunk.content) if chunk.content else 0}")
                # Avoid duplicate text: some backends emit both streamed chunks and the final full AIMessage.
                if chunk.content and not saw_text_chunk:
                    response_chunks.append(chunk.content)
                    _log_msg(f"       Added to response: {chunk.content[:100] if len(chunk.content) > 100 else chunk.content}")
                    if on_stream_chunk:
                        try:
                            on_stream_chunk("".join(response_chunks))
                        except Exception as callback_error:
                            _log_msg(f"⚠ Stream callback error: {callback_error}")
                            
            elif isinstance(chunk, ToolMessage):
                # Safely access chunk.name with default
                tool_name = getattr(chunk, 'name', 'unknown')
                _log_msg(f"  🛠️ ToolMessage from: {tool_name}")
                
                if tool_name == "search_products":
                    try:
                        result_data = json.loads(chunk.content or "{}")
                        
                        # Check if this is an error response
                        if result_data.get("status") == "error":
                            error_msg = result_data.get("message", "Unknown error")
                            tool_results_received[tool_name] = f"ERROR: {error_msg}"
                            _log_msg(f"❌ TOOL_ERROR: {tool_name} → {error_msg}")
                        else:
                            product_count = len(result_data.get("products", []))
                            tool_results_received[tool_name] = product_count
                            _log_msg(f"📊 TOOL_RESULT: {tool_name} → {product_count} products")
                            latest_products = result_data.get("products", []) or []

                            extracted = extract_current_product(chunk.content or "")
                            if extracted:
                                new_current_product = extracted
                                _log_msg(f"✓ Product detected: {extracted[:60]}...")
                    except json.JSONDecodeError as e:
                        _log_msg(f"⚠ TOOL_RESULT: {tool_name} (parse error: {str(e)})")
        elif mode == "values":
            final_state = data
            _log_msg(f"  [Values] State has {len(final_state.get('messages', []))} messages")
            if final_state and final_state.get("messages"):
                messages = final_state["messages"]

    response = "".join(response_chunks)
    _log_msg(f"✓ Agent streaming complete ({chunk_count} chunks)")
    _log_msg(f"✓ Agent response ready ({len(response)} chars)")
    if response:
        _log_msg(f"  Response preview: {response[:150]}")
    else:
        _log_msg(f"  ⚠️ Response is EMPTY!")

    # Ground final text to tool result for price questions, avoiding unrelated hallucinated products.
    if latest_products and _is_price_query(query) and not _response_mentions_any_product(response, latest_products):
        response = _build_grounded_price_response(latest_products)
        _log_msg("✓ Response grounded from latest search_products result")
        if on_stream_chunk:
            try:
                on_stream_chunk(response)
            except Exception as callback_error:
                _log_msg(f"⚠ Stream callback error: {callback_error}")
    
    # Persist ProductMemory for next turn
    product_memory_manager.persist_current()
    _log_msg(f"✓ ProductMemory persisted for next turn")

    return {
        "response": response,
        "messages": messages,
        "current_product": new_current_product,
        "topic_changed": topic_changed,
        "tool_calls": tool_calls_made,
        "tool_results": tool_results_received,
        "logs": logs,
    }
