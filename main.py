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
from tools.normal.tools import search_products


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


def _extract_balanced_json(text: str, start_idx: int) -> str | None:
    """Extract the first balanced JSON object starting at/after start_idx."""
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


def _extract_pseudo_search_products_args(text: str) -> dict | None:
    """Detect pseudo tool-call text and extract search_products args JSON."""
    marker = "to=search_products"
    marker_idx = text.find(marker)
    if marker_idx == -1:
        return None

    raw_json = _extract_balanced_json(text, marker_idx)
    if not raw_json:
        return None

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _format_search_products_result(tool_content: str) -> str:
    """Render search tool JSON into a concise, user-facing Vietnamese response."""
    try:
        data = json.loads(tool_content)
    except (json.JSONDecodeError, TypeError):
        return tool_content.strip() if isinstance(tool_content, str) else ""

    status = data.get("status")
    if status == "error":
        return data.get("message") or "Đã xảy ra lỗi khi tra cứu dữ liệu sản phẩm."

    if status == "no_products":
        return data.get("message") or "Không tìm thấy sản phẩm phù hợp trong dữ liệu hiện tại."

    products = data.get("products") or []
    if not products:
        return "Không tìm thấy sản phẩm phù hợp trong dữ liệu hiện tại."

    lines = [f"Tìm thấy {len(products)} sản phẩm phù hợp:"]
    for idx, p in enumerate(products[:10], 1):
        name = p.get("tên") or "N/A"
        price = p.get("giá") or "N/A"
        brand = p.get("hãng") or "Unknown"
        lines.append(f"{idx}. {name} | Giá: {price} | Hãng: {brand}")

    return "\n".join(lines)


def _is_topic_change(input_query: str, current_product: str | None, verbose: bool = False) -> bool:
    """Phát hiện topic change dựa trên entity mismatch.

    Nếu user đề cập brand/entity khác với current_product → topic change.
    Không enrich query khi đã phát hiện topic change.
    """
    if not current_product:
        return False

    # Brand/entity mapping: keyword trong query → brand
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

    # Tìm brand của current_product
    current_brand: str | None = None
    for brand, keywords in brand_keywords.items():
        if any(kw in product_lower for kw in keywords):
            current_brand = brand
            break

    # Tìm brand trong query mới
    query_brand: str | None = None
    for brand, keywords in brand_keywords.items():
        if any(kw in query_lower for kw in keywords):
            query_brand = brand
            break

    if verbose:
        _log(f"  [TOPIC_DETECT] current_brand={current_brand}, query_brand={query_brand}")

    # Nếu cả hai đều có brand và khác nhau → topic change
    if current_brand and query_brand and current_brand != query_brand:
        if verbose:
            _log(f"  [TOPIC_DETECT] MATCH → Topic change (brand mismatch: {current_brand} vs {query_brand})")
        return True

    # Explicit topic change keywords
    explicit_change = ["sản phẩm khác", "tìm cái khác", "thay đổi", "loại khác", "cái khác"]
    for kw in explicit_change:
        if kw in query_lower:
            if verbose:
                _log(f"  [TOPIC_DETECT] MATCH → Topic change (keyword: '{kw}')")
            return True

    if verbose:
        _log(f"  [TOPIC_DETECT] No match → Same topic")
    return False


def _build_effective_query(input_query: str, current_product: str | None, verbose: bool = False) -> str:
    """Ghép current_product vào đầu query nếu chưa có trong query.

    Nếu query đã chứa tên/keyword sản phẩm thì giữ nguyên.
    Nếu phát hiện topic change thì không enrich.
    """
    if not current_product:
        if verbose:
            _log(f"  [QUERY_BUILD] No current_product → keep query as-is")
        return input_query
    if current_product.lower() in input_query.lower():
        if verbose:
            _log(f"  [QUERY_BUILD] current_product already in query → keep as-is")
        return input_query
    if _is_topic_change(input_query, current_product, verbose=verbose):
        if verbose:
            _log(f"  [QUERY_BUILD] Topic change detected → keep query as-is (no enrich)")
        return input_query
    # Lấy keyword ngắn gọn nhất từ tên sản phẩm (bỏ các từ chung như Model, Product)
    short = re.sub(r'\b(Model|Product|Series|Type)\b', '', current_product, flags=re.IGNORECASE).strip()
    enriched = f"{short} {input_query}"
    if verbose:
        _log(f"  [QUERY_BUILD] Enriching query → '{enriched}'")
    return enriched


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
        _log(f"Current context: product='{current_product}'")

        # Ghép current_product vào query nếu chưa có → tool có context follow-up.
        # Nếu phát hiện topic change → KHÔNG enrich, reset current_product.
        _log("[TOPIC_DETECTION] Checking if topic changed...")
        if _is_topic_change(input_query, current_product, verbose=verbose_logs):
            _log(f"[TOPIC_DETECTION] ✓ Topic change detected → resetting context (was: '{current_product}')")
            current_product = None
        else:
            _log(f"[TOPIC_DETECTION] ✓ Same topic (continuing with current context)")
        
        _log("[QUERY_BUILD] Building effective query...")
        effective_query = _build_effective_query(input_query, current_product, verbose=verbose_logs)
        os.environ["RUN_USER_QUERY"] = effective_query
        if effective_query != input_query:
            _log(f"[QUERY_BUILD] ✓ Query enriched: '{input_query}' → '{effective_query}'")
        else:
            _log(f"[QUERY_BUILD] ✓ Query unchanged: '{effective_query}'")

        messages.append(HumanMessage(content=input_query))
        _log(f"[STATE] Messages: {len(messages)} items, current_product: {current_product or 'None'}")

        _log("[RUN] Starting agent stream...")
        streamed_chunks: list[str] = []
        final_state = None
        tool_calls_made: list[str] = []
        tool_results_received: dict[str, int] = {}  # tool_name → product_count

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
                                tool_name = tc['name']
                                tool_calls_made.append(tool_name)
                                _log(f"[STREAM] TOOL_CALL: name={tool_name}")
                elif isinstance(chunk, ToolMessage):
                    # Cập nhật current_product từ kết quả tool — luôn chạy bất kể verbose.
                    if chunk.name == "search_products":
                        try:
                            result_data = json.loads(chunk.content or "{}")
                            product_count = len(result_data.get("products", []))
                            tool_results_received[chunk.name] = product_count
                            _log(f"[STREAM] TOOL_RESULT: {chunk.name} returned {product_count} products")
                            
                            extracted = _extract_current_product(chunk.content or "")
                            if extracted:
                                old_product = current_product
                                current_product = extracted
                                _log(f"[STATE] current_product updated: '{old_product}' → '{current_product}'")
                        except json.JSONDecodeError:
                            _log(f"[STREAM] TOOL_RESULT: {chunk.name} (parse error)")
                    else:
                        if verbose_logs:
                            output = repr(chunk.content)[:200]
                            _log(f"[STREAM] TOOL_RESULT: name={chunk.name} output={output}")
            elif mode == "values":
                final_state = data

        # Cập nhật lịch sử hội thoại từ state cuối cùng của graph.
        if final_state and final_state.get("messages"):
            messages = final_state["messages"]
            _log(f"[STATE] Updated conversation messages: {len(messages)} items")

        final_response = ""
        if final_state and final_state.get("messages"):
            last = final_state["messages"][-1]
            if isinstance(last, AIMessage) and isinstance(last.content, str):
                final_response = last.content.strip()
        if not final_response:
            final_response = "".join(streamed_chunks).strip()

        # Fallback: model in pseudo tool-call text instead of making a real tool call.
        if not tool_calls_made and not tool_results_received:
            pseudo_args = _extract_pseudo_search_products_args(final_response)
            if pseudo_args is not None:
                _log(f"[FALLBACK] Detected pseudo tool-call. Executing search_products with args={pseudo_args}")
                try:
                    tool_content = await search_products.ainvoke(pseudo_args)
                    try:
                        parsed = json.loads(tool_content or "{}")
                        tool_results_received["search_products"] = len(parsed.get("products") or [])
                    except (json.JSONDecodeError, AttributeError):
                        tool_results_received["search_products"] = 0

                    extracted = _extract_current_product(tool_content or "")
                    if extracted:
                        old_product = current_product
                        current_product = extracted
                        _log(f"[STATE] current_product updated by fallback: '{old_product}' → '{current_product}'")

                    final_response = _format_search_products_result(tool_content or "")
                except Exception as exc:
                    _log(f"[FALLBACK] Failed to execute pseudo tool-call: {exc}")

        _log(f"[RUN_SUMMARY] Tool calls: {tool_calls_made}, Results: {tool_results_received}")
        _log(f"[RUN_SUMMARY] Streamed {len(streamed_chunks)} chunks, Final product: {current_product or 'None'}")
        _log("─" * 80)

        if final_response:
            _log(f"\nFinal assistant response: {final_response}")
        else:
            _log("\nFinal assistant response: <empty>")

        _log(f"Run completed. Conversation items after run: {len(messages)}")
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
