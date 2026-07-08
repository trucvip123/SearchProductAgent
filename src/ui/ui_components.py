"""Streamlit UI components."""

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent import LOCAL_MODEL
import os


def render_page_config():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="🔍 SearchProductAgent",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar(verbose_mode_default=False, show_logs_default=False, auto_scroll_logs_default=False):
    """Render sidebar with settings and controls."""
    with st.sidebar:
        st.title("⚙️ Cài đặt")
        
        verbose_mode = st.checkbox("🔍 Verbose Mode", value=verbose_mode_default, help="Hiển thị chi tiết logs")
        show_logs = st.checkbox("📋 Hiển thị Logs", value=show_logs_default, help="Bảng logs chi tiết")
        auto_scroll_logs = st.checkbox("↓ Auto Scroll Logs", value=auto_scroll_logs_default)
        
        st.divider()
        
        st.subheader("📊 Thông tin Agent")
        st.text(f"Model: {LOCAL_MODEL}")
        st.text(f"LLM Endpoint: {os.getenv('OPENAI_BASE_URL')}")
        
        st.divider()
        
        if st.button("🗑️ Xóa lịch sử", use_container_width=True):
            st.session_state.messages = []
            st.session_state.current_product = None
            st.session_state.logs = []
            st.session_state.product_memory_manager.reset()
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
    
    return verbose_mode, show_logs, auto_scroll_logs


def render_header():
    """Render page header."""
    st.title("🔍 SearchProductAgent UI")
    st.markdown("**Tương tác thuận tiện với agent để tìm kiếm sản phẩm**")


def render_current_context():
    """Render current product context display."""
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.current_product:
            st.info(f"📌 **Sản phẩm hiện tại:** {st.session_state.current_product[:80]}")
        else:
            st.warning("ℹ️ Chưa có sản phẩm trong context")

    with col2:
        if st.button("🔄 Reset", help="Reset sản phẩm hiện tại"):
            st.session_state.current_product = None
            st.session_state.product_memory_manager.reset()
            st.rerun()


def render_chat_history():
    """Render chat message history."""
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages:
            if isinstance(msg, HumanMessage):
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg.content)
            elif isinstance(msg, AIMessage):
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg.content)
    
    return chat_container


def render_agent_response(response_text: str):
    """Render agent response in chat."""
    if response_text.strip():
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(response_text)
    else:
        st.warning("⚠️ Agent did not generate a response. Check logs for details.")


def render_response_metadata(result: dict):
    """Render metadata about the response (topic change, tool calls, results)."""
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


def render_logs_panel(logs: list):
    """Render logs display panel."""
    st.divider()
    st.subheader("📋 Logs")
    
    if logs:
        logs_text = "\n".join(logs[-50:])  # Last 50 logs
        st.code(logs_text, language="plaintext")
    else:
        st.info("Chưa có logs")


def render_statistics(messages: list, tool_calls_history: list, logs: list):
    """Render statistics panel."""
    if messages or tool_calls_history:
        st.divider()
        st.subheader("📈 Thống kê")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💬 Tin nhắn", len(messages))
        with col2:
            st.metric("📞 Tool calls", len(tool_calls_history))
        with col3:
            st.metric("📝 Logs", len(logs))
        with col4:
            unique_tools = len(set(tool_calls_history))
            st.metric("🛠️ Unique Tools", unique_tools)
