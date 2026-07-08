"""Query processing utilities for agent interaction."""

import json
import re
from typing import Optional


def extract_current_product(tool_content: str) -> Optional[str]:
    """Trích tên sản phẩm đầu tiên từ JSON kết quả tool."""
    try:
        data = json.loads(tool_content)
        products = data.get("products") or []
        if products:
            return products[0].get("tên") or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def is_topic_change(input_query: str, current_product: Optional[str]) -> bool:
    """Phát hiện topic change dựa trên entity mismatch."""
    if not current_product:
        return False

    brand_keywords = {
        "intel":      ["intel", "xeon", "core i", "pentium", "celeron"],
        "amd":        ["amd", "opteron", "ryzen", "epyc", "athlon"],
        "dell":       ["dell", "poweredge"],
        "hpe":        ["hpe", "proliant", "hewlett"],
        "asus":       ["asus"],
        "lenovo":     ["lenovo", "thinkpad", "thinkcentre"],
        "supermicro": ["supermicro"],
        "wd":         ["western digital", "wd "],
        "seagate":    ["seagate"],
        "synology":   ["synology"],
    }

    query_lower = input_query.lower()
    product_lower = current_product.lower()

    current_brand = None
    for brand, keywords in brand_keywords.items():
        if any(kw in product_lower for kw in keywords):
            current_brand = brand
            break

    query_brand = None
    for brand, keywords in brand_keywords.items():
        if any(kw in query_lower for kw in keywords):
            query_brand = brand
            break

    if current_brand and query_brand and current_brand != query_brand:
        return True

    explicit_change = ["sản phẩm khác", "tìm cái khác", "thay đổi", "loại khác", "cái khác"]
    if any(kw in query_lower for kw in explicit_change):
        return True

    return False


def build_effective_query(input_query: str, current_product: Optional[str]) -> str:
    """Ghép current_product vào đầu query nếu chưa có."""
    if not current_product:
        return input_query
    if current_product.lower() in input_query.lower():
        return input_query
    if is_topic_change(input_query, current_product):
        return input_query
    short = re.sub(r'\b(Model|Product|Series|Type)\b', '', current_product, flags=re.IGNORECASE).strip()
    return f"{short} {input_query}"
