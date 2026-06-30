import asyncio
import json
import os
import re
from datetime import datetime

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


def _is_verbose_enabled() -> bool:
    return os.getenv("VERBOSE_LOGS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def _extract_current_product(tool_content: str) -> str | None:
    """Trích tên sản phẩm đầu tiên từ JSON kết quả tool.

    Trả None nếu không parse được hoặc không có sản phẩm.
    """
    try:
        data = json.loads(tool_content)
        products = data.get("products") or []
        if products:
            return products[0].get("tên") or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _build_effective_query(input_query: str, current_product: str | None) -> str:
    """Ghép current_product vào đầu query nếu chưa có trong query.

    Nếu query đã chứa tên/keyword sản phẩm thì giữ nguyên.
    """
    if not current_product:
        return input_query
    if current_product.lower() in input_query.lower():
        return input_query
    # Lấy keyword ngắn gọn nhất từ tên sản phẩm (bỏ các từ chung như Model, Product)
    short = re.sub(r'\b(Model|Product|Series|Type)\b', '', current_product, flags=re.IGNORECASE).strip()
    return f"{short} {input_query}"


async def main():
    verbose_logs = _is_verbose_enabled()

    _log(f"Model running: {LOCAL_MODEL}")
    _log(f"Endpoint: {os.getenv('OPENAI_BASE_URL')}")
    _log(f"Verbose logs: {'ON' if verbose_logs else 'OFF'} (set VERBOSE_LOGS=0 to disable)")

    messages: list = []
    current_product: str | None = None  # sản phẩm/thực thể đang được hỏi
    while True:
        input_query = input("Enter the query: ")
        _log(f"Received user query: {input_query}")

        # Ghép current_product vào query nếu chưa có → tool có context follow-up.
        effective_query = _build_effective_query(input_query, current_product)
        os.environ["RUN_USER_QUERY"] = effective_query
        if effective_query != input_query:
            _log(f"RUN_USER_QUERY (enriched): '{effective_query}'")
        else:
            _log(f"RUN_USER_QUERY: '{effective_query}'")

        messages.append(HumanMessage(content=input_query))
        _log(f"Conversation items before run: {len(messages)}")

        _log("Started streamed run")
        streamed_chunks: list[str] = []
        final_state = None

        async for mode, data in orchestrator_agent.astream(
            {"messages": messages},
            stream_mode=["values", "messages"],
        ):
            if mode == "messages":
                chunk, _meta = data
                # Stream token của câu trả lời cuối (AIMessageChunk có content).
                if isinstance(chunk, AIMessageChunk):
                    if chunk.content:
                        streamed_chunks.append(chunk.content)
                        print(chunk.content, end="", flush=True)
                    if verbose_logs:
                        for tc in getattr(chunk, "tool_call_chunks", None) or []:
                            if tc.get("name"):
                                _log(f"Stream event: TOOL_CALL name={tc['name']}")
                elif isinstance(chunk, ToolMessage):
                    # Cập nhật current_product từ kết quả tool — luôn chạy bất kể verbose.
                    if chunk.name == "search_products":
                        extracted = _extract_current_product(chunk.content or "")
                        if extracted:
                            current_product = extracted
                            _log(f"current_product updated: '{current_product}'")
                    if verbose_logs:
                        output = repr(chunk.content)[:200]
                        _log(f"Stream event: TOOL_RESULT name={chunk.name} output={output}")
            elif mode == "values":
                final_state = data

        # Cập nhật lịch sử hội thoại từ state cuối cùng của graph.
        if final_state and final_state.get("messages"):
            messages = final_state["messages"]

        final_response = ""
        if final_state and final_state.get("messages"):
            last = final_state["messages"][-1]
            if isinstance(last, AIMessage) and isinstance(last.content, str):
                final_response = last.content.strip()
        if not final_response:
            final_response = "".join(streamed_chunks).strip()

        if final_response:
            _log(f"\nFinal assistant response: {final_response}")
        else:
            _log("\nFinal assistant response: <empty>")

        _log(f"Run completed. Conversation items after run: {len(messages)}")
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
