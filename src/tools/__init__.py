"""Tools module - Search and product discovery tools."""

# Re-export from old location for now (compatibility)
from tools.normal.tools import (
    search_products,
    SearchProductsArgs,
    ProductMemory,
    SearchIntent,
)

__all__ = [
    "search_products",
    "SearchProductsArgs",
    "ProductMemory",
    "SearchIntent",
]
