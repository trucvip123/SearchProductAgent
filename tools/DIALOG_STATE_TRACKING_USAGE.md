"""Example: Cách integrate Dialog State Tracking vào SearchProductAgent.

Ví dụ này cho thấy flow đầy đủ:
1. User gửi query
2. LLM extract ProductMemory
3. DialogManager detect topic change
4. Quyết định reset hay continue context
5. Gọi search_products tool
6. Save state
"""

# ────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE 1: Trong agent.py
# ────────────────────────────────────────────────────────────────────────

"""
from dialog_manager import DialogManager, check_and_handle_topic_change
from normal.tools import ProductMemory

class SearchProductAgent:
    def __init__(self):
        self.dialog_manager = DialogManager()
        self.llm = ...  # initialize LLM
        
    async def process_user_query(self, user_query: str) -> str:
        '''
        Main agent loop với Dialog State Tracking.
        '''
        
        # 1. LLM extract ProductMemory from user_query
        product_memory = await self.llm.extract_product_memory(user_query)
        
        # 2. Check topic change & get guidance
        topic_result = await check_and_handle_topic_change(
            dialog_manager=self.dialog_manager,
            user_query=user_query,
            product_memory=product_memory,
            agent_context=self.current_context,
        )
        
        # 3. Update agent context nếu topic change
        if topic_result["topic_changed"]:
            self.current_context = topic_result["updated_agent_context"]
            self.llm.clear_conversation_history()  # Reset conversation
            
            # Thêm context reset message vào system prompt
            reset_msg = topic_result["context_reset_message"]
            print(f"[Agent] Topic changed: {reset_msg}")
        
        # 4. Gọi search_products tool (như thường)
        search_result = await self.search_products_tool(
            user_query=user_query,
            **product_memory.to_dict(),
        )
        
        # 5. LLM generate response
        response = await self.llm.generate_response(
            user_query=user_query,
            search_result=search_result,
            guidance=topic_result["guidance"],
        )
        
        return response

agent = SearchProductAgent()
response = await agent.process_user_query("tìm máy chủ Dell")
"""

# ────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE 2: Trong main.py
# ────────────────────────────────────────────────────────────────────────

"""
from dialog_manager import DialogManager

# Conversation flow
dialog_manager = DialogManager()

# Turn 1: User asks about Dell server
query1 = "tìm máy chủ Dell PowerEdge R740"
memory1 = ProductMemory(brand="Dell", series="PowerEdge", model="R740")
result1 = dialog_manager.detect_topic_change(query1, memory1)
print(result1)
# Output:
# {
#     "topic_changed": False,
#     "change_reason": None,
#     "action": "continue",
#     ...
# }

# Turn 2: User follows up with more details (clarification)
query2 = "giá bao nhiêu, xin link"
memory2 = ProductMemory(brand="Dell", series="PowerEdge", model="R740")  # Same
result2 = dialog_manager.detect_topic_change(query2, memory2)
print(result2)
# Output:
# {
#     "topic_changed": False,
#     "action": "clarify",  # Follow-up question
#     ...
# }

# Turn 3: User switches to different product
query3 = "tôi muốn tìm ổ cứng ngoài Western Digital"
memory3 = ProductMemory(product_type="ổ cứng ngoài", brand="WD")
result3 = dialog_manager.detect_topic_change(query3, memory3)
print(result3)
# Output:
# {
#     "topic_changed": True,  # DETECTED!
#     "change_reason": "entity_mismatch",  # Different product_type
#     "action": "reset",
#     "prev_product": {"brand": "Dell", "series": "PowerEdge", ...},
#     "active_product": {"product_type": "ổ cứng ngoài", "brand": "WD"},
#     "dialog_state_summary": {
#         "turn_count": 3,
#         "product_history_count": 1,
#         ...
#     }
# }

# Turn 4: Another clarification
query4 = "còn hàng không"
memory4 = ProductMemory(product_type="ổ cứng ngoài", brand="WD")  # Same as turn 3
result4 = dialog_manager.detect_topic_change(query4, memory4)
print(result4)
# Output:
# {
#     "topic_changed": False,
#     "action": "clarify",
#     "active_product": {"product_type": "ổ cứng ngoài", "brand": "WD"},
# }

# Export conversation history
conversation_json = dialog_manager.export_conversation()
print(conversation_json)
"""

# ────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE 3: Topic change detection mechanisms
# ────────────────────────────────────────────────────────────────────────

"""
Dialog State Tracker phát hiện topic change qua:

1. EXPLICIT_REQUEST
   - User: "tôi muốn tìm sản phẩm khác"
   - Keywords: "khác", "thay đổi", "tìm kiếm khác"

2. ENTITY_MISMATCH
   - Previous: brand=Dell, model=R740, product_type=máy chủ
   - Current: brand=WD, product_type=ổ cứng ngoài
   - Action: Detected topic change vì brand/product_type khác

3. SEMANTIC_DISTANCE
   - Previous: "máy chủ Dell PowerEdge R740 128GB RAM"
   - Current: "laptop Lenovo ThinkPad"
   - Similarity score < threshold → topic change

4. DOMAIN_SWITCH
   - Previous: Server domain (máy chủ, CPU, RAM, HDD)
   - Current: Storage domain (ổ cứng, SSD, NAS)
   - Action: Detected domain switch

5. CLARIFICATION (NOT a topic change)
   - Previous: brand=Dell, series=PowerEdge
   - Current: brand=Dell, series=PowerEdge (same)
   - User query: "giá bao nhiêu", "xin link", "thông số"
   - Action: "clarify" (continue with same product)
"""

# ────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE 4: State logging & debugging
# ────────────────────────────────────────────────────────────────────────

"""
Logs khi turn 3 (topic change):
[DialogManager] Turn 3: TOPIC CHANGED (entity_mismatch) | Dell PowerEdge → WD

Logs khi turn 4 (clarification):
[DialogManager] Turn 4: CLARIFY | Product: WD

Trích xuất từ dialog_state_summary:
{
    "turn_count": 4,
    "active_product": {
        "product_type": "ổ cứng ngoài",
        "brand": "WD",
        "capacity": "2TB"
    },
    "product_history_count": 1,  # Đã track 1 sản phẩm cũ (Dell)
    "last_update": "2026-07-01T10:30:45.123456"
}

Lấy product history:
dialog_manager.get_product_history()
# Output:
# [
#     {
#         "product": {"brand": "Dell", "series": "PowerEdge", "model": "R740"},
#         "query": "Dell PowerEdge R740"
#     }
# ]
"""

# ────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE 5: Integration với LLM prompt
# ────────────────────────────────────────────────────────────────────────

"""
Khi topic change detected, update LLM system prompt:

SYSTEM_PROMPT_TEMPLATE = '''
Bạn là agent điều phối kiêm tra cứu sản phẩm từ PostgreSQL Vector DB.

{context}

Quy tắc chọn hành động:
- Câu hỏi liên quan sản phẩm → gọi search_products
- Câu hỏi chung → trả lời trực tiếp
'''

# Khi topic change:
current_context = dialog_manager.get_context_for_llm()
if current_context.get("message"):
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        context=current_context["message"]
    )
    # Sử dụng system_prompt này khi gọi LLM
    
# current_context:
{
    "current_product_context": {
        "product_type": "ổ cứng ngoài",
        "brand": "WD",
        "capacity": "2TB"
    },
    "previous_products": [
        {
            "product": {"brand": "Dell", "series": "PowerEdge"},
            "query": "Dell PowerEdge"
        }
    ],
    "product_history_count": 1,
    "is_topic_aware": True,
    "message": "Người dùng đã chuyển sang sản phẩm khác. "
               "Bây giờ tập trung vào ổ cứng ngoài WD. "
               "Quên những thông tin về sản phẩm cũ."
}
"""

print(__doc__)
