# Project Refactoring Guide

## 📚 Overview

The SearchProductAgent project has been refactored to follow **Python best practices** for project organization. The new structure improves:

- ✅ Code organization and maintainability
- ✅ Import clarity and modularity
- ✅ Scalability for future features
- ✅ Testing and documentation
- ✅ Team collaboration

## 🔄 What Changed

### Old Structure (Legacy)
```
project/
├── agent.py              # At root level
├── main.py              # At root level
├── streamlit_app.py     # At root level
└── tools/
    └── normal/          # All utilities mixed together
        ├── tools.py
        ├── models.py
        ├── search_tool.py
        ├── intent_filters.py
        ├── logging_utils.py
        └── ...
```

### New Structure (Modern)
```
project/
├── src/                 # Clear separation of concerns
│   ├── agent/          # Agent logic
│   ├── tools/          # Tools & search
│   ├── models/         # Data models
│   ├── utils/          # Helper functions
│   └── ui/             # Web interfaces
├── tests/              # Test suite
├── docs/               # Documentation
├── main.py            # CLI entry point
└── streamlit_app.py   # Web UI entry point
```

## 🚀 Migration Phases

### Phase 1: ✅ COMPLETE - Create New Structure
- ✅ Created `src/` directory with proper subdirectories
- ✅ Created compatibility layer in `src/__init__.py` files
- ✅ Created migration guide and documentation
- ✅ Created tests directory
- ✅ Created logs directory

### Phase 2: 🔄 IN PROGRESS - Gradual File Migration
- Files are being moved from legacy locations to `src/` subdirectories
- Both old and new import paths work (no breaking changes)
- Can test incrementally

### Phase 3: 📋 PLANNED - Update Entry Points
- Update `main.py` to use new imports
- Update `streamlit_app.py` to use new imports
- Update test files to use new imports

### Phase 4: 📋 PLANNED - Cleanup
- Remove legacy files once fully migrated
- Update CI/CD pipelines if applicable

## 📦 Import Compatibility

### During Migration (Works Now!)

Both import styles work simultaneously:

```python
# New style - PREFERRED
from src.agent import orchestrator_agent
from src.tools import search_products
from src.models import ProductMemory
from src.utils import _log

# Old style - STILL WORKS
from agent import orchestrator_agent
from tools.normal.tools import search_products
from tools.normal.models import ProductMemory
from tools.normal.logging_utils import _log
```

### After Migration (Target State)

Only new imports in codebase:
```python
from src.agent import orchestrator_agent
from src.tools import search_products
from src.models import ProductMemory
from src.utils import _log
```

## 🎯 Benefits

### Code Organization
- **Clear separation of concerns**: Each module has a single responsibility
- **Intuitive structure**: Easy to find code by purpose (agent, tools, models, utils)
- **Reduced coupling**: Imports follow logical dependency chains

### Development Experience
```python
# ✅ Clear what you're importing
from src.agent import orchestrator_agent  # I'm using the agent
from src.tools import search_products      # I'm using search tool
from src.models import ProductMemory       # I'm using data model

# ❌ Unclear structure
from tools.normal.tools import search_products  # Where's the orchestrator?
from agent import orchestrator_agent           # Where's the model?
```

### Maintainability
- ✅ Adding new tools: Create file in `src/tools/`, export in `__init__.py`
- ✅ Adding new utilities: Create file in `src/utils/`, export in `__init__.py`
- ✅ Adding new UI: Create in `src/ui/` and main script at root
- ✅ Adding tests: Create in `tests/` with mirrored structure

### Scalability
Easy to add new features:
- New agent type? → Add to `src/agent/`
- New tool? → Add to `src/tools/`
- New data model? → Add to `src/models/`
- New utility? → Add to `src/utils/`

## 🔍 Quick Migration Checklist

For developers working on this project:

### When Updating Code:
- [ ] Use `from src.X import Y` instead of old paths
- [ ] Check `src/__init__.py` files to see what's exported
- [ ] If adding new files, create under appropriate `src/` subdirectory
- [ ] Update docstrings and comments if needed

### When Creating Tests:
- [ ] Create test files in `tests/` directory
- [ ] Mirror the structure of `src/` in test names
- [ ] Example: `src/tools/search.py` → `tests/test_search_tools.py`

### When Adding Documentation:
- [ ] Update relevant `.md` files in `docs/`
- [ ] Refer to section in `STRUCTURE.md` for architecture details

## 📋 Reference: Old to New Path Mapping

| Purpose | Old Path | New Path | Exported By |
|---------|----------|----------|-------------|
| Main Agent | `agent.py` | `src/agent/__init__.py` | `src/agent` |
| Search Tool | `tools/normal/search_tool.py` | `src/tools/__init__.py` | `src.tools` |
| Data Models | `tools/normal/models.py` | `src/models/__init__.py` | `src.models` |
| Logging | `tools/normal/logging_utils.py` | `src/utils/__init__.py` | `src.utils` |
| Error Handler | `tools/normal/error_utils.py` | `src/utils/__init__.py` | `src.utils` |
| DB Pool | `tools/normal/db_pool.py` | `src/utils/__init__.py` | `src.utils` |
| Query Norm | `tools/normal/query_normalizer.py` | `src/utils/__init__.py` | `src.utils` |
| Embedding | `tools/normal/retrieval.py` | `src/utils/__init__.py` | `src.utils` |
| Intent Parse | `tools/normal/intent_filters.py` | `src/utils/__init__.py` | `src.utils` |

## 🐛 Troubleshooting

### Import Error: "No module named 'src'"
**Solution**: Make sure you're running from the project root directory:
```bash
cd d:\AI\Agent\SearchProductAgent
python main.py  # or streamlit run streamlit_app.py
```

### "ModuleNotFoundError: No module named 'tools.normal'"
**Solution**: The legacy path still exists. Check that you're using the correct import:
```python
# Try new import first
from src.tools import search_products

# Or fallback to old import (still works for now)
from tools.normal.tools import search_products
```

### Tests not finding modules
**Solution**: Make sure tests are run from project root:
```bash
pytest tests/
# not
cd tests && pytest
```

## 📞 Questions?

Refer to:
1. `STRUCTURE.md` - Detailed architecture guide
2. `src/__init__.py` - See what's exported from each module
3. Code comments and docstrings in each module
4. Existing tests as examples

## ✨ Next Steps

1. **Use new imports**: When modifying code, prefer `from src.X import Y`
2. **Add tests**: Create new tests in `tests/` for new features
3. **Document**: Update docstrings and STRUCTURE.md as needed
4. **Review**: During code review, ensure import paths follow new structure

---

**Refactoring initiated**: July 7, 2026
**Status**: Phase 1 Complete, Phase 2 In Progress
**Backward Compatibility**: ✅ Fully Maintained
