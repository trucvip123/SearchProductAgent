"""
Streamlit UI for SearchProductAgent - Tương tác thuận tiện với agent
"""

import os
import streamlit as st
from dotenv import load_dotenv

# Setup environment
load_dotenv()
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

# Import from src.ui modules
from src.ui import (
    print_log,
    run_async,
    run_agent_query,
    render_page_config,
    render_sidebar,
    render_header,
    render_current_context,
    render_chat_history,
    render_response_metadata,
    render_logs_panel,
)
from src.agent import LOCAL_MODEL
from src.agent import ProductMemoryManager


# ─────────────────────────────────────────────────────────────────
# Page Configuration
# ─────────────────────────────────────────────────────────────────

render_page_config()


# ─────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────

verbose_mode, show_logs, auto_scroll_logs = render_sidebar()


# ─────────────────────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────────────────────

render_header()

print_log("="*60)
print_log("🚀 Streamlit app initialized")
print_log(f"Model: {LOCAL_MODEL}")
print_log(f"LLM Endpoint: {os.getenv('OPENAI_BASE_URL')}")
print_log("="*60)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_product" not in st.session_state:
    st.session_state.current_product = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "tool_calls_history" not in st.session_state:
    st.session_state.tool_calls_history = []
if "product_memory_manager" not in st.session_state:
    st.session_state.product_memory_manager = ProductMemoryManager()


# Display current context
render_current_context()

# Display chat history
render_chat_history()

# User input
user_input = st.chat_input("Nhập câu hỏi của bạn...", key="user_input")

if user_input:
    print_log(f"📝 User input received: {user_input}")
    
    # Display user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # Stream API Responses for streamlit
    with st.chat_message("assistant", avatar="🤖"):
        response_placeholder = st.empty()
        response_placeholder.markdown("▌")

    # Run agent
    print_log(f"🤖 Starting agent execution...")
    with st.spinner("🔄 Agent đang xử lý..."):
        try:
            def _stream_to_ui(partial_text: str):
                if partial_text and partial_text.strip():
                    response_placeholder.markdown(f"{partial_text}▌")

            result = run_async(run_agent_query(
                query=user_input,
                messages=st.session_state.messages,
                current_product=st.session_state.current_product,
                product_memory_manager=st.session_state.product_memory_manager,
                verbose_logs=verbose_mode,
                on_stream_chunk=_stream_to_ui,
            ))
            
            print_log(f"✅ Agent execution completed successfully")
            print_log(f"📊 Response length: {len(result['response'])} chars")
            print_log(f"🛠️ Tool calls: {result['tool_calls']}")
            print_log(f"📈 Tool results: {result['tool_results']}")

            # Update state
            st.session_state.messages = result["messages"]
            st.session_state.current_product = result["current_product"]
            st.session_state.logs.extend(result["logs"])
            st.session_state.tool_calls_history.extend(result["tool_calls"])
        except Exception as e:
            error_msg = str(e)
            print_log(f"❌ Agent execution failed: {error_msg}")
            st.error(f"❌ Lỗi khi chạy agent: {error_msg}")
            st.session_state.logs.append(f"[ERROR] {error_msg}")
            response_placeholder.empty()
            
            result = {
                "response": "",
                "messages": st.session_state.messages,
                "current_product": st.session_state.current_product,
                "topic_changed": False,
                "tool_calls": [],
                "tool_results": {},
                "logs": [f"[ERROR] {error_msg}"],
            }

    # Display agent response
    if result["response"].strip():
        print_log(f"📨 Displaying agent response ({len(result['response'])} chars)")
        response_placeholder.markdown(result["response"])
    else:
        print_log("⚠️ Agent did not generate a response")
        response_placeholder.empty()
        st.warning("⚠️ Agent did not generate a response. Check logs for details.")

    # Display metadata
    render_response_metadata(result)


# Logs Panel
if show_logs:
    render_logs_panel(st.session_state.logs)
