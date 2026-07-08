# SearchProductAgent Project Structure - Final Overview

## 📁 Complete Directory Tree

```
SearchProductAgent/
│
├── 📁 src/                              # Modern Source Code
│   ├── __init__.py                      # Package root
│   ├── 📁 agent/
│   │   └── __init__.py                  # Exports orchestrator_agent, LOCAL_MODEL
│   ├── 📁 tools/
│   │   └── __init__.py                  # Exports search_products, SearchProductsArgs
│   ├── 📁 models/
│   │   └── __init__.py                  # Exports ProductMemory, SearchIntent
│   ├── 📁 utils/
│   │   └── __init__.py                  # Exports all utilities
│   ├── 📁 prompts/
│   │   └── __init__.py                  # Placeholder for prompt management
│   └── 📁 ui/
│       └── __init__.py                  # Placeholder for UI apps
│
├── 📁 tests/                            # Test Suite
│   └── __init__.py
│
├── 📁 tools/                            # Legacy Tools (Backward Compatible)
│   ├── __dst_init__.py
│   ├── dialog_manager.py
│   ├── dialog_state_tracker.py
│   ├── test_dialog_state_tracking.py
│   ├── 📁 normal/
│   │   ├── __pycache__/
│   │   ├── db_pool.py
│   │   ├── error_utils.py
│   │   ├── intent_filters.py
│   │   ├── logging_utils.py
│   │   ├── models.py
│   │   ├── query_normalizer.py
│   │   ├── retrieval.py
│   │   ├── search_tool.py
│   │   └── tools.py
│   └── DIALOG_STATE_TRACKING_USAGE.md
│
├── 📁 docs/                             # Documentation Files
│   ├── rabbit.txt
│   ├── DIALOG_STATE_TRACKING_USAGE.md
│   ├── DST_README.md
│   ├── INTEGRATION_GUIDE.md
│   ├── README.md
│   └── .gitkeep
│
├── 📁 data/                             # Data Files
│   ├── 📁 knowledge_base/
│   │   └── .gitkeep
│   └── examples.json (optional)
│
├── 📁 logs/                             # Application Logs (gitignored)
│   └── .gitkeep
│
├── 📁 .git/                             # Git Repository
├── 📁 .venv/                            # Python Virtual Environment
├── 📁 __pycache__/                      # Python Cache
│
├── 🐍 agent.py                          # Legacy Agent (root level)
├── 🐍 main.py                           # CLI Entry Point
├── 🐍 streamlit_app.py                  # Web UI Entry Point
├── 🐍 quickstart.py                     # Quick Start Demo
│
├── 📄 .env                              # Environment Config (gitignored)
├── 📄 .env.example                      # Example Environment Config
├── 📄 .gitignore                        # Git Ignore Rules
├── 📄 requirements.txt                  # Python Dependencies
├── 📄 README.md                         # Main Documentation
├── 📄 STRUCTURE.md                      # Detailed Structure Guide
├── 📄 REFACTORING.md                    # Refactoring Guide
├── 📄 EXAMPLES.md                       # Usage Examples
├── 📄 PROJECT_STRUCTURE.md              # This File
│
├── 📄 PRICE_FILTERING_FEATURE.md        # Feature Documentation
├── 📄 STREAMLIT_UI_GUIDE.md             # UI Guide
├── 🐳 docker-compose.yml                # Docker Configuration
│
├── 🧪 test_dedup_and_filter.py          # Legacy Test
└── 🧪 test_price_filter.py              # Legacy Test
```

## 📊 Module Organization

### src/agent/ - Agent Orchestration
```
Responsibilities:
- Route queries to appropriate handler
- Manage conversation state
- Coordinate ReAct agent for tool calling
- Define system prompts

Exports:
- orchestrator_agent: Main LangGraph compilation
- LOCAL_MODEL: Model name from env
- OrchestratorState: State class
- ORCHESTRATOR_PROMPT: Product search prompt
- GENERAL_ASSISTANT_PROMPT: General Q&A prompt
```

### src/tools/ - Search & Discovery
```
Responsibilities:
- Execute hybrid search (Vector + FTS + Keyword)
- Define tool schema (SearchProductsArgs)
- Coordinate search components

Exports:
- search_products: Main tool (async)
- SearchProductsArgs: Pydantic schema
- ProductMemory: Structured state
- SearchIntent: Parsed intent
```

### src/models/ - Data Models
```
Responsibilities:
- Define data structures
- Provide conversion/serialization methods

Exports:
- ProductMemory: Product context dataclass
- SearchIntent: Search intent dataclass
```

### src/utils/ - Utilities & Helpers
```
Responsibilities:
- Logging and error handling
- Database connectivity
- Query normalization
- Intent parsing
- Embedding generation
- Result merging

Exports:
- _log(): Structured logging
- _error_json(): Error formatting
- get_db_pool(): DB connection pool
- normalize_query_with_llm(): LLM normalization
- _get_query_embedding(): Vector embedding
- _parse_price_intent(): Price parsing
- And 15+ more utilities
```

### src/prompts/ - Prompt Management
```
Status: Placeholder for future consolidation
Purpose: Centralize all system prompts

Planned:
- Extract prompts from agent module
- Create template system
- Enable prompt versioning
```

### src/ui/ - Web Interfaces
```
Status: Placeholder for future organization
Purpose: Separate UI implementations

Future:
- Move streamlit_app.py components
- Separate state management
- Extract reusable widgets
```

## 🔄 Import Patterns

### Modern Style (Recommended)
```python
from src.agent import orchestrator_agent, LOCAL_MODEL
from src.tools import search_products, SearchProductsArgs
from src.models import ProductMemory, SearchIntent
from src.utils import _log, get_db_pool, _parse_price_intent
```

### Legacy Style (Still Works)
```python
from agent import orchestrator_agent, LOCAL_MODEL
from tools.normal.tools import search_products, SearchProductsArgs, ProductMemory
from tools.normal.models import SearchIntent
from tools.normal.logging_utils import _log
from tools.normal.db_pool import get_db_pool
```

## 📚 Documentation Map

| Document | Purpose |
|----------|---------|
| `README.md` | Main project README with setup and usage |
| `STRUCTURE.md` | Detailed architecture and module guide |
| `REFACTORING.md` | Migration guide and phases |
| `EXAMPLES.md` | Code examples and usage patterns |
| `PROJECT_STRUCTURE.md` | This file - visual directory map |
| `PRICE_FILTERING_FEATURE.md` | Price parsing implementation |
| `STREAMLIT_UI_GUIDE.md` | Web UI features and usage |
| `INTEGRATION_GUIDE.md` | Dialog state tracking integration |

## 🎯 Best Practices

1. **New Code**: Use `from src.X import Y` imports
2. **Tests**: Create in `tests/` with mirrored module names
3. **Documentation**: Update relevant `.md` files
4. **Exports**: Always export public APIs via `__init__.py`
5. **Backward Compatibility**: Old imports continue to work during migration

## ✨ Features by Module

### Agent Module
- ✅ Multi-turn conversation support
- ✅ Query routing (product vs. general)
- ✅ ReAct tool calling
- ✅ State management
- ✅ Streaming support

### Tools Module
- ✅ Hybrid search (Vector + FTS + Keyword)
- ✅ RRF result merging
- ✅ Product deduplication
- ✅ Schema validation
- ✅ Async execution
- ✅ Connection pooling

### Models Module
- ✅ ProductMemory dataclass
- ✅ SearchIntent dataclass
- ✅ Serialization methods
- ✅ Type safety with dataclasses

### Utils Module
- ✅ Structured logging
- ✅ Error handling
- ✅ DB pool management
- ✅ Query normalization (rule-based + LLM)
- ✅ Price intent extraction
- ✅ Embedding generation
- ✅ Intent parsing
- ✅ Product filtering

## 🚀 Getting Started

### Run CLI
```bash
python main.py
```

### Run Web UI
```bash
streamlit run streamlit_app.py
```

### Run Tests
```bash
pytest tests/
```

### Explore Imports
See `EXAMPLES.md` for detailed import examples

---

**Refactored**: July 7, 2026
**Status**: ✅ Complete - Phase 1
**Backward Compatibility**: ✅ Fully Maintained
**Ready for**: Phase 2 - File Migration
