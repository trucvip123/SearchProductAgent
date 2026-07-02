"""
Streamlit UI for SearchProductAgent - Tương tác thuận tiện với agent
"""

import asyncio
import json
import os
import re
from datetime import datetime
from io import StringIO

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    ToolMessage,
)

from agent import orchestrator_agent, LOCAL_MODEL


# ─────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────


def _extract_current_product(tool_content: str) -> str | None:
    """Trích tên sản phẩm đầu tiên từ JSON kết quả tool."""
    try:
        data = json.loads(tool_content)
        products = data.get("products") or []
        if products:
            return products[0].get("tên") or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _is_topic_change(input_query: str, current_product: str | None) -> bool:
    """Phát hiện topic change dựa trên entity mismatch."""
    if not current_product:
        return False

    brand_keywords: dict[str, list[str]] = {
        "intel":      ["intel", "xeon", "core i", "pentium", "celeron"],
        "amd":        ["amd", "opteron", "ryzen", "epyc", "athlon"],
        "dell":       ["dell", "poweredge"],
        "hpe":        ["hpe", "proliant", "hewlett"],
        "asus":       ["asus"],
        "lenovo":     ["lenovo", "thinkpad", "thinkcentre"],
        "supermicro": ["supermicro"],
        "wd":         ["western digital", "wd "],
        "seagate":    ["seagate"],
        "synology":   ["synology"],
    }

    query_lower = input_query.lower()
    product_lower = current_product.lower()

    current_brand: str | None = None
    for brand, keywords in brand_keywords.items():
        if any(kw in product_lower for kw in keywords):
            current_brand = brand
            break

    query_brand: str | None = None
    for brand, keywords in brand_keywords.items():
        if any(kw in query_lower for kw in keywords):
            query_brand = brand
            break

    if current_brand and query_brand and current_brand != query_brand:
        return True

    explicit_change = ["sản phẩm khác", "tìm cái khác", "thay đổi", "loại khác", "cái khác"]
    if any(kw in query_lower for kw in explicit_change):
        return True

    return False


def _build_effective_query(input_query: str, current_product: str | None) -> str:
    """Ghép current_product vào đầu query nếu chưa có."""
    if not current_product:
        return input_query
    if current_product.lower() in input_query.lower():
        return input_query
    if _is_topic_change(input_query, current_product):
        return input_query
    short = re.sub(r'\b(Model|Product|Series|Type)\b', '', current_product, flags=re.IGNORECASE).strip()
    return f"{short} {input_query}"


async def run_agent_query(
    query: str,
    messages: list,
    current_product: str | None,
    verbose_logs: bool = False
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
    logs = []
    tool_calls_made = []
    tool_results_received = {}
    response_chunks = []
    new_current_product = current_product

    def _log_msg(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{ts}] {msg}")

    # Topic detection
    topic_changed = _is_topic_change(query, current_product)
    if topic_changed:
        _log_msg(f"✓ Topic change detected: resetting context")
        new_current_product = None
    else:
        _log_msg(f"✓ Same topic: keeping context")

    # Build effective query
    effective_query = _build_effective_query(query, current_product)
    if effective_query != query:
        _log_msg(f"✓ Query enriched: '{effective_query}'")
    else:
        _log_msg(f"✓ Query unchanged")

    os.environ["RUN_USER_QUERY"] = effective_query
    messages.append(HumanMessage(content=query))
    _log_msg(f"Running agent with {len(messages)} messages...")

    # Stream agent
    async for mode, data in orchestrator_agent.astream(
        {"messages": messages},
        stream_mode=["values", "messages"],
    ):
        if mode == "messages":
            chunk, _meta = data
            if isinstance(chunk, AIMessageChunk):
                if chunk.content:
                    response_chunks.append(chunk.content)
                if verbose_logs:
                    for tc in getattr(chunk, "tool_call_chunks", None) or []:
                        if tc.get("name"):
                            tool_name = tc['name']
                            tool_calls_made.append(tool_name)
                            _log_msg(f"📞 TOOL_CALL: {tool_name}")
            elif isinstance(chunk, ToolMessage):
                if chunk.name == "search_products":
                    try:
                        result_data = json.loads(chunk.content or "{}")
                        product_count = len(result_data.get("products", []))
                        tool_results_received[chunk.name] = product_count
                        _log_msg(f"📊 TOOL_RESULT: {chunk.name} → {product_count} products")

                        extracted = _extract_current_product(chunk.content or "")
                        if extracted:
                            new_current_product = extracted
                            _log_msg(f"✓ Product detected: {extracted[:60]}...")
                    except json.JSONDecodeError:
                        _log_msg(f"⚠ TOOL_RESULT: {chunk.name} (parse error)")
        elif mode == "values":
            final_state = data
            if final_state and final_state.get("messages"):
                messages = final_state["messages"]

    response = "".join(response_chunks)
    _log_msg(f"✓ Agent response ready ({len(response)} chars)")

    return {
        "response": response,
        "messages": messages,
        "current_product": new_current_product,
        "topic_changed": topic_changed,
        "tool_calls": tool_calls_made,
        "tool_results": tool_results_received,
        "logs": logs,
    }


# ─────────────────────────────────────────────────────────────────
# Streamlit App
# ─────────────────────────────────────────────────────────────────


st.set_page_config(
    page_title="🔍 SearchProductAgent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# Sidebar Settings
# ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Cài đặt")
    
    verbose_mode = st.checkbox("🔍 Verbose Mode", value=True, help="Hiển thị chi tiết logs")
    show_logs = st.checkbox("📋 Hiển thị Logs", value=True, help="Bảng logs chi tiết")
    auto_scroll_logs = st.checkbox("↓ Auto Scroll Logs", value=True)
    
    st.divider()
    
    st.subheader("📊 Thông tin Agent")
    st.text(f"Model: {LOCAL_MODEL}")
    st.text(f"LLM Endpoint: {os.getenv('OPENAI_BASE_URL')}")
    
    st.divider()
    
    if st.button("🗑️ Xóa lịch sử", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_product = None
        st.session_state.logs = []
        st.rerun()
    
    if st.button("📖 Về SearchProductAgent", use_container_width=True):
        st.info(
            """
            **SearchProductAgent** là một agent thông minh để tìm kiếm sản phẩm.
            
            Tính năng:
            - 🧠 Phát hiện topic change (tự reset context nếu user đổi brand)
            - 🔗 Query enrichment (tự ghi nhớ sản phẩm đang hỏi)
            - 🛠️ Tool calling (gọi search_products khi cần)
            - 📝 Enhanced logging (logs chi tiết từng bước)
            """
        )


# ─────────────────────────────────────────────────────────────────
# Main Chat Interface
# ─────────────────────────────────────────────────────────────────

st.title("🔍 SearchProductAgent UI")
st.markdown("**Tương tác thuận tiện với agent để tìm kiếm sản phẩm**")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_product" not in st.session_state:
    st.session_state.current_product = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "tool_calls_history" not in st.session_state:
    st.session_state.tool_calls_history = []

# ─────────────────────────────────────────────────────────────────
# Display Current Context
# ─────────────────────────────────────────────────────────────────

col1, col2 = st.columns([3, 1])
with col1:
    if st.session_state.current_product:
        st.info(f"📌 **Sản phẩm hiện tại:** {st.session_state.current_product[:80]}")
    else:
        st.warning("ℹ️ Chưa có sản phẩm trong context")

with col2:
    if st.button("🔄 Reset", help="Reset sản phẩm hiện tại"):
        st.session_state.current_product = None
        st.rerun()

# ─────────────────────────────────────────────────────────────────
# Chat Display Area
# ─────────────────────────────────────────────────────────────────

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg.content)

# ─────────────────────────────────────────────────────────────────
# User Input
# ─────────────────────────────────────────────────────────────────

user_input = st.chat_input("Nhập câu hỏi của bạn...", key="user_input")

if user_input:
    # Display user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # Run agent
    with st.spinner("🔄 Agent đang xử lý..."):
        result = asyncio.run(run_agent_query(
            query=user_input,
            messages=st.session_state.messages,
            current_product=st.session_state.current_product,
            verbose_logs=verbose_mode,
        ))

        # Update state
        st.session_state.messages = result["messages"]
        st.session_state.current_product = result["current_product"]
        st.session_state.logs.extend(result["logs"])
        st.session_state.tool_calls_history.extend(result["tool_calls"])

    # Display agent response
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(result["response"])

    # Display metadata
    col1, col2, col3 = st.columns(3)
    with col1:
        if result["topic_changed"]:
            st.warning("⚠️ Topic changed - context reset")
        else:
            st.success("✓ Same topic")
    with col2:
        if result["tool_calls"]:
            st.info(f"📞 Tools: {', '.join(result['tool_calls'])}")
    with col3:
        if result["tool_results"]:
            st.success(f"📊 Results: {result['tool_results']}")


# ─────────────────────────────────────────────────────────────────
# Logs Panel
# ─────────────────────────────────────────────────────────────────

if show_logs:
    st.divider()
    st.subheader("📋 Logs")
    
    if st.session_state.logs:
        logs_text = "\n".join(st.session_state.logs[-50:])  # Last 50 logs
        st.code(logs_text, language="plaintext")
    else:
        st.info("Chưa có logs")

# ─────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────

if st.session_state.messages or st.session_state.tool_calls_history:
    st.divider()
    st.subheader("📈 Thống kê")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💬 Tin nhắn", len(st.session_state.messages))
    with col2:
        st.metric("📞 Tool calls", len(st.session_state.tool_calls_history))
    with col3:
        st.metric("📝 Logs", len(st.session_state.logs))
    with col4:
        unique_tools = len(set(st.session_state.tool_calls_history))
        st.metric("🛠️ Unique Tools", unique_tools)
