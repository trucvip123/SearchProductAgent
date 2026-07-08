from os import getenv
import re
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from tools.normal.tools import search_products


LOCAL_MODEL = getenv("LOCAL_MODEL", "llama3.1:8b")


def _build_llm() -> ChatOpenAI:
    """Tạo LLM trỏ tới endpoint OpenAI-compatible (mặc định Ollama local)."""
    return ChatOpenAI(
        model=LOCAL_MODEL,
        base_url=getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
        api_key=getenv("OPENAI_API_KEY", "ollama"),
        temperature=0,
        streaming=True,
    )


ORCHESTRATOR_PROMPT = """/no_think
Bạn là agent điều phối kiêm tra cứu sản phẩm từ PostgreSQL Vector DB.

Phạm vi sản phẩm hỗ trợ:
- Máy chủ, thiết bị lưu trữ, máy bộ, laptop, máy tính
- Thiết bị mạng, linh kiện máy chủ, thiết bị văn phòng, phần mềm

Quy tắc chọn hành động:
- Câu hỏi liên quan sản phẩm/giá/cấu hình/hãng/model/link/tình trạng hàng:
  → PHẢI gọi tool search_products trước khi trả lời. TUYỆT ĐỐI không tự bịa giá hay đoán cấu hình.
- Câu hỏi chung KHÔNG liên quan sản phẩm (chào hỏi, khái niệm chung):
  → Trả lời trực tiếp ngắn gọn bằng tiếng Việt, không cần gọi tool.

Khi gọi search_products:
- Điền các structured field bạn nhận ra được (brand, series, model, cpu, ram, capacity, interface, product_type, price_range).
- **QUAN TRỌNG: Giữ nguyên (preserve) các field từ lượt hội thoại trước:**
    * Nếu user không mention thay đổi một field (ví dụ: product_type, brand) → GIỮ NGUYÊN giá trị cũ
    * Chỉ THAY ĐỔI khi user rõ ràng mention (ví dụ: "thay đổi sang loại khác", "tìm hãng khác", "giá khác")
- Tham số user_query phải chứa đủ ngữ cảnh để tìm kiếm độc lập:
    * Câu hỏi đầy đủ: dùng NGUYÊN VĂN câu user hỏi, không rút gọn.
    * Câu follow-up thiếu ngữ cảnh (ví dụ: "xin link", "giá bao nhiêu", "còn hàng không", "thông số kỹ thuật"):
      PHẢI gộp tên sản phẩm/model từ lượt hội thoại trước vào đầu user_query.
      Ví dụ: lượt trước hỏi "amd opteron 1381", lượt này hỏi "xin link sản phẩm"
             → user_query = "amd opteron 1381 xin link sản phẩm"
- Không làm rơi cụm mô tả loại sản phẩm và các cụm kỹ thuật (brand, model, CPU, số hiệu).

Cách trả lời — TRẢ LỜI ĐÚNG & ĐỦ CÂU HỎI, KHÔNG THỪA:
- Chỉ trả lời đúng thông tin người dùng HỎI:
    * Hỏi giá        → chỉ trả lời giá (+ tên sản phẩm để xác định).
    * Hỏi link       → chỉ trả lời link (+ tên sản phẩm).
    * Hỏi cấu hình   → chỉ trả lời cấu hình liên quan.
    * Hỏi tổng quan  → trả lời đầy đủ tên, giá, hãng, cấu hình chính.
- KHÔNG liệt kê tất cả thông tin khi người dùng chỉ hỏi một trường cụ thể.
- Nếu tool trả về nhiều sản phẩm nhưng user hỏi về 1 sản phẩm → chỉ dùng kết quả khớp nhất.
- Nếu tool báo không tìm thấy: nói rõ "không tìm thấy trong dữ liệu hiện tại" và đề nghị cung cấp model/từ khóa khác.
- Không viết câu meta kiểu "tôi sẽ gọi agent khác", "đợi một chút".

Ví dụ đúng:
  User: "giá máy chủ Dell R740 bao nhiêu?"
  ✅ "Máy chủ Dell PowerEdge R740 có giá 45.000.000 đồng."
  ❌ "Máy chủ Dell PowerEdge R740, hãng: Dell, cấu hình: Xeon Gold 6248, RAM 128GB, giá: 45.000.000 đồng, link: ..."
"""

GENERAL_ASSISTANT_PROMPT = """/no_think
Bạn là trợ lý VNPT GIA LAI hỗ trợ chung cho các câu hỏi KHÔNG liên quan tìm sản phẩm trong database.

Nguyên tắc:
- Trả lời ngắn gọn, rõ ràng bằng tiếng Việt.
- Không bịa giá/cấu hình/link sản phẩm.
- Nếu user hỏi liên quan sản phẩm, yêu cầu họ nêu rõ tiêu chí để agent tra cứu.
"""


class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]
    route: str


def _latest_user_content(messages: list) -> str:
    for msg in reversed(messages or []):
        if getattr(msg, "type", "") == "human":
            content = getattr(msg, "content", "")
            return content if isinstance(content, str) else ""
    return ""


def _is_product_query(query: str) -> bool:
    q = (query or "").lower().strip()
    if not q:
        return False

    product_keywords = [
        "giá", "gia", "cấu hình", "cau hinh", "cpu", "ram", "ssd", "hdd",
        "model", "series", "link", "sản phẩm", "san pham", "máy chủ", "may chu",
        "server", "laptop", "thinkpad", "lenovo", "dell", "hpe", "asus", "wd",
        "seagate", "synology", "proliant", "poweredge", "dưới", "duoi", "triệu", "trieu",
    ]

    if any(k in q for k in product_keywords):
        return True

    return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(triệu|trieu|tr|m|tỷ|ty|b|vnd|đ)?\b", q))


async def _route_node(state: OrchestratorState) -> dict:
    query = _latest_user_content(state.get("messages", []))
    route: Literal["product", "general"] = "product" if _is_product_query(query) else "general"
    return {"route": route}


def _route_next(state: OrchestratorState) -> Literal["product_agent", "general_agent"]:
    return "product_agent" if state.get("route") == "product" else "general_agent"


product_agent = create_agent(
    model=_build_llm(),
    tools=[search_products],
    system_prompt=ORCHESTRATOR_PROMPT,
)


async def _general_node(state: OrchestratorState) -> dict:
    messages = state.get("messages", [])
    llm = _build_llm()
    response = await llm.ainvoke([SystemMessage(content=GENERAL_ASSISTANT_PROMPT), *messages])
    return {"messages": [AIMessage(content=response.content if isinstance(response.content, str) else str(response.content))]}


_graph_builder = StateGraph(OrchestratorState)
_graph_builder.add_node("router", _route_node)
_graph_builder.add_node("product_agent", product_agent)
_graph_builder.add_node("general_agent", _general_node)
_graph_builder.add_edge(START, "router")
_graph_builder.add_conditional_edges("router", _route_next, {"product_agent": "product_agent", "general_agent": "general_agent"})
_graph_builder.add_edge("product_agent", END)
_graph_builder.add_edge("general_agent", END)


orchestrator_agent = _graph_builder.compile()
