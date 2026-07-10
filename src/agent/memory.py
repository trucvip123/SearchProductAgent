"""ProductMemory manager — cross-turn conversation state and context injection.

This is the canonical implementation. product_memory.py (root) is a backward-compatible shim.
"""

import json
from dataclasses import asdict
from typing import Optional

from langchain_core.messages import SystemMessage

from ..models import ProductMemory


class ProductMemoryManager:
    """Manage ProductMemory across conversation turns.

    Features:
    - Save ProductMemory from previous turn
    - Merge new ProductMemory with previous (preserve None fields)
    - Generate system context for LLM to merge/preserve fields
    """

    _MEMORY_FIELDS = [
        "product_type", "brand", "series", "model", "cpu",
        "ram", "storage", "capacity", "interface", "price_range", "product_link",
    ]

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.previous_memory: Optional[ProductMemory] = None
        self.current_memory: Optional[ProductMemory] = None

    def update_with_previous(self, search_result: str) -> None:
        """Extract ProductMemory from search results and save as previous."""
        try:
            data = json.loads(search_result)
            products = data.get("products") or []
            if products and products[0]:
                if self.verbose:
                    pass
        except (json.JSONDecodeError, TypeError):
            pass

    def merge_memory(self, new_memory: Optional[ProductMemory | dict]) -> ProductMemory:
        """Merge new ProductMemory with previous, preserving None fields.

        Rules:
        - Non-None fields from new_memory → override
        - None fields from new_memory → preserve from previous_memory
        """
        if new_memory is None:
            new_memory = ProductMemory()

        if isinstance(new_memory, dict):
            new_memory = ProductMemory(**{
                k: v for k, v in new_memory.items() if k in self._MEMORY_FIELDS
            })

        if not self.previous_memory:
            self.current_memory = new_memory
            return new_memory

        merged_dict = {}
        for field in self._MEMORY_FIELDS:
            new_val = getattr(new_memory, field, None)
            prev_val = getattr(self.previous_memory, field, None)
            merged_dict[field] = new_val if new_val is not None else prev_val

        merged = ProductMemory(**merged_dict)
        self.current_memory = merged
        return merged

    def persist_current(self) -> None:
        """Save current_memory as previous for next turn."""
        if self.current_memory:
            self.previous_memory = self.current_memory

    def reset(self) -> None:
        """Reset all memory."""
        self.previous_memory = None
        self.current_memory = None

    def get_context_message(self) -> Optional[SystemMessage]:
        """Generate system message to remind LLM about previous ProductMemory."""
        if not self.previous_memory:
            return None

        prev_dict = {k: v for k, v in asdict(self.previous_memory).items() if v}
        if not prev_dict:
            return None

        prev_fields = ", ".join([f"{k}='{v}'" for k, v in prev_dict.items()])
        context = (
            "Lưu ý về lượt hội thoại trước:\n"
            f"Thông tin sản phẩm từ lượt trước: {prev_fields}\n\n"
            "Khi extract ProductMemory cho lượt này:\n"
            "- Nếu user không đề cập rõ ràng thay đổi 1 field → hãy GIỮ NGUYÊN giá trị cũ\n"
            "- Chỉ THAY ĐỔI khi user rõ ràng mention (ví dụ: \"thay đổi sang\", \"khác hãng\", \"giá khác\", etc.)\n"
            "- Điều này để đảm bảo context được preserve qua các lượt hội thoại."
        )
        return SystemMessage(content=context)
