"""Integration Guide: Thêm Dialog State Tracking vào agent.py

Step-by-step hướng dẫn để tích hợp DST vào SearchProductAgent.

═══════════════════════════════════════════════════════════════════════════════
STEP 1: Import Dialog Manager
═══════════════════════════════════════════════════════════════════════════════

Thêm vào agent.py:

```python
from tools.dialog_manager import DialogManager, check_and_handle_topic_change
```

═══════════════════════════════════════════════════════════════════════════════
STEP 2: Initialize DialogManager trong Agent
═══════════════════════════════════════════════════════════════════════════════

```python
class SearchProductAgent:
    def __init__(self):
        # Existing initialization
        self.llm = ChatOpenAI(...)
        # ...
        
        # NEW: Initialize Dialog State Tracker
        from tools.dialog_manager import DialogManagementConfig, DialogManager
        
        dst_config = DialogManagementConfig(
            topic_change_threshold=0.6,
            enable_state_logging=True,
            verbose=True,
        )
        self.dialog_manager = DialogManager(dst_config)
        
        # Maintain current agent context
        self.agent_context = {}
```

═══════════════════════════════════════════════════════════════════════════════
STEP 3: Add Topic Change Detection dalam Agent Loop
═══════════════════════════════════════════════════════════════════════════════

```python
async def process_user_query(self, user_query: str) -> str:
    '''
    Agent loop với Dialog State Tracking.
    '''
    
    # 1. LLM extract ProductMemory from user_query
    from langchain_core.messages import HumanMessage
    
    extraction_prompt = '''
    Extract product information from user query.
    Return JSON with: product_type, brand, series, model, cpu, ram, etc.
    '''
    
    # Thực hiện extraction (tuỳ thuộc vào LLM setup)
    product_memory = ProductMemory(...)  # Extracted from user_query
    
    # 2. CHECK TOPIC CHANGE ← NEW STEP
    topic_result = await check_and_handle_topic_change(
        dialog_manager=self.dialog_manager,
        user_query=user_query,
        product_memory=product_memory,
        agent_context=self.agent_context,
    )
    
    # 3. Update agent context if topic changed
    if topic_result["topic_changed"]:
        print(f"[Agent] Topic changed: {topic_result['action']}")
        print(f"[Agent] {topic_result['context_reset_message']}")
        
        # Update context
        self.agent_context = topic_result["updated_agent_context"]
        
        # Optional: Clear LLM conversation history
        # self.conversation_history.clear()
        
        # Optional: Add system message để LLM biết topic đã change
        # system_msg = topic_result["context_reset_message"]
    
    # 4. Call search_products tool (unchanged)
    search_result = await search_products(
        user_query=user_query,
        product_type=product_memory.product_type,
        brand=product_memory.brand,
        series=product_memory.series,
        model=product_memory.model,
        # ... other fields
    )
    
    # 5. Generate response
    response = await self.llm.generate_response(
        user_query=user_query,
        search_result=search_result,
        guidance=topic_result["guidance"],  # Additional context
    )
    
    return response
```

═══════════════════════════════════════════════════════════════════════════════
STEP 4: Handle Topic Change in LLM Prompts (Optional)
═══════════════════════════════════════════════════════════════════════════════

Có thể thêm context về topic change vào system prompt:

```python
SYSTEM_PROMPT_TEMPLATE = '''
Bạn là agent tìm kiếm sản phẩm từ PostgreSQL Vector Database.

{product_context}

Quy tắc:
- Câu liên quan sản phẩm → gọi search_products
- Câu chung → trả lời trực tiếp
'''

# Khi detect topic change:
if topic_result["topic_changed"]:
    product_context = topic_result["updated_agent_context"].get("product_context", {})
    context_message = product_context.get("message", "")
    
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        product_context=context_message
    )
    
    # Sử dụng system_prompt này khi gọi LLM
    response = await self.llm.generate_response(
        system_prompt=system_prompt,
        user_query=user_query,
        search_result=search_result,
    )
```

═══════════════════════════════════════════════════════════════════════════════
STEP 5: Export & Analyze Conversations (Optional)
═══════════════════════════════════════════════════════════════════════════════

```python
# After conversation ends
conversation_export = self.dialog_manager.export_conversation()

# Save to file
with open("conversation_state.json", "w") as f:
    f.write(conversation_export)

# Get summary
summary = self.dialog_manager.tracker.get_state_summary()
print(f"Total turns: {summary['turn_count']}")
print(f"Products discussed: {summary['product_history_count'] + 1}")
print(f"Active product: {summary['active_product']}")

# Get product history
product_history = self.dialog_manager.get_product_history()
for i, item in enumerate(product_history, 1):
    print(f"Product {i}: {item['query']}")
```

═══════════════════════════════════════════════════════════════════════════════
MINIMAL INTEGRATION (Tối giản)
═══════════════════════════════════════════════════════════════════════════════

Nếu chỉ muốn detect topic change mà không thay đổi toàn bộ:

```python
# Minimal version (just detect, no action)
async def process_user_query(self, user_query: str):
    product_memory = ProductMemory(...)  # Extract
    
    # Detect topic change (read-only, không thay đổi behavior)
    topic_result = await check_and_handle_topic_change(
        dialog_manager=self.dialog_manager,
        user_query=user_query,
        product_memory=product_memory,
        agent_context=self.agent_context,
    )
    
    # Log for debugging
    if topic_result["topic_changed"]:
        print(f"[DEBUG] Topic changed: {topic_result['action']}")
    
    # Rest of agent logic unchanged
    response = await search_products(...)
    return response
```

═══════════════════════════════════════════════════════════════════════════════
COMPLETE EXAMPLE (main.py)
═══════════════════════════════════════════════════════════════════════════════

```python
import asyncio
from agent import SearchProductAgent, orchestrator_agent
from tools.dialog_manager import DialogManager

async def main():
    agent = SearchProductAgent()
    
    # Simulated conversation
    queries = [
        "tìm máy chủ Dell PowerEdge",
        "giá bao nhiêu",
        "tôi muốn tìm ổ cứng ngoài Western Digital",
        "dung lượng bao nhiêu",
        "xin link sản phẩm",
    ]
    
    for query in queries:
        print(f"\\nUser: {query}")
        response = await agent.process_user_query(query)
        print(f"Agent: {response}")
    
    # Export conversation state
    state_export = agent.dialog_manager.export_conversation()
    print(f"\\nConversation state exported: {len(state_export)} characters")
    
    # Summary
    summary = agent.dialog_manager.tracker.get_state_summary()
    print(f"\\nSummary:")
    print(f"  Total turns: {summary['turn_count']}")
    print(f"  Products: {summary['product_history_count'] + 1}")

if __name__ == "__main__":
    asyncio.run(main())
```

═══════════════════════════════════════════════════════════════════════════════
TESTING
═══════════════════════════════════════════════════════════════════════════════

Để test Dialog State Tracking:

```bash
# Run demo
python tools/test_dialog_state_tracking.py

# Output sẽ show:
# - Basic DST mechanics
# - Topic change detection
# - Various detection mechanisms
# - Slot operations
```

═══════════════════════════════════════════════════════════════════════════════
DEBUGGING
═══════════════════════════════════════════════════════════════════════════════

Enable verbose logging:

```python
from tools.dialog_manager import DialogManagementConfig, DialogManager

config = DialogManagementConfig(
    enable_state_logging=True,
    verbose=True,
)
manager = DialogManager(config)
```

Logs sẽ show:
```
[DialogManager] Turn 1: CONTINUE | Product: Dell PowerEdge
[DialogManager] Turn 2: CLARIFY | Product: Dell PowerEdge
[DialogManager] Turn 3: TOPIC CHANGED (entity_mismatch) | Dell PowerEdge → WD
```

═══════════════════════════════════════════════════════════════════════════════
CONFIGURATION TUNING
═══════════════════════════════════════════════════════════════════════════════

topic_change_threshold:
- Default: 0.6
- Higher (0.7-0.8): Less sensitive → need more explicit change to detect
- Lower (0.4-0.5): More sensitive → detect change easier

enable_state_logging:
- True: Print logs for debugging
- False: Silent mode (production)

verbose:
- True: Detailed logs
- False: Minimal logs

Example for strict topic detection:
```python
config = DialogManagementConfig(
    topic_change_threshold=0.7,  # Strict
    enable_state_logging=True,
    verbose=True,
)
```

═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Problem: Topic change not detected
Solution: Lower topic_change_threshold (e.g., 0.5 instead of 0.6)

Problem: Too many false positives
Solution: Raise topic_change_threshold (e.g., 0.7)

Problem: Losing context on topic change
Solution: Implement context preservation in get_context_for_llm()

Problem: State not persisting
Solution: Call export_conversation() to save state to file
"""

print(__doc__)
