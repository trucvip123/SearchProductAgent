"""
Example Usage Guide - SearchProductAgent New Structure

This file demonstrates how to use the refactored SearchProductAgent
with the new modern project structure.
"""

# ============================================================================
# Example 1: Import the Agent
# ============================================================================

from src.agent import orchestrator_agent, LOCAL_MODEL

print(f"Using model: {LOCAL_MODEL}")

# ============================================================================
# Example 2: Import Data Models
# ============================================================================

from src.models import ProductMemory, SearchIntent

# Create a product memory instance
memory = ProductMemory(
    product_type="laptop",
    brand="Dell",
    price_range="dưới 20 triệu"
)

print(f"Product Memory: {memory.to_log_dict()}")

# ============================================================================
# Example 3: Import Search Tool
# ============================================================================

from src.tools import search_products, SearchProductsArgs

# The search_products tool is ready for use with the orchestrator_agent

# ============================================================================
# Example 4: Import Utilities
# ============================================================================

from src.utils import (
    _log,
    get_db_pool,
    _get_query_embedding,
    _normalize_user_query,
    _parse_price_intent,
)

# Log a message
_log("EXAMPLE", "Starting SearchProductAgent demonstration")

# Normalize a user query
normalized = _normalize_user_query("giaa laptop dell duoi 20 trieuuu")
print(f"Normalized query: {normalized}")

# Parse price intent
min_price, max_price = _parse_price_intent("dưới 20 triệu")
print(f"Price range: {min_price} - {max_price}")

# ============================================================================
# Example 5: Using with LangChain
# ============================================================================

import asyncio
from langchain_core.messages import HumanMessage

async def example_agent_call():
    """Example of calling the agent with a query."""
    query = "Tìm laptop dell dưới 15 triệu"
    
    # Create the input message
    messages = [HumanMessage(content=query)]
    
    # Invoke the orchestrator agent
    result = await orchestrator_agent.ainvoke({
        "messages": messages,
        "route": ""  # Will be set by router node
    })
    
    print(f"Agent response: {result}")

# Uncomment to run (requires async context):
# asyncio.run(example_agent_call())

# ============================================================================
# Example 6: Import Style Comparison
# ============================================================================

# NEW STYLE (PREFERRED) - Clear and modern
from src.agent import orchestrator_agent
from src.tools import search_products, ProductMemory
from src.models import SearchIntent
from src.utils import _log, get_db_pool

# OLD STYLE (STILL WORKS during migration) - Backward compatible
from agent import orchestrator_agent as orch_agent
from tools.normal.tools import search_products as search_tool
from tools.normal.models import ProductMemory as ProdMemory
from tools.normal.logging_utils import _log as log_fn

# Both work! But prefer the new style in new code.

# ============================================================================
# Example 7: Working with the Streamlit App
# ============================================================================

# If you want to add features to streamlit_app.py, use new imports:

# In streamlit_app.py:
# from src.agent import orchestrator_agent
# from src.tools import search_products, ProductMemory
# from src.models import SearchIntent
# from src.utils import _log

# ============================================================================
# Example 8: Adding Tests
# ============================================================================

# Create tests/test_search_tools.py with:

"""
import pytest
from src.tools import search_products, SearchProductsArgs
from src.models import ProductMemory

@pytest.mark.asyncio
async def test_search_products():
    result = await search_products(
        user_query="laptop",
        max_results=5
    )
    assert isinstance(result, str)
    # More assertions...
"""

# ============================================================================
# Example 9: Adding New Tools
# ============================================================================

# To add a new tool:
# 1. Create src/tools/new_tool.py
# 2. Implement your tool
# 3. Export it in src/tools/__init__.py:
#    from .new_tool import my_new_tool
#    __all__ = [..., "my_new_tool"]
# 4. Use it:
#    from src.tools import my_new_tool

# ============================================================================
# Example 10: Adding New Utilities
# ============================================================================

# To add a new utility:
# 1. Create src/utils/new_utility.py
# 2. Implement your utility
# 3. Export it in src/utils/__init__.py
# 4. Use it:
#    from src.utils import my_new_util

# ============================================================================
# Summary
# ============================================================================

"""
KEY POINTS:
1. ✅ Use new imports: from src.X import Y
2. ✅ Old imports still work during migration
3. ✅ Add new code under src/ with proper __init__.py exports
4. ✅ Create tests in tests/ directory
5. ✅ Keep entry points (main.py, streamlit_app.py) at root

STRUCTURE:
- src/agent/      → LLM orchestration logic
- src/tools/      → Search tools and tool definitions
- src/models/     → Data models and schemas
- src/utils/      → Helper functions and utilities
- src/ui/         → Web interfaces (future)
- src/prompts/    → System prompts (future)

ENTRY POINTS:
- main.py              → CLI application
- streamlit_app.py     → Web UI application
- quickstart.py        → Quick start demo

For more info, see STRUCTURE.md and REFACTORING.md
"""
