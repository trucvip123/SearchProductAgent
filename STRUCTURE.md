# SearchProductAgent - Project Structure Guide

## 📁 Directory Organization

```
SearchProductAgent/
├── src/                          # Main source code
│   ├── __init__.py              # Package initialization
│   ├── agent/                   # LLM Agent orchestration
│   │   └── __init__.py          # Exports: orchestrator_agent, LOCAL_MODEL
│   ├── tools/                   # Agent tools and utilities
│   │   └── __init__.py          # Exports: search_products, SearchProductsArgs
│   ├── models/                  # Data models and schemas
│   │   └── __init__.py          # Exports: ProductMemory, SearchIntent
│   ├── utils/                   # Helper utilities
│   │   └── __init__.py          # Exports: logging, error handling, DB pool, etc.
│   ├── prompts/                 # System prompts (future)
│   └── ui/                      # Web interfaces
│       └── __init__.py
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_agent.py            # Agent tests
│   ├── test_tools.py            # Tool tests
│   └── test_api.py              # API tests
│
├── tools/                        # Legacy tools (backward compatibility)
│   └── normal/                  # Core search and filtering tools
│
├── data/                         # Data files
│   ├── examples.json            # Example data
│   └── knowledge_base/          # Knowledge base storage
│
├── docs/                         # Documentation files
│   ├── rabbit.txt
│   ├── DIALOG_STATE_TRACKING_USAGE.md
│   ├── INTEGRATION_GUIDE.md
│   ├── PRICE_FILTERING_FEATURE.md
│   └── STREAMLIT_UI_GUIDE.md
│
├── logs/                         # Application logs (gitignored)
│   └── .gitkeep
│
├── main.py                       # CLI entry point
├── streamlit_app.py             # Streamlit web UI entry point
├── quickstart.py                # Quick start guide
├── agent.py                     # Core agent (legacy location)
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (gitignored)
├── .env.example                 # Example environment configuration
├── .gitignore                   # Git ignore rules
├── README.md                    # Main documentation
└── docker-compose.yml           # Docker configuration

```

## 🏗️ Module Architecture

### `src/agent/`
**Purpose**: LLM orchestration and routing logic
**Key Exports**:
- `orchestrator_agent`: Main LangGraph agent
- `LOCAL_MODEL`: Model name from environment
- `ORCHESTRATOR_PROMPT`: System prompt for product queries
- `GENERAL_ASSISTANT_PROMPT`: System prompt for general queries

**Responsibilities**:
- Route queries to appropriate agent (product search vs general Q&A)
- Orchestrate ReAct agent for tool calling
- Manage conversation state and messages

### `src/tools/`
**Purpose**: Search tools and product discovery
**Key Exports**:
- `search_products`: Main search tool (async, LangChain @tool)
- `SearchProductsArgs`: Pydantic schema for search parameters
- `ProductMemory`: Structured state for product context
- `SearchIntent`: Normalized search intent

**Responsibilities**:
- Execute hybrid search (Vector + FTS + Keyword)
- Parse and normalize search intents
- Filter products by criteria
- Deduplicate results using RRF (Reciprocal Rank Fusion)

### `src/models/`
**Purpose**: Data models and type definitions
**Key Exports**:
- `ProductMemory`: Product search context (product_type, brand, model, price_range, etc.)
- `SearchIntent`: Parsed and normalized search intent

**Data Classes**:
```python
@dataclass
class ProductMemory:
    product_type: Optional[str]
    brand: Optional[str]
    series: Optional[str]
    model: Optional[str]
    cpu: Optional[str]
    ram: Optional[str]
    storage: Optional[str]
    capacity: Optional[str]
    interface: Optional[str]
    price_range: Optional[str]
    product_link: Optional[str]
```

### `src/utils/`
**Purpose**: Helper utilities and infrastructure
**Key Modules**:
- `_log()`: Structured logging with timestamp
- `_error_json()`: Error response formatting
- `get_db_pool()`: AsyncPG connection pool management
- `normalize_query_with_llm()`: LLM-based query normalization
- `_get_query_embedding()`: Vector embedding generation
- `_parse_price_intent()`: Price range extraction
- `_build_search_intent()`: Intent normalization
- `_rrf_merge()`: Reciprocal Rank Fusion for hybrid search

**Responsibilities**:
- Database connectivity and pooling
- Logging and error handling
- Query normalization and intent extraction
- Price parsing and validation
- Embedding generation
- Result merging and ranking

### `src/ui/`
**Purpose**: Web interface and API endpoints
**Current**: Empty (placeholder for future separation)
**Future Candidates**:
- `streamlit_app.py` → Move from root
- FastAPI routes for API-based access

## 🚀 Entry Points

### `main.py` (CLI)
```bash
python main.py
```
- Console-based interface
- Multi-turn conversation support
- ProductMemory context preservation
- Logging and debug output

### `streamlit_app.py` (Web UI)
```bash
streamlit run streamlit_app.py
```
- Browser-based chat interface
- Session state management
- Async execution with proper event loop handling
- Real-time logging display

### `quickstart.py` (Demo)
```bash
python quickstart.py
```
- Quick testing and demonstration
- Example queries

## 📦 Import Patterns

### Modern (from src/)
```python
from src.agent import orchestrator_agent, LOCAL_MODEL
from src.tools import search_products, ProductMemory
from src.models import SearchIntent
from src.utils import _log, get_db_pool
```

### Legacy (backward compatible)
```python
from agent import orchestrator_agent, LOCAL_MODEL
from tools.normal.tools import search_products, ProductMemory
from tools.normal.models import SearchIntent
from tools.normal.logging_utils import _log
```

Both patterns work! The `src/` modules re-export from the legacy locations for now.

## 🔄 Migration Strategy

The refactoring uses a **gradual migration** approach:

1. **Phase 1** (Current): Create `src/` structure with compatibility re-exports
2. **Phase 2**: Move files incrementally to `src/` with updated imports
3. **Phase 3**: Update entry points (main.py, streamlit_app.py) to use new imports
4. **Phase 4**: Remove legacy `tools/` directory once all imports are updated

**Benefits**:
- ✅ No breaking changes during migration
- ✅ Can test incrementally
- ✅ Easy rollback if needed
- ✅ Parallel development possible

## 📋 Best Practices

### Adding New Modules
1. Create under appropriate `src/` subdirectory
2. Implement the module with clear responsibilities
3. Export via `__init__.py`
4. Add documentation
5. Consider legacy re-export in compatibility layer

### Updating Imports
```python
# ✅ Prefer new paths
from src.tools import search_products
from src.models import ProductMemory

# ⚠️  Legacy paths still work (with deprecation warning in future)
from tools.normal.tools import search_products
from tools.normal.models import ProductMemory
```

### Adding Tests
```python
# Create in tests/ directory
# Example: tests/test_search_tool.py

import pytest
from src.tools import search_products
from src.models import ProductMemory

@pytest.mark.asyncio
async def test_search_products():
    result = await search_products(user_query="laptop")
    assert "products" in result
```

## 🔧 Configuration

### Environment Variables
See `.env.example` for all available options:
- `LOCAL_MODEL`: LLM model name (default: llama3.1:8b)
- `OPENAI_BASE_URL`: LLM endpoint (default: http://localhost:11434/v1)
- `POSTGRES_HOST`: Database host
- `POSTGRES_DB`: Database name
- `EMBEDDING_MODEL`: Embedding model (default: nomic-embed-text)
- `VERBOSE_LOGS`: Enable detailed logging (default: 1)

### Database Configuration
- PostgreSQL with pgvector extension
- Vector embeddings for hybrid search
- Full-text search (FTS)
- Keyword matching

## 📚 Documentation Files

- `README.md` - Main documentation
- `docs/DIALOG_STATE_TRACKING_USAGE.md` - Dialog state management
- `docs/INTEGRATION_GUIDE.md` - Integration patterns
- `docs/PRICE_FILTERING_FEATURE.md` - Price parsing feature
- `docs/STREAMLIT_UI_GUIDE.md` - Streamlit UI guide

## 🐛 Debugging

Enable verbose logging for debugging:
```bash
export VERBOSE_LOGS=1
python main.py
```

Check logs in:
- Console output (CLI)
- Streamlit sidebar (Web UI)
- `logs/` directory (future)

## 🚢 Deployment

### Docker
```bash
docker-compose up
```

### Production
See `docker-compose.yml` for production setup with PostgreSQL, Redis, etc.

---

**Last Updated**: 2026-07-07
**Version**: 1.0 (Beta)
**Status**: ✅ Fully Functional with Modern Structure
