"""Test & Demo: Dialog State Tracking Implementation

Chạy file này để thấy Dialog State Tracking hoạt động trên ví dụ thực tế.

Usage:
    python test_dialog_state_tracking.py
"""

from dialog_state_tracker import (
    DialogStateTracker,
    ProductSlot,
    TopicChangeReason,
)
from dialog_manager import DialogManager, DialogManagementConfig
from normal.tools import ProductMemory


def demo_basic_dst():
    """Demo cơ bản: Topic change detection."""
    print("\n" + "="*80)
    print("DEMO 1: Basic Dialog State Tracking")
    print("="*80)
    
    tracker = DialogStateTracker(topic_change_threshold=0.6)
    
    # Turn 1: User asks about Dell server
    print("\n[Turn 1] User: 'tìm máy chủ Dell PowerEdge R740'")
    slots_1 = ProductSlot(
        product_type="máy chủ",
        brand="Dell",
        series="PowerEdge",
        model="R740",
        cpu="Gold 6248",
        ram="128GB",
    )
    result_1 = tracker.update(
        user_query="tìm máy chủ Dell PowerEdge R740",
        new_product_slots=slots_1,
        system_response="Found 5 Dell PowerEdge R740 servers",
    )
    print(f"├─ Topic changed: {result_1['topic_changed']}")
    print(f"├─ Action: {result_1['action']}")
    print(f"└─ Active slots: {result_1['curr_slots']}")
    
    # Turn 2: Clarification
    print("\n[Turn 2] User: 'giá bao nhiêu?'")
    slots_2 = ProductSlot(
        product_type="máy chủ",
        brand="Dell",
        series="PowerEdge",
        model="R740",
    )
    result_2 = tracker.update(
        user_query="giá bao nhiêu?",
        new_product_slots=slots_2,
    )
    print(f"├─ Topic changed: {result_2['topic_changed']}")
    print(f"├─ Action: {result_2['action']}")
    print(f"├─ Change reason: {result_2['change_reason']}")
    print(f"└─ Active slots: {result_2['curr_slots']}")
    
    # Turn 3: TOPIC CHANGE - Switch to storage
    print("\n[Turn 3] User: 'tôi muốn tìm ổ cứng ngoài Western Digital'")
    slots_3 = ProductSlot(
        product_type="ổ cứng ngoài",
        brand="WD",
        capacity="2TB",
    )
    result_3 = tracker.update(
        user_query="tôi muốn tìm ổ cứng ngoài Western Digital",
        new_product_slots=slots_3,
    )
    print(f"├─ Topic changed: {result_3['topic_changed']} ← DETECTED!")
    print(f"├─ Action: {result_3['action']}")
    print(f"├─ Change reason: {result_3['change_reason']}")
    print(f"├─ Prev slots: {result_3['prev_slots']}")
    print(f"└─ Curr slots: {result_3['curr_slots']}")
    
    # Turn 4: Continue with storage
    print("\n[Turn 4] User: 'xin link sản phẩm'")
    slots_4 = ProductSlot(
        product_type="ổ cứng ngoài",
        brand="WD",
        capacity="2TB",
    )
    result_4 = tracker.update(
        user_query="xin link sản phẩm",
        new_product_slots=slots_4,
    )
    print(f"├─ Topic changed: {result_4['topic_changed']}")
    print(f"├─ Action: {result_4['action']}")
    print(f"└─ Active slots: {result_4['curr_slots']}")
    
    # Summary
    print("\n" + "-"*80)
    print("SUMMARY:")
    print(f"  Total turns: {tracker.state.turn_count}")
    print(f"  Product history: {len(tracker.state.product_history)} products")
    print(f"  Current active: {tracker.get_state_summary()['active_product']}")
    return tracker


def demo_dialog_manager():
    """Demo DialogManager integration."""
    print("\n" + "="*80)
    print("DEMO 2: Dialog Manager Integration")
    print("="*80)
    
    config = DialogManagementConfig(
        topic_change_threshold=0.6,
        enable_state_logging=True,
        verbose=True,
    )
    manager = DialogManager(config)
    
    # Simulate conversation
    conversations = [
        {
            "query": "tìm máy chủ Dell",
            "memory": ProductMemory(brand="Dell", product_type="máy chủ"),
        },
        {
            "query": "thông số kỹ thuật là gì",
            "memory": ProductMemory(brand="Dell", product_type="máy chủ"),
        },
        {
            "query": "tôi muốn tìm cái khác, ổ cứng WD",
            "memory": ProductMemory(brand="WD", product_type="ổ cứng ngoài"),
        },
        {
            "query": "còn hàng không",
            "memory": ProductMemory(brand="WD", product_type="ổ cứng ngoài"),
        },
    ]
    
    for i, conv in enumerate(conversations, 1):
        print(f"\n[Turn {i}] User: '{conv['query']}'")
        result = manager.detect_topic_change(
            user_query=conv["query"],
            product_memory=conv["memory"],
        )
        print(f"├─ Topic changed: {result['topic_changed']}")
        print(f"├─ Action: {result['action']}")
        print(f"├─ Guidance: {result['guidance']}")
        if result['topic_changed']:
            print(f"└─ Reset message: {result['context_reset_message']}")
    
    # Export conversation
    print("\n" + "-"*80)
    print("Conversation exported:")
    export = manager.export_conversation()
    print(f"Total characters: {len(export)}")
    print(f"Product history: {len(manager.get_product_history())} products")


def demo_topic_change_mechanisms():
    """Demo various topic change detection mechanisms."""
    print("\n" + "="*80)
    print("DEMO 3: Topic Change Detection Mechanisms")
    print("="*80)
    
    tracker = DialogStateTracker(topic_change_threshold=0.6)
    
    test_cases = [
        {
            "name": "1. EXPLICIT_REQUEST",
            "description": "User says 'khác' (different)",
            "prev_slots": ProductSlot(brand="Dell", model="R740"),
            "curr_slots": ProductSlot(brand="WD", capacity="2TB"),
            "query": "tôi muốn tìm sản phẩm khác",
            "expected_reason": "explicit_request",
        },
        {
            "name": "2. ENTITY_MISMATCH",
            "description": "Product type changed",
            "prev_slots": ProductSlot(product_type="máy chủ", brand="Dell"),
            "curr_slots": ProductSlot(product_type="ổ cứng ngoài", brand="WD"),
            "query": "ổ cứng WD",
            "expected_reason": "entity_mismatch",
        },
        {
            "name": "3. SEMANTIC_DISTANCE",
            "description": "Low similarity score",
            "prev_slots": ProductSlot(product_type="máy chủ", brand="Dell"),
            "curr_slots": ProductSlot(product_type="laptop", brand="Lenovo"),
            "query": "laptop Lenovo",
            "expected_reason": "semantic_distance",
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{test['name']}")
        print(f"  Description: {test['description']}")
        print(f"  Query: '{test['query']}'")
        
        # First turn
        tracker.update(
            user_query="initial search",
            new_product_slots=test['prev_slots'],
        )
        
        # Second turn (should trigger topic change)
        result = tracker.update(
            user_query=test['query'],
            new_product_slots=test['curr_slots'],
        )
        
        print(f"  ├─ Topic changed: {result['topic_changed']}")
        print(f"  ├─ Reason: {result['change_reason']}")
        print(f"  └─ Expected: {test['expected_reason']}")
        
        # Reset for next test
        tracker = DialogStateTracker()


def demo_slot_operations():
    """Demo ProductSlot operations."""
    print("\n" + "="*80)
    print("DEMO 4: ProductSlot Operations")
    print("="*80)
    
    # Create slots
    slot1 = ProductSlot(
        brand="Dell",
        series="PowerEdge",
        model="R740",
        cpu="Gold 6248",
        ram="128GB",
    )
    
    slot2 = ProductSlot(
        brand="Dell",
        series="PowerEdge",
        model="R760",  # Different model
        cpu="Gold 6346",
    )
    
    slot3 = ProductSlot(
        brand="WD",
        capacity="2TB",
    )
    
    print("\nSlot 1 (Dell R740):")
    print(f"  to_dict(): {slot1.to_dict()}")
    print(f"  to_search_query(): '{slot1.to_search_query()}'")
    print(f"  is_empty(): {slot1.is_empty()}")
    
    print("\nSlot 2 (Dell R760):")
    print(f"  to_dict(): {slot2.to_dict()}")
    
    print("\nSlot 3 (WD):")
    print(f"  to_dict(): {slot3.to_dict()}")
    
    print("\nSimilarity scores:")
    sim_1_2 = slot1.similarity_score(slot2)
    sim_1_3 = slot1.similarity_score(slot3)
    sim_2_3 = slot2.similarity_score(slot3)
    
    print(f"  Slot1 ↔ Slot2 (Dell R740 vs R760): {sim_1_2:.2f}")
    print(f"  Slot1 ↔ Slot3 (Dell vs WD): {sim_1_3:.2f}")
    print(f"  Slot2 ↔ Slot3 (Dell vs WD): {sim_2_3:.2f}")
    
    print(f"\n  Threshold: 0.6")
    print(f"  1↔2 < 0.6? {sim_1_2 < 0.6} (same brand, different model)")
    print(f"  1↔3 < 0.6? {sim_1_3 < 0.6} (completely different)")


def main():
    """Run all demos."""
    print("\n" + "█"*80)
    print("Dialog State Tracking (DST) - Comprehensive Demo")
    print("█"*80)
    
    demo_basic_dst()
    demo_dialog_manager()
    demo_topic_change_mechanisms()
    demo_slot_operations()
    
    print("\n" + "█"*80)
    print("Demo completed!")
    print("█"*80 + "\n")


if __name__ == "__main__":
    main()
