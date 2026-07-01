"""Dialog Manager - Tích hợp Dialog State Tracker vào agent pipeline.

Quản lý:
- Update dialog state trước khi gọi search_products tool
- Phát hiện topic change → reset context
- Log state transitions cho debugging
"""

import json
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

from dialog_state_tracker import (
    DialogStateTracker,
    ProductSlot,
    TopicChangeReason,
)
from normal.tools import ProductMemory


@dataclass
class DialogManagementConfig:
    """Cấu hình Dialog Management."""
    topic_change_threshold: float = 0.6          # Ngưỡng semantic similarity để decide topic change
    enable_state_logging: bool = True             # Log state transitions
    max_conversation_turns: int = 100             # Max turns để track
    verbose: bool = True                          # In detailed logs


class DialogManager:
    """Manages dialog state tracking & topic detection for product search agent."""
    
    def __init__(self, config: Optional[DialogManagementConfig] = None):
        self.config = config or DialogManagementConfig()
        self.tracker = DialogStateTracker(
            topic_change_threshold=self.config.topic_change_threshold
        )
        self.conversation_history: list[Dict[str, Any]] = []
        
    def _log(self, message: str) -> None:
        """Internal logging."""
        if self.config.verbose:
            print(f"[DialogManager] {message}", flush=True)

    def extract_product_slots(self, memory: ProductMemory) -> ProductSlot:
        """Convert ProductMemory → ProductSlot."""
        return ProductSlot(
            product_type=memory.product_type,
            brand=memory.brand,
            series=memory.series,
            model=memory.model,
            cpu=memory.cpu,
            ram=memory.ram,
            storage=memory.storage,
            capacity=memory.capacity,
            interface=memory.interface,
            price_range=memory.price_range,
            product_link=memory.product_link,
        )

    def detect_topic_change(
        self,
        user_query: str,
        product_memory: ProductMemory,
    ) -> Dict[str, Any]:
        """Phát hiện topic change & cập nhật dialog state.
        
        Args:
            user_query: Câu hỏi từ user
            product_memory: Extracted product slots từ LLM
            
        Returns:
            {
                "topic_changed": bool,
                "change_reason": str | None,
                "should_reset_context": bool,
                "active_product": dict,
                "action": "reset" | "continue" | "clarify",
                "dialog_state_summary": dict,
            }
        """
        # Convert memory → slots
        new_slots = self.extract_product_slots(product_memory)
        
        # Update tracker
        state_update = self.tracker.update(
            user_query=user_query,
            new_product_slots=new_slots,
        )
        
        # Decide if should reset LLM context
        should_reset = state_update["topic_changed"]
        
        result = {
            "topic_changed": state_update["topic_changed"],
            "change_reason": state_update["change_reason"],
            "should_reset_context": should_reset,
            "action": state_update["action"],
            "active_product": state_update["curr_slots"],
            "prev_product": state_update["prev_slots"],
            "turn_count": state_update["turn_count"],
            "dialog_state_summary": self.tracker.get_state_summary(),
        }
        
        if self.config.enable_state_logging:
            self._log_state_transition(result)
        
        # Store in history
        self.conversation_history.append({
            "turn": state_update["turn_count"],
            "user_query": user_query,
            **result,
        })
        
        return result

    def _log_state_transition(self, result: Dict[str, Any]) -> None:
        """Log state transition cho debugging."""
        action = result["action"]
        turn = result["turn_count"]
        
        if result["topic_changed"]:
            prev = result["prev_product"]
            curr = result["active_product"]
            prev_str = f"{prev.get('brand', 'N/A')} {prev.get('model', 'N/A')}".strip()
            curr_str = f"{curr.get('brand', 'N/A')} {curr.get('model', 'N/A')}".strip()
            
            self._log(
                f"Turn {turn}: TOPIC CHANGED ({result['change_reason']}) "
                f"| {prev_str or 'NEW'} → {curr_str or 'EMPTY'}"
            )
        else:
            product = result["active_product"]
            product_str = f"{product.get('brand', 'N/A')} {product.get('model', 'N/A')}".strip()
            self._log(f"Turn {turn}: {action.upper()} | Product: {product_str or 'NONE'}")

    def get_context_reset_message(self) -> str:
        """Generate system message để reset LLM context khi topic change."""
        state = self.tracker.get_state_summary()
        product = state["active_product"]
        
        if not product:
            return (
                "Người dùng đã chuyển sang sản phẩm/chủ đề mới. "
                "Quên những thông tin về sản phẩm cũ. "
                "Bây giờ tập trung vào tìm kiếm sản phẩm mới."
            )
        
        product_desc = " ".join(filter(None, [
            product.get("brand"),
            product.get("series"),
            product.get("model"),
        ]))
        
        return (
            f"Người dùng đã chuyển sang sản phẩm khác. "
            f"Bây giờ tập trung vào sản phẩm: {product_desc}. "
            f"Quên những thông tin về sản phẩm cũ."
        )

    def get_product_history(self) -> list[Dict[str, Any]]:
        """Lấy lịch sử các sản phẩm đã hỏi."""
        history = []
        for slot in self.tracker.state.product_history:
            if not slot.is_empty():
                history.append({
                    "product": slot.to_dict(),
                    "query": slot.to_search_query(),
                })
        return history

    def get_current_product(self) -> Optional[Dict[str, Any]]:
        """Lấy sản phẩm hiện tại."""
        active = self.tracker.state.active_product_slots
        if active.is_empty():
            return None
        return active.to_dict()

    def reset_conversation(self) -> None:
        """Reset conversation state (new conversation bắt đầu)."""
        self.tracker.reset()
        self.conversation_history = []
        self._log("Conversation reset")

    def export_conversation(self) -> str:
        """Export toàn bộ conversation state to JSON."""
        export_data = {
            "config": {
                "topic_change_threshold": self.config.topic_change_threshold,
                "max_conversation_turns": self.config.max_conversation_turns,
            },
            "dialog_state": json.loads(self.tracker.export_state()),
            "conversation_history": self.conversation_history,
        }
        return json.dumps(export_data, ensure_ascii=False, indent=2)

    def get_context_for_llm(self) -> Dict[str, Any]:
        """Lấy context để đưa vào LLM system prompt khi topic change."""
        current = self.get_current_product()
        history = self.get_product_history()
        
        return {
            "current_product_context": current or {},
            "previous_products": history,
            "product_history_count": len(history),
            "is_topic_aware": True,
            "message": self.get_context_reset_message() if len(history) > 0 else "",
        }


# ─────────────────────────────────────────────────────────────────────────
# Integration hooks cho agent pipeline
# ─────────────────────────────────────────────────────────────────────────

async def check_and_handle_topic_change(
    dialog_manager: DialogManager,
    user_query: str,
    product_memory: ProductMemory,
    agent_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Check topic change & return guidance cho agent.
    
    Dùng trước khi gọi search_products tool.
    
    Args:
        dialog_manager: DialogManager instance
        user_query: User's current query
        product_memory: Extracted ProductMemory
        agent_context: Current LLM context (để update nếu cần)
        
    Returns:
        {
            "topic_changed": bool,
            "should_clear_context": bool,
            "context_reset_message": str,
            "updated_agent_context": dict,
            "guidance": str,
        }
    """
    # Detect topic change
    result = dialog_manager.detect_topic_change(user_query, product_memory)
    
    updated_context = dict(agent_context)
    guidance = ""
    
    if result["topic_changed"]:
        # Topic change detected → cần reset context
        llm_context = dialog_manager.get_context_for_llm()
        updated_context["product_context"] = llm_context
        guidance = (
            f"Người dùng chuyển từ sản phẩm cũ sang sản phẩm mới "
            f"(lý do: {result['change_reason']}). "
            f"Hãy quên thông tin về sản phẩm cũ và tập trung vào sản phẩm mới."
        )
    else:
        if result["action"] == "clarify":
            guidance = "Người dùng đang yêu cầu thêm thông tin về sản phẩm hiện tại."
        else:
            guidance = "Tiếp tục tìm kiếm sản phẩm hiện tại."
    
    return {
        "topic_changed": result["topic_changed"],
        "should_clear_context": result["should_reset_context"],
        "context_reset_message": dialog_manager.get_context_reset_message(),
        "updated_agent_context": updated_context,
        "guidance": guidance,
        "action": result["action"],
    }
