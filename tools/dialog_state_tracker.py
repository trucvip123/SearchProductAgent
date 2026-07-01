"""Dialog State Tracking (DST) để quản lý trạng thái hội thoại nhiều chủ đề sản phẩm.

Kỹ thuật được dùng trong:
- MultiWOZ, DSTC (Dialog State Tracking Challenge)
- Hệ thống quản lý hội thoại nhiều miền (Multi-Domain Dialog Systems)
- Phát hiện topic switch trong conversation

Chức năng:
- Track trạng thái sản phẩm hiện tại
- Phát hiện khi người dùng chuyển sang sản phẩm/chủ đề khác
- Reset state cũ & initialize state mới
- Maintain conversation history cho context
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class TopicChangeReason(Enum):
    """Lý do phát hiện topic change."""
    EXPLICIT_REQUEST = "explicit_request"        # User yêu cầu rõ ràng sản phẩm khác
    ENTITY_MISMATCH = "entity_mismatch"          # Entity khác (brand, model, product_type)
    SEMANTIC_DISTANCE = "semantic_distance"      # Semantic similarity thấp
    DOMAIN_SWITCH = "domain_switch"              # Chuyển sang domain khác (server → storage)
    CLARIFICATION = "clarification"              # Follow-up về sản phẩm hiện tại


@dataclass
class ProductSlot:
    """Một product slot trong dialog state (tương tự MultiWOZ slot)."""
    product_type: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    model: Optional[str] = None
    cpu: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    capacity: Optional[str] = None
    interface: Optional[str] = None
    price_range: Optional[str] = None
    product_link: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, exclude None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_search_query(self) -> str:
        """Convert slot values to search query."""
        tokens = [v for v in self.to_dict().values() if v]
        return " ".join(tokens) if tokens else ""

    def is_empty(self) -> bool:
        """Check if all slots are None."""
        return all(v is None for v in asdict(self).values())

    def similarity_score(self, other: "ProductSlot") -> float:
        """Tính điểm tương đồng với ProductSlot khác (0-1).
        
        Độ tương đồng cao nếu cùng product_type, brand, model.
        """
        if self.is_empty() or other.is_empty():
            return 0.0
        
        matching_fields = 0
        total_fields = 0
        
        # Các field quan trọng để so sánh
        important_fields = ["product_type", "brand", "model"]
        for field_name in important_fields:
            self_val = getattr(self, field_name)
            other_val = getattr(other, field_name)
            if self_val is not None or other_val is not None:
                total_fields += 1
                if self_val and other_val and self_val.lower() == other_val.lower():
                    matching_fields += 1
        
        if total_fields == 0:
            return 0.0
        return matching_fields / total_fields


@dataclass
class DialogTurn:
    """Một lượt hội thoại (user query + system response)."""
    user_query: str
    system_response: Optional[str] = None
    product_slots: ProductSlot = field(default_factory=ProductSlot)
    topic_change_detected: bool = False
    topic_change_reason: Optional[TopicChangeReason] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DialogState:
    """Dialog State tương tự MultiWOZ belief state.
    
    Attributes:
        active_product_slots: ProductSlot hiện tại mà user đang hỏi
        product_history: Lịch sử các sản phẩm đã hỏi trong conversation
        conversation_turns: Toàn bộ lịch sử hội thoại
        turn_count: Số lượt hội thoại
    """
    active_product_slots: ProductSlot = field(default_factory=ProductSlot)
    product_history: List[ProductSlot] = field(default_factory=list)
    conversation_turns: List[DialogTurn] = field(default_factory=list)
    turn_count: int = 0
    last_product_query_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "active_product_slots": self.active_product_slots.to_dict(),
            "product_history": [ps.to_dict() for ps in self.product_history],
            "conversation_turns": [
                {
                    "user_query": t.user_query,
                    "system_response": t.system_response,
                    "product_slots": t.product_slots.to_dict(),
                    "topic_change_detected": t.topic_change_detected,
                    "topic_change_reason": t.topic_change_reason.value if t.topic_change_reason else None,
                    "timestamp": t.timestamp,
                }
                for t in self.conversation_turns
            ],
            "turn_count": self.turn_count,
            "last_product_query_timestamp": self.last_product_query_timestamp,
        }


class DialogStateTracker:
    """Dialog State Tracker cho hệ thống tìm kiếm sản phẩm.
    
    Phát hiện:
    - Topic change (người dùng chuyển sang sản phẩm khác)
    - Clarification (follow-up về sản phẩm hiện tại)
    - Reset state khi cần
    
    Kỹ thuật:
    - Entity-based: So sánh product_type, brand, model
    - Semantic: Có thể mở rộng dùng embeddings
    - Heuristic: Kiểm tra keywords, entity mismatch
    """
    
    def __init__(self, topic_change_threshold: float = 0.5):
        """
        Args:
            topic_change_threshold: Ngưỡng similarity để quyết định topic change.
                                   < threshold → topic changed
        """
        self.state = DialogState()
        self.topic_change_threshold = topic_change_threshold

    def update(
        self,
        user_query: str,
        new_product_slots: ProductSlot,
        system_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cập nhật dialog state với lượt hội thoại mới.
        
        Args:
            user_query: Câu user gõ
            new_product_slots: ProductSlot extracted từ user query
            system_response: Response từ search tool
            
        Returns:
            {
                "topic_changed": bool,
                "change_reason": TopicChangeReason | None,
                "prev_slots": ProductSlot,
                "curr_slots": ProductSlot,
                "action": "reset" | "continue" | "clarify",
            }
        """
        self.state.turn_count += 1
        
        # Phát hiện topic change
        topic_changed, reason = self._detect_topic_change(
            self.state.active_product_slots,
            new_product_slots,
            user_query,
        )
        
        # Determine action
        action = "reset" if topic_changed else ("clarify" if self._is_clarification(user_query) else "continue")
        
        # Update state
        prev_slots = self.state.active_product_slots
        
        if topic_changed:
            # Save previous slots to history
            if not prev_slots.is_empty():
                self.state.product_history.append(prev_slots)
            # Reset to new slots
            self.state.active_product_slots = new_product_slots
        else:
            # Merge new slots with existing (update non-None fields)
            self.state.active_product_slots = self._merge_slots(
                self.state.active_product_slots,
                new_product_slots,
            )
        
        # Record turn
        turn = DialogTurn(
            user_query=user_query,
            system_response=system_response,
            product_slots=self.state.active_product_slots,
            topic_change_detected=topic_changed,
            topic_change_reason=reason,
        )
        self.state.conversation_turns.append(turn)
        self.state.last_product_query_timestamp = datetime.now().isoformat()
        
        return {
            "topic_changed": topic_changed,
            "change_reason": reason.value if reason else None,
            "prev_slots": prev_slots.to_dict(),
            "curr_slots": self.state.active_product_slots.to_dict(),
            "action": action,
            "turn_count": self.state.turn_count,
        }

    def _detect_topic_change(
        self,
        prev_slots: ProductSlot,
        new_slots: ProductSlot,
        user_query: str,
    ) -> tuple[bool, Optional[TopicChangeReason]]:
        """Phát hiện topic change thông qua:
        
        1. Entity-based: Product type, brand, model mismatch
        2. Explicit keywords: "khác", "product", "thay đổi"
        3. Semantic distance: Similarity score
        
        Returns:
            (topic_changed, reason)
        """
        
        # Empty previous state → always new topic
        if prev_slots.is_empty():
            return False, None
        
        # Explicit request detection
        explicit_keywords = ["khác", "sản phẩm khác", "thay đổi", "tìm kiếm khác", "loại khác"]
        for kw in explicit_keywords:
            if kw.lower() in user_query.lower():
                return True, TopicChangeReason.EXPLICIT_REQUEST
        
        # Entity-based mismatch: product_type, brand, model different
        if self._has_entity_mismatch(prev_slots, new_slots):
            return True, TopicChangeReason.ENTITY_MISMATCH
        
        # Semantic similarity check
        similarity = prev_slots.similarity_score(new_slots)
        if similarity < self.topic_change_threshold:
            return True, TopicChangeReason.SEMANTIC_DISTANCE
        
        # No topic change → clarification
        return False, None

    def _has_entity_mismatch(self, prev: ProductSlot, new: ProductSlot) -> bool:
        """Kiểm tra nếu product_type, brand, hoặc model khác nhau.
        
        Nếu user chỉ định new entity mà khác với previous → topic change.
        """
        # Kiểm tra các field "định danh" sản phẩm
        identifier_fields = ["product_type", "brand", "model"]
        
        for field_name in identifier_fields:
            prev_val = getattr(prev, field_name)
            new_val = getattr(new, field_name)
            
            # Nếu new_val được specify và khác prev_val → mismatch
            if new_val is not None:
                if prev_val is not None and new_val.lower() != prev_val.lower():
                    return True
                if prev_val is None and new_val:
                    # New specification của field này → có thể là topic change
                    # Nhưng chỉ nếu khác xa với previous context
                    pass
        
        return False

    def _is_clarification(self, user_query: str) -> bool:
        """Kiểm tra nếu câu hỏi là clarification (follow-up) về sản phẩm hiện tại.
        
        VD: "giá bao nhiêu", "xin link", "còn hàng không", "thông số kỹ thuật"
        """
        clarification_keywords = [
            "giá", "bao nhiêu", "link", "xin", "còn hàng", "tình trạng",
            "thông số", "chi tiết", "cấu hình", "thông tin", "cách",
            "vận chuyển", "bảo hành", "khác", "nào tốt", "so sánh"
        ]
        
        query_lower = user_query.lower()
        return any(kw in query_lower for kw in clarification_keywords)

    def _merge_slots(self, prev: ProductSlot, new: ProductSlot) -> ProductSlot:
        """Merge slots: new values override prev values.
        
        Dùng cho clarification case (update thêm thông tin về sản phẩm hiện tại).
        """
        merged = ProductSlot(
            product_type=new.product_type or prev.product_type,
            brand=new.brand or prev.brand,
            series=new.series or prev.series,
            model=new.model or prev.model,
            cpu=new.cpu or prev.cpu,
            ram=new.ram or prev.ram,
            storage=new.storage or prev.storage,
            capacity=new.capacity or prev.capacity,
            interface=new.interface or prev.interface,
            price_range=new.price_range or prev.price_range,
            product_link=new.product_link or prev.product_link,
        )
        return merged

    def reset(self) -> None:
        """Reset toàn bộ dialog state (new conversation)."""
        self.state = DialogState()

    def get_state_summary(self) -> Dict[str, Any]:
        """Lấy summary của current dialog state."""
        return {
            "turn_count": self.state.turn_count,
            "active_product": self.state.active_product_slots.to_dict(),
            "product_history_count": len(self.state.product_history),
            "last_update": self.state.last_product_query_timestamp,
        }

    def export_state(self) -> str:
        """Export dialog state to JSON string."""
        return json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2)

    def should_reset_for_new_topic(self, user_query: str, new_slots: ProductSlot) -> bool:
        """Quyết định có nên reset state cho topic mới hay không.
        
        Dùng trong main agent loop để biết có cần clear state hay không.
        """
        topic_changed, _ = self._detect_topic_change(
            self.state.active_product_slots,
            new_slots,
            user_query,
        )
        return topic_changed
