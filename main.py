import asyncio
import os
from datetime import datetime
import agents
from dotenv import load_dotenv
from agents import Runner, RunConfig
from openai.types.responses import ResponseTextDeltaEvent
from agents.items import TResponseInputItem
from agents.stream_events import RawResponsesStreamEvent

load_dotenv()
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

from agent import orchestrator_agent, LOCAL_MODEL


def _is_verbose_enabled() -> bool:
    return os.getenv("VERBOSE_LOGS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def _extract_final_response_text(result: object, streamed_text: str) -> str:
    """Lấy final response text theo best-effort từ result; fallback về text đã stream."""
    # 1) Ưu tiên final_output nếu SDK có expose.
    final_output = getattr(result, "final_output", None)
    if isinstance(final_output, str) and final_output.strip():
        return final_output

    # 2) Một số SDK trả output_text trực tiếp.
    output_text = getattr(result, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    # 3) fallback: text đã ghép từ streaming deltas.
    return streamed_text


async def main():
    run_config = RunConfig(tracing_disabled=True)
    verbose_logs = _is_verbose_enabled()

    _log(f"Model running: {LOCAL_MODEL}")
    _log(f"Endpoint: {os.getenv('OPENAI_BASE_URL')}")
    _log(f"Verbose logs: {'ON' if verbose_logs else 'OFF'} (set VERBOSE_LOGS=0 to disable)")

    input_items: list[TResponseInputItem] = []
    while True:
        input_query = input("Enter the query: ")
        _log(f"Received user query: {input_query}")

        # Hard guard: lưu query nguyên văn để tool luôn có thể dùng đúng câu user gõ.
        os.environ["RUN_USER_QUERY"] = input_query

        input_items.append({"content": input_query, "role": "user"})
        _log(f"Conversation items before run: {len(input_items)}")

        result = Runner.run_streamed(orchestrator_agent, input_items, run_config=run_config)
        _log("Started streamed run")
        _log("Result: " + repr(result))
        streamed_chunks: list[str] = []

        async for item in result.stream_events():
            _log(f"Stream event type: {type(item)}")
            if not isinstance(item, RawResponsesStreamEvent):
                _log("event data: " + repr(getattr(item, "data", None)))
            if verbose_logs:
                # Log tool call events để phát hiện khi agent không gọi tool
                if item.type == "run_item_stream_event":
                    run_item = getattr(item, "item", None)
                    item_type = getattr(run_item, "type", "?")
                    if item_type == "tool_call_item":
                        tool_name = getattr(getattr(run_item, "raw_item", None), "name", "?")
                        _log(f"Stream event: TOOL_CALL name={tool_name}")
                    elif item_type == "tool_call_output_item":
                        output = repr(getattr(run_item, "output", ""))[:200]
                        _log(f"Stream event: TOOL_RESULT output={output}")
                    else:
                        _log(f"Stream event: run_item type={item_type}")
                elif item.type == "agent_updated_stream_event":
                    agent_name = getattr(getattr(item, "new_agent", None), "name", "?")
                    _log(f"Stream event: AGENT_SWITCH new_agent={agent_name}")

            if item.type == "raw_response_event" and isinstance(item.data, ResponseTextDeltaEvent):
                streamed_chunks.append(item.data.delta)
                print(item.data.delta, end="", flush=True)

        final_response = _extract_final_response_text(result, "".join(streamed_chunks)).strip()
        if final_response:
            _log(f"Final assistant response: {final_response}")
        else:
            _log("Final assistant response: <empty>")

        input_items = result.to_input_list()
        _log(f"Run completed. Conversation items after run: {len(input_items)}")
        print("\n")

                

if __name__ == "__main__":
    asyncio.run(main())