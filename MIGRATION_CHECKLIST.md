# Restructuring Checklist & Migration Guide

## ✅ Phase 1: Complete - Project Structure Refactored

### Deliverables ✅
- [x] Create `src/` directory with proper subdirectories
- [x] Create `tests/` directory for test suite
- [x] Create `data/` and `logs/` directories
- [x] Create `__init__.py` files in all modules
- [x] Create import compatibility layer
- [x] Create comprehensive documentation
- [x] Update README with references
- [x] Verify no breaking changes

### Documentation Created ✅
- [x] STRUCTURE.md - Architecture guide
- [x] REFACTORING.md - Migration guide
- [x] EXAMPLES.md - Usage examples
- [x] PROJECT_STRUCTURE.md - Directory map
- [x] RESTRUCTURING_COMPLETE.md - Summary
- [x] Updated README.md

### Current State ✅
```
✅ New imports available: from src.X import Y
✅ Old imports still work: from tools.normal.X import Y
✅ Both work simultaneously
✅ Zero breaking changes
✅ Ready for production
```

---

## 📋 Phase 2: Gradual File Migration - PLANNED

### What Needs to Be Done
Move actual source files from legacy to new structure while maintaining compatibility

### Files to Migrate (Priority Order)

#### High Priority
- [ ] `tools/normal/models.py` → `src/models/models.py`
  - Status: Data class - safe to move
  - Impact: ProductMemory, SearchIntent
  - Tests: Existing tests in test_*.py
  
- [ ] `tools/normal/search_tool.py` → `src/tools/search.py`
  - Status: Main tool - needs careful migration
  - Impact: search_products tool
  - Dependencies: All utility modules
  - Tests: Integration tests needed

- [ ] `agent.py` → `src/agent/agent.py`
  - Status: Core orchestrator
  - Impact: orchestrator_agent export
  - Dependencies: search_products tool
  - Tests: Agent tests needed

#### Medium Priority
- [ ] `tools/normal/logging_utils.py` → `src/utils/logging.py`
  - Status: Utility - safe to move
  - Dependencies: None (used everywhere)
  - Tests: Simple unit tests

- [ ] `tools/normal/error_utils.py` → `src/utils/errors.py`
  - Status: Utility - safe to move
  - Dependencies: logging_utils
  - Tests: Unit tests

- [ ] `tools/normal/db_pool.py` → `src/utils/database.py`
  - Status: Infrastructure - safe to move
  - Dependencies: logging_utils
  - Tests: Integration tests needed

#### Lower Priority
- [ ] `tools/normal/intent_filters.py` → `src/utils/intent.py`
- [ ] `tools/normal/retrieval.py` → `src/utils/embedding.py`
- [ ] `tools/normal/query_normalizer.py` → `src/utils/normalization.py`

### Migration Checklist Template

For each file:
- [ ] Create target file in new location (e.g., `src/utils/logging.py`)
- [ ] Copy source code from old location
- [ ] Update internal imports to new paths
- [ ] Update `src/X/__init__.py` to import and export
- [ ] Test that old imports still work (via compatibility layer)
- [ ] Test that new imports work
- [ ] Update entry points if needed
- [ ] Update tests if applicable
- [ ] Run full test suite
- [ ] Keep old file as legacy reference
- [ ] Document in REFACTORING.md

### Example Migration: models.py

```python
# Step 1: Create src/models/models.py (copy from tools/normal/models.py)

# Step 2: Update src/models/__init__.py
from .models import ProductMemory, SearchIntent

# Step 3: Keep backward compatibility
# src/tools/__init__.py already imports ProductMemory from tools.normal.tools
# which re-exports from tools.normal.models
# So it should still work

# Step 4: Test
from src.models import ProductMemory  # New way - works
from tools.normal.models import ProductMemory  # Old way - still works
```

---

## 📋 Phase 3: Update Entry Points - PLANNED

### Entry Points to Update

#### main.py
```python
# Old imports
from agent import orchestrator_agent, LOCAL_MODEL
from tools.normal.tools import search_products, ProductMemory

# New imports (after Phase 2)
from src.agent import orchestrator_agent, LOCAL_MODEL
from src.tools import search_products
from src.models import ProductMemory
```

#### streamlit_app.py
```python
# Similar updates to imports
from src.agent import orchestrator_agent, LOCAL_MODEL
from src.tools import search_products
from src.models import ProductMemory
from src.utils import _log
```

### Update Checklist
- [ ] Update all imports in main.py
- [ ] Update all imports in streamlit_app.py
- [ ] Update all imports in quickstart.py
- [ ] Test CLI: `python main.py`
- [ ] Test Web UI: `streamlit run streamlit_app.py`
- [ ] Test quickstart: `python quickstart.py`

---

## 📋 Phase 4: Create Tests - PLANNED

### Test Structure to Create

```
tests/
├── __init__.py
├── test_models.py           # Test ProductMemory, SearchIntent
├── test_search_tool.py      # Test search_products
├── test_agent.py            # Test orchestrator_agent
├── test_utilities.py        # Test utility functions
└── test_integration.py      # Test full workflows
```

### Test Checklist
- [ ] Create test files for each module
- [ ] Write unit tests for utilities
- [ ] Write integration tests for search pipeline
- [ ] Write tests for agent routing
- [ ] Add pytest configuration (pytest.ini)
- [ ] Add test requirements (pytest, pytest-asyncio, etc.)
- [ ] Run: `pytest tests/`
- [ ] Add test CI/CD pipeline

---

## 📋 Phase 5: Cleanup - PLANNED

### After Full Migration

- [ ] Review all legacy code in `tools/normal/`
- [ ] Verify all imports updated to use `src/`
- [ ] Archive old `tools/normal/` as backup
- [ ] Remove old imports from all files
- [ ] Update documentation to remove migration notes
- [ ] Final test suite run
- [ ] Commit with cleanup message

---

## 🔍 Verification Checklist

### After Each Phase

#### Phase 2: File Migration
- [ ] No import errors: `python -m py_compile src/**/*.py`
- [ ] Old imports work: `python -c "from tools.normal.tools import search_products"`
- [ ] New imports work: `python -c "from src.tools import search_products"`
- [ ] Existing tests pass: `pytest tests/` or `python test_*.py`

#### Phase 3: Entry Points
- [ ] CLI runs: `python main.py`
  - [ ] Can accept queries
  - [ ] Can exit gracefully (Ctrl+C)
- [ ] Web UI runs: `streamlit run streamlit_app.py`
  - [ ] Loads at http://localhost:8501
  - [ ] Can submit queries
  - [ ] Shows responses
- [ ] Quickstart runs: `python quickstart.py`

#### Phase 4: Tests
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Coverage acceptable: `pytest --cov=src tests/`
- [ ] No import warnings

#### Phase 5: Cleanup
- [ ] No broken imports
- [ ] Documentation updated
- [ ] README reflects new structure
- [ ] All CI/CD checks pass

---

## 📊 Migration Timeline (Recommended)

**Phase 1**: ✅ Complete (Week of July 7, 2026)
- Create structure
- Create documentation
- No code changes

**Phase 2**: 📋 Next (Week of July 14)
- Migrate files incrementally
- Test after each migration
- Maintain compatibility
- Estimated: 3-5 days

**Phase 3**: 📋 Follow-up (Week of July 21)
- Update entry points
- Test all interfaces
- Estimated: 1 day

**Phase 4**: 📋 Concurrent
- Create tests while migrating
- Can run in parallel with Phase 2-3
- Estimated: Ongoing

**Phase 5**: 📋 Final (End of July)
- Cleanup and final verification
- Update CI/CD pipelines
- Estimated: 1 day

---

## 👥 Responsibility Assignment

### Project Lead
- [ ] Review structure design
- [ ] Approve migration plan
- [ ] Manage timeline

### Backend Developer(s)
- [ ] Execute Phase 2 migrations
- [ ] Write integration tests
- [ ] Update documentation

### QA/Testing
- [ ] Execute Phase 4 tests
- [ ] Verify Phase 3 entry points
- [ ] Run final verification

### DevOps/CI-CD
- [ ] Update CI/CD pipelines in Phase 5
- [ ] Monitor migrations
- [ ] Ensure no service downtime

---

## 📞 Support & Questions

### If You Encounter Issues

1. **Import Error?**
   - Check `src/X/__init__.py` exports
   - Check import compatibility layer
   - See EXAMPLES.md

2. **Test Failure?**
   - Verify both old and new paths work
   - Check for circular imports
   - See REFACTORING.md

3. **Structure Question?**
   - Read STRUCTURE.md
   - Check PROJECT_STRUCTURE.md
   - Review src/__init__.py files

---

## ✨ Success Criteria

Phase completion signoff:

- [ ] All code builds without errors
- [ ] All tests pass (>95% coverage)
- [ ] No breaking changes to users
- [ ] Documentation is complete
- [ ] Performance is unchanged
- [ ] All team members trained
- [ ] Production tested

---

## 📝 Notes

- Document any blockers or issues encountered
- Update this checklist as you go
- Share learnings with team
- Keep REFACTORING.md updated
- Communicate timeline changes early

---

**Last Updated**: July 7, 2026
**Phase**: 1 (Complete), Preparing Phase 2
**Status**: On Track
**Next Milestone**: Phase 2 - Gradual File Migration
