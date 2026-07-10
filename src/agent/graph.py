"""Core agent graph — routing, state, and compiled orchestrator.

This is the canonical implementation. agent.py (root) is a backward-compatible shim.
"""

import re
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from langchain.agents import create_agent

from ..models import LOCAL_MODEL, _build_llm
from ..tools import search_products
from ..prompts import ORCHESTRATOR_PROMPT, GENERAL_ASSISTANT_PROMPT
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
        "seagate", "synology", "qnap", "nas", "storage", "raid", "proliant",
        "poweredge", "dưới", "duoi", "triệu", "trieu",
    ]

    if any(k in q for k in product_keywords):
        return True

    # Model/SKU-like token (e.g. R740, DS925+, RX580, E5-2680) → product query.
    for token in re.findall(r"[a-z0-9.+-]+", q):
        if len(token) < 4:
            continue
        if any(ch.isalpha() for ch in token) and any(ch.isdigit() for ch in token):
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
    return {
        "messages": [
            AIMessage(
                content=response.content if isinstance(response.content, str) else str(response.content)
            )
        ]
    }


_graph_builder = StateGraph(OrchestratorState)
_graph_builder.add_node("router", _route_node)
_graph_builder.add_node("product_agent", product_agent)
_graph_builder.add_node("general_agent", _general_node)
_graph_builder.add_edge(START, "router")
_graph_builder.add_conditional_edges(
    "router",
    _route_next,
    {"product_agent": "product_agent", "general_agent": "general_agent"},
)
_graph_builder.add_edge("product_agent", END)
_graph_builder.add_edge("general_agent", END)

orchestrator_agent = _graph_builder.compile()
