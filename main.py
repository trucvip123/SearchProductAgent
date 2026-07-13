import asyncio
import os
import re
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from src.agent import LOCAL_MODEL
from src.agent import run_agent_query
from src.agent import ProductMemoryManager


def _is_verbose_enabled() -> bool:
    return os.getenv("VERBOSE_LOGS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


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

    product_family_keywords: dict[str, list[str]] = {
        "gpu": ["card màn hình", "card man hinh", "vga", "gpu", "rtx", "gtx", "radeon"],
        "server": ["máy chủ", "may chu", "server", "vmware", "esxi", "proliant", "poweredge"],
        "laptop": ["laptop", "notebook", "thinkpad", "macbook"],
        "storage": ["nas", "ổ cứng", "o cung", "ssd", "hdd", "synology", "qnap"],
        "network": ["switch", "router", "firewall", "wifi", "access point"],
    }

    query_lower = input_query.lower()
    product_lower = current_product.lower()

    def _is_more_results_followup(q: str) -> bool:
        patterns = [
            r"\bc[oò]n\b.*\bkh[aá]c\b",
            r"s[aả]n\s*ph[aẩ]m\s*n[aà]o\s*kh[aá]c",
            r"ngo[aà]i\s+ra",
            r"kh[aá]c\s*(ko|kh[oô]ng)",
        ]
        return any(re.search(pattern, q or "") for pattern in patterns)

    # "còn ... khác" usually means ask for more results under current constraints,
    # not a topic switch.
    if _is_more_results_followup(query_lower):
        if verbose:
            _log("  [TOPIC_DETECT] Follow-up 'more results' detected → same topic")
        return False

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

    def _detect_product_family(text: str) -> str | None:
        normalized = (text or "").lower()
        if not normalized:
            return None
        for family, keywords in product_family_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                return family
        return None

    current_family = _detect_product_family(product_lower)
    query_family = _detect_product_family(query_lower)
    if verbose:
        _log(f"  [TOPIC_DETECT] current_family={current_family}, query_family={query_family}")

    if current_family and query_family and current_family != query_family:
        if verbose:
            _log(f"  [TOPIC_DETECT] MATCH → Topic change (family mismatch: {current_family} vs {query_family})")
        return True

    # Explicit topic change keywords
    explicit_change = [
        "thay đổi",
        "đổi sang",
        "chuyển sang",
        "hãng khác",
        "brand khác",
        "loại khác",
        "dòng khác",
        "model khác",
    ]
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
    def _is_more_results_followup(q: str) -> bool:
        patterns = [
            r"\bc[oò]n\b.*\bkh[aá]c\b",
            r"s[aả]n\s*ph[aẩ]m\s*n[aà]o\s*kh[aá]c",
            r"ngo[aà]i\s+ra",
            r"kh[aá]c\s*(ko|kh[oô]ng)",
        ]
        return any(re.search(pattern, q or "") for pattern in patterns)

    def _is_general_chat_message(q: str) -> bool:
        text = re.sub(r"\s+", " ", (q or "").strip().lower())
        if not text:
            return False
        patterns = [
            r"^(hi|hello|hey|alo|yo)\W*$",
            r"^(ok|oke|okay|v[âa]ng|d[ạa]|uhm+)\W*$",
            r"^(ch[aà]o|xin\s+ch[aà]o|ch[aà]o\s+bạn)\W*$",
            r"^(c[aả]m\s*ơn|thanks?|thank\s+you)\W*$",
            r"^(bye|tạm\s+biệt|tam\s+biet|hẹn\s+gặp\s+lại)\W*$",
        ]
        return any(re.search(pattern, text) for pattern in patterns)

    if _is_general_chat_message(input_query):
        if verbose:
            _log("  [QUERY_BUILD] General chit-chat detected -> keep query as-is")
        return input_query

    if _is_more_results_followup(input_query.lower()):
        if verbose:
            _log("  [QUERY_BUILD] Follow-up 'more results' → keep query as-is")
        return input_query

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
    product_memory_manager = ProductMemoryManager(verbose=verbose_logs)  # ← NEW: Track ProductMemory
    
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
            product_memory_manager.previous_memory = None  # ← NEW: Reset ProductMemory on topic change
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
        
        # ← NEW: Add system context about previous ProductMemory to help LLM preserve fields
        context_msg = product_memory_manager.get_context_message()
        if context_msg:
            messages.insert(-1, context_msg)  # Insert before the latest HumanMessage
            _log(f"[PRODUCT_MEMORY] Added context message about previous memory")
        
        # ← NEW: If query was enriched, add a helper message to make LLM aware of the context
        # This ensures the LLM uses enriched query when calling search_products
        if effective_query != input_query:
            enrichment_note = (
                f"[Ngữ cảnh: {effective_query}]\n\n"
                f"Dựa trên ngữ cảnh trên, hãy tìm kiếm sản phẩm."
            )
            context_msg_enriched = SystemMessage(content=enrichment_note)
            messages.insert(-1, context_msg_enriched)
            _log(f"[ENRICHMENT] Added query enrichment context")
        
        _log(f"[STATE] Messages: {len(messages)} items, current_product: {current_product or 'None'}")

        # Use shared agent handler for query execution
        agent_result = await run_agent_query(
            query=input_query,
            messages=messages[:-1],  # Exclude the HumanMessage we just added (it's added inside run_agent_query)
            current_product=current_product,
            product_memory_manager=product_memory_manager,
            verbose_logs=verbose_logs,
            log_func=_log,
        )
        
        # Update state from result
        final_response = agent_result.response
        current_product = agent_result.current_product or current_product
        messages = agent_result.final_messages
        
        _log(f"[RUN_SUMMARY] Tool calls: {agent_result.tool_calls_made}, Results: {agent_result.tool_results_received}")
        _log(f"[RUN_SUMMARY] Final product: {current_product or 'None'}")
        
        _log("─" * 80)

        if final_response:
            _log(f"\nFinal assistant response: {final_response}")
        else:
            _log("\nFinal assistant response: <empty>")

        _log(f"Run completed. Conversation items after run: {len(messages)}")
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
