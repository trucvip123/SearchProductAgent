from src.agent.graph import _build_routing_context, _heuristic_product_route


def test_heuristic_routes_clear_price_and_model_queries_to_product():
    assert _heuristic_product_route("giá máy chủ Dell R740 khoảng 45 triệu") is True
    assert _heuristic_product_route("tôi cần Dell PowerEdge R740 với 64GB RAM") is True
    assert _heuristic_product_route("bên bạn có những sản phẩm gì?") is False
    assert _heuristic_product_route("bán những hãng nào?") is False


def test_build_routing_context_uses_recent_messages():
    messages = [
        {"type": "human", "content": "hello"},
        {"type": "ai", "content": "hi"},
        {"type": "human", "content": "show me servers"},
        {"type": "ai", "content": "sure"},
        {"type": "human", "content": "compare Dell and HPE"},
        {"type": "ai", "content": "I can help"},
        {"type": "human", "content": "what about the price?"},
    ]

    context = _build_routing_context(messages, limit=6)

    assert len(context) == 6
    assert context[-1]["content"] == "what about the price?"
    assert context[0]["content"] == "show me servers"
