"""Dialog State Tracking (DST) Implementation Guide

📚 Kỹ thuật từ các hệ thống hội thoại tiên tiến:
- MultiWOZ (Multi-Domain Dialogue Dataset)
- DSTC (Dialog State Tracking Challenge - ACL)
- Các chatbot thương mại (booking.com, hotels.com)

🎯 Mục tiêu:
- Phát hiện khi user chuyển topic/chủ đề sản phẩm
- Reset state liên quan đến sản phẩm cũ
- Initialize state mới cho sản phẩm hiện tại
- Maintain context đầy đủ cho conversation

═══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

1. dialog_state_tracker.py (Core DST Logic)
   └─ DialogStateTracker: Track & detect topic change
   └─ ProductSlot: Represent product entities (brand, model, etc)
   └─ DialogTurn: Represent một lượt hội thoại
   └─ DialogState: Belief state của cuộc hội thoại
   └─ TopicChangeReason: Enum các lý do detect topic change

2. dialog_manager.py (Integration Layer)
   └─ DialogManager: Manage DST trong agent pipeline
   └─ DialogManagementConfig: Configuration
   └─ check_and_handle_topic_change(): Main integration function

3. normal/tools.py (Search Tool)
   └─ search_products(): Tool không thay đổi, vẫn nhận ProductMemory

═══════════════════════════════════════════════════════════════════════════════
HOW IT WORKS
═══════════════════════════════════════════════════════════════════════════════

FLOW DỤC:

┌─────────────────────────────────────────────────────────────────────────────┐
│ User Input: "tôi muốn tìm máy chủ Dell PowerEdge"                          │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LLM Extract ProductMemory                                                   │
│ └─ brand="Dell", series="PowerEdge", product_type="máy chủ"               │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ DialogManager.detect_topic_change()                                         │
│ ├─ Convert ProductMemory → ProductSlot                                      │
│ ├─ Compare với previous_slots (history)                                     │
│ ├─ Detect mechanism:                                                        │
│ │  ├─ Explicit keywords ("khác", "thay đổi")                              │
│ │  ├─ Entity mismatch (brand/model/product_type khác)                      │
│ │  └─ Semantic distance (similarity < threshold)                           │
│ └─ Return: topic_changed, change_reason, action                            │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼ (topic_changed=True)        ▼ (topic_changed=False)
   ┌──────────────────┐          ┌──────────────────┐
   │ RESET STATE      │          │ CONTINUE STATE   │
   ├──────────────────┤          ├──────────────────┤
   │ 1. Save prev →   │          │ 1. Check if:     │
   │    history       │          │    - clarify?    │
   │ 2. Init new      │          │    - continue?   │
   │    state         │          │ 2. Merge slots   │
   │ 3. Clear LLM     │          │    if needed      │
   │    context       │          │ 3. Keep context  │
   └──────────────────┘          └──────────────────┘
        │                             │
        └──────────────┬──────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Call search_products(user_query, **product_memory)                          │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Save DialogTurn to DialogState.conversation_turns                           │
│ ├─ user_query                                                               │
│ ├─ system_response                                                          │
│ ├─ product_slots (current state)                                            │
│ ├─ topic_change_detected (boolean)                                          │
│ ├─ topic_change_reason (enum)                                               │
│ └─ timestamp                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
TOPIC CHANGE DETECTION MECHANISMS
═══════════════════════════════════════════════════════════════════════════════

1. EXPLICIT_REQUEST
   Người dùng yêu cầu rõ ràng sản phẩm khác
   
   Keywords: "khác", "sản phẩm khác", "thay đổi", "tìm cái khác"
   
   Example:
   Turn 1: "tìm máy chủ Dell"
           state.active: brand=Dell, product_type=máy chủ
   
   Turn 2: "tôi muốn tìm sản phẩm khác" ← KEYWORD DETECTED
           → topic_changed = True
           → change_reason = EXPLICIT_REQUEST

2. ENTITY_MISMATCH
   Người dùng specify entities khác nhau (brand, model, product_type)
   
   Detected khi: new_entity ≠ previous_entity
   
   Example:
   Turn 1: "Dell PowerEdge"
           state.active: brand=Dell, product_type=máy chủ
   
   Turn 2: "WD ổ cứng ngoài" ← BRAND CHANGED: Dell → WD
           state.active: brand=WD, product_type=ổ cứng ngoài
           → topic_changed = True
           → change_reason = ENTITY_MISMATCH

3. SEMANTIC_DISTANCE
   Similarity score giữa previous & current slots < threshold
   
   Similarity = matching_fields / total_fields
   (chỉ tính product_type, brand, model)
   
   Example:
   Turn 1: state.active = {brand: Dell, product_type: máy chủ}
   Turn 2: state.active = {brand: Lenovo, product_type: laptop}
   
   Similarity = 0/2 = 0.0 < 0.6 (threshold)
   → topic_changed = True
   → change_reason = SEMANTIC_DISTANCE

4. DOMAIN_SWITCH
   Chuyển giữa các domain khác nhau (server → storage, laptop → network)
   
   Domain inference từ product_type
   
   (Có thể mở rộng sau)

5. CLARIFICATION (NOT a topic change)
   Người dùng hỏi thêm chi tiết về sản phẩm hiện tại
   
   Keywords: "giá", "link", "thông số", "cấu hình", "còn hàng"
   
   Example:
   Turn 1: "máy chủ Dell PowerEdge"
           state.active: brand=Dell, series=PowerEdge
   
   Turn 2: "giá bao nhiêu?" ← CLARIFICATION KEYWORD
           state.active: brand=Dell, series=PowerEdge (NO CHANGE)
           action = "clarify"
           topic_changed = False

═══════════════════════════════════════════════════════════════════════════════
DATA STRUCTURES
═══════════════════════════════════════════════════════════════════════════════

ProductSlot
├─ product_type: str (máy chủ, ổ cứng ngoài, laptop...)
├─ brand: str (Dell, WD, Lenovo...)
├─ series: str (PowerEdge, My Book, ThinkPad...)
├─ model: str (R740xd, DS223j...)
├─ cpu: str (Gold 6248, E-2434...)
├─ ram: str (128GB, 32GB...)
├─ storage: str (2TB SSD...)
├─ capacity: str (3TB, 8TB...)
├─ interface: str (USB 3.0, PCIe...)
├─ price_range: str (dưới 5 triệu...)
└─ product_link: str (URL...)

DialogTurn
├─ user_query: str (câu user hỏi)
├─ system_response: str (response từ tool)
├─ product_slots: ProductSlot (state at this turn)
├─ topic_change_detected: bool
├─ topic_change_reason: TopicChangeReason (enum)
└─ timestamp: str (ISO format)

DialogState
├─ active_product_slots: ProductSlot (current state)
├─ product_history: List[ProductSlot] (previous products)
├─ conversation_turns: List[DialogTurn] (turn history)
├─ turn_count: int
└─ last_product_query_timestamp: str

═══════════════════════════════════════════════════════════════════════════════
INTEGRATION WITH AGENT
═══════════════════════════════════════════════════════════════════════════════

In agent.py:

```python
from dialog_manager import DialogManager, check_and_handle_topic_change

class SearchProductAgent:
    def __init__(self):
        self.dialog_manager = DialogManager()
        # ... other initialization
    
    async def run(self, user_query: str):
        # 1. Extract ProductMemory from query
        product_memory = await self.llm.extract_product_memory(user_query)
        
        # 2. CHECK TOPIC CHANGE ← NEW STEP
        topic_result = await check_and_handle_topic_change(
            dialog_manager=self.dialog_manager,
            user_query=user_query,
            product_memory=product_memory,
            agent_context=self.context,
        )
        
        # 3. Update context if topic changed
        if topic_result["topic_changed"]:
            self.context = topic_result["updated_agent_context"]
            self.llm.clear_history()
            print(f"Topic changed: {topic_result['context_reset_message']}")
        
        # 4. Search products (unchanged)
        search_result = await search_products(**product_memory)
        
        # 5. Generate response
        response = await self.llm.generate_response(
            user_query=user_query,
            search_result=search_result,
        )
        
        return response
```

═══════════════════════════════════════════════════════════════════════════════
CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

DialogManagementConfig:
├─ topic_change_threshold: float = 0.6
│  └─ Ngưỡng similarity để quyết định topic change
│     < 0.6: topic change
│     ≥ 0.6: same topic (continue/clarify)
│
├─ enable_state_logging: bool = True
│  └─ Print logs cho debugging
│
├─ max_conversation_turns: int = 100
│  └─ Max turns để track (có thể reset nếu vượt)
│
└─ verbose: bool = True
   └─ In detailed logs

Example customize:
```python
config = DialogManagementConfig(
    topic_change_threshold=0.7,  # More strict
    enable_state_logging=True,
    verbose=True,
)
dialog_manager = DialogManager(config)
```

═══════════════════════════════════════════════════════════════════════════════
BENEFITS
═══════════════════════════════════════════════════════════════════════════════

✅ Automatic Topic Detection
   - Không cần user nói "thay đổi chủ đề"
   - Agent tự phát hiện & handle

✅ State Isolation
   - Reset state cũ → không bị lẫn lộn thông tin
   - Tránh hallucination

✅ Better UX
   - Agent không hỏi lại thông tin về sản phẩm cũ
   - Context luôn đồng bộ

✅ Conversation History
   - Track đầy đủ hội thoại (turns, products, state changes)
   - Có thể export cho analysis

✅ Scalable
   - Dễ mở rộng cho multi-domain (server, storage, network...)
   - Cấu trúc rõ ràng, dễ maintain

═══════════════════════════════════════════════════════════════════════════════
EXAMPLE CONVERSATION
═══════════════════════════════════════════════════════════════════════════════

User: "tìm máy chủ Dell PowerEdge R740"
[Turn 1] 
└─ Extracted: brand=Dell, series=PowerEdge, model=R740, product_type=máy chủ
└─ Action: CONTINUE (first turn)
└─ State: active={Dell, PowerEdge, R740, máy chủ}

User: "giá bao nhiêu"
[Turn 2]
└─ Extracted: brand=Dell, series=PowerEdge, model=R740 (same)
└─ Similarity: 1.0 (all matching)
└─ Action: CLARIFY (follow-up)
└─ State: active={Dell, PowerEdge, R740, máy chủ} (unchanged)

User: "tôi muốn tìm ổ cứng ngoài Western Digital"
[Turn 3] ← TOPIC CHANGE DETECTED
└─ Extracted: product_type=ổ cứng ngoài, brand=WD
└─ Change reason: ENTITY_MISMATCH (product_type khác)
└─ Action: RESET
└─ State: active={WD, ổ cứng ngoài}
└─ History: [{Dell, PowerEdge, R740, máy chủ}] (saved)
└─ Message: "Người dùng chuyển sang ổ cứng ngoài WD. Quên máy chủ Dell."

User: "còn hàng không"
[Turn 4]
└─ Extracted: product_type=ổ cứng ngoài, brand=WD (same as turn 3)
└─ Action: CLARIFY
└─ State: active={WD, ổ cứng ngoài} (unchanged)

═══════════════════════════════════════════════════════════════════════════════
FILES
═══════════════════════════════════════════════════════════════════════════════

tools/dialog_state_tracker.py
├─ Core DST implementation
├─ Classes: DialogStateTracker, ProductSlot, DialogTurn, DialogState
├─ ~250 lines
└─ No external dependencies (only stdlib + dataclasses)

tools/dialog_manager.py
├─ Integration layer for agent pipeline
├─ Classes: DialogManager, DialogManagementConfig
├─ Functions: check_and_handle_topic_change()
├─ ~300 lines
└─ Depends on: dialog_state_tracker.py, normal.tools.ProductMemory

tools/DIALOG_STATE_TRACKING_USAGE.md
└─ Usage examples & integration patterns

═══════════════════════════════════════════════════════════════════════════════
"""

print(__doc__)
