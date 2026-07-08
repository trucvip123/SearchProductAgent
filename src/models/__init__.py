"""Data models for ProductMemory and SearchIntent."""

from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Dict, Any


@dataclass
class ProductMemory:
    """Structured memory for one product search turn."""

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

    def to_search_tokens(self) -> List[str]:
        tokens = []
        for f in fields(self):
            val = getattr(self, f.name)
            if val and isinstance(val, str) and val.strip():
                tokens.append(val.strip())
        return tokens

    def to_log_dict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class SearchIntent:
    """Normalized intent extracted from query and structured memory."""

    product_type: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    model: Optional[str] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    price_text: Optional[str] = None

    def to_log_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
