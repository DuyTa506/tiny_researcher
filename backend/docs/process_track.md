# Process Track - Research Assistant Backend

> **Ongoing work and issues tracking**

---

## Current Status: ✅ Phase 1-2 COMPLETE (v3.0)

**Last Run Results (2026-02-06):**
- **Version:** v3.0 (Phase 1-2)
- Complete 8-phase pipeline implemented
- Redis caching operational
- Memory management with checkpoints
- Selective PDF loading (score >= 8)
- Full report generation working

---

## Completed Features ✅

### Phase 1: Infrastructure ✅

#### 1. Redis Tool Cache Layer ✅
- **File:** `src/tools/cache_manager.py`
- Per-tool TTL configuration (ArXiv: 1h, HF: 30min)
- MD5-based cache key generation
- Hit/miss metrics tracking
- Integrated into PlanExecutor

#### 2. Enhanced Metrics ✅
- **File:** `src/planner/executor.py`
- Cache hit rate calculation
- Average step duration
- Relevance bands (3-5, 6-7, 8-10)
- High-relevance paper count

#### 3. ResearchMemoryManager ✅
- **File:** `src/core/memory_manager.py`
- Hot/Warm/Cold storage layers
- Session lifecycle management
- Phase transition tracking
- Checkpoint/restore functionality
- Analysis context generation

### Phase 2: Complete Pipeline ✅

#### 4. Selective PDF Loading ✅
- **File:** `src/research/analysis/pdf_loader.py`
- Only loads PDFs for score >= 8
- Redis caching (7-day TTL)
- Graceful fallback handling

#### 5. Full Pipeline Integration ✅
- **File:** `src/research/pipeline.py`
- 8-phase workflow:
  1. Planning
  2. Execution (with cache)
  3. Persistence
  4. Analysis
  5. PDF Loading (selective)
  6. Summarization
  7. Clustering
  8. Report Writing
- Memory manager integration
- Automatic checkpointing

#### 6. Services Wired ✅
- SummarizerService - Generate paper summaries
- ClustererService - Group papers by theme
- WriterService - Generate Markdown reports

---

## Features by Component

### PlanExecutor + Deduplication ✅
- Multi-level dedup: arxiv_id → fingerprint → title similarity
- Quality metrics tracking
- **Cache integration**
- **Enhanced progress metrics**

### MongoDB Integration ✅
- Models: Paper, Cluster, Report
- Repositories with async CRUD
- Session tracking

### AnalyzerService ✅
- Batch relevance scoring (abstract-only)
- JSON parsing fixed
- **Relevance band tracking**

### Tool Registry ✅
- `arxiv_search`, `arxiv_search_keywords`
- `hf_trending` (selector may be broken - HF UI changed)
- `collect_url`
- **Redis caching for all tools**

### Memory & Caching ✅
- Tool cache (Redis, per-tool TTL)
- PDF cache (Redis, 7-day TTL)
- Session cache (Redis, 24h TTL)
- Checkpoint storage (Redis, 24h TTL)

---

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| test_research_pipeline.py | ✅ | Legacy test, 99 papers |
| debug_analyzer.py | ✅ | JSON parsing verified |
| test_mongodb.py | ✅ | CRUD operations working |
| **test_phase_1_2.py** | ✅ | **Full 8-phase pipeline** |

---

## Architecture Evolution

### v2.4 (Previous)
```
Planning → Execution → Persistence → Analysis (stopped here)
```

### v3.0 (Current - Phase 1-2)
```
Planning → Execution (cached) → Persistence
    → Analysis → PDF Loading (selective)
    → Summarization → Clustering → Writing

All tracked in ResearchMemoryManager with checkpoints
```

---

## Known Issues

| Issue | Status | Priority | Notes |
|-------|--------|----------|-------|
| HF scraper selector broken | Open | Low | HF UI changed, selector outdated |
| Qdrant shutdown warning | Ignore | Low | Not used in Phase 1-2 |
| pypdf dependency | ⚠️ Warning | Low | Should be `pypdf` not `pypdf2` |

---

## Configuration Files Updated

✅ `.env.example` - Changed from PostgreSQL to MongoDB
✅ `src/core/config.py` - MongoDB settings
✅ `docs/` - All docs updated for v3.0

---

## Test Commands

```bash
# Start services
docker run -d -p 27017:27017 --name mongo mongo:7
docker run -d -p 6379:6379 --name redis redis:7

# Verify services
docker ps

# Run tests
python scripts/test_phase_1_2.py          # Full pipeline (NEW)
python scripts/test_research_pipeline.py  # Legacy test
python scripts/debug_analyzer.py          # Analyzer test
```

---

## Next Steps (Phase 3+)

### Phase 3: Adaptive Planning
- [ ] **QueryParser** - Extract query type and complexity
- [ ] **ResearchQuery** model - Structured query representation
- [ ] **AdaptivePlannerService** - Choose phases based on query type
- [ ] **Phase templates** - Simple vs comprehensive vs url-based

**Files to create:**
- `src/planner/adaptive_planner.py`
- `src/planner/query_parser.py`
- `src/core/schema.py` - Add ResearchQuery

### Phase 4: Conversational Interface
- [ ] **ConversationContext** - Multi-turn state management
- [ ] **IntentClassifier** - Classify user intent
- [ ] **QAEngine** - Answer questions about papers
- [ ] **Refinement handlers** - add_papers, change_focus, deep_dive
- [ ] **State machine** - IDLE → PLANNING → RESEARCHING → INTERACTIVE

**Files to create:**
- `src/conversation/context.py`
- `src/conversation/intent_classifier.py`
- `src/conversation/qa_engine.py`
- `src/conversation/refinement.py`

### Phase 5: Vector Store Integration
- [ ] **Vector embeddings** for all papers
- [ ] **Semantic search** functionality
- [ ] **"Find similar"** feature
- [ ] **Embedding caching**

**Files to update:**
- `src/storage/vector_store.py` - Implement fully
- `src/research/analysis/clusterer.py` - Use vector DB

---

## Performance Metrics (Current)

From `test_phase_1_2.py`:

- **Collection:** ~100 papers in 20-40s (first run), 2-5s (cached)
- **Analysis:** ~99 papers in 15-30s
- **PDF Loading:** ~20 papers (score >= 8) in 5-15s
- **Summarization:** ~25 summaries in 10-20s
- **Clustering:** ~4 clusters in 2-5s
- **Writing:** Report in 1-3s

**Total Pipeline:** 45-90s (first run), 15-30s (cached)

**Cache Hit Rates:**
- First run: 0%
- Second run (same topic): 60-80%
- Repeated queries: 80-95%

---

## Metrics Tracked

### Execution Metrics
- Total papers collected
- Unique papers (after dedup)
- Duplicates removed
- Cache hits / Cache misses
- Cache hit rate
- Average step duration

### Quality Metrics
- Relevant papers (score >= 7)
- High-relevance papers (score >= 8)
- Relevance bands (3-5, 6-7, 8-10)

### Processing Metrics
- Papers with full text loaded
- Papers with summaries
- Clusters created

---

## Dependencies

### Required Services
- MongoDB 7.0+ (port 27017)
- Redis 7.0+ (port 6379)

### Python Packages
- fastapi ^0.109
- motor ^3.3 (MongoDB async)
- redis ^5.0 (with async support)
- sentence-transformers ^2.3
- scikit-learn ^1.4
- pypdf (for PDF parsing)
- openai ^1.10 / google-generativeai ^0.3

---

## Documentation Updated

- ✅ `docs/checklist.md` - v3.0 checklist
- ✅ `docs/dataflow.md` - 8-phase flow
- ✅ `docs/system_design.md` - v3.0 architecture
- ✅ `docs/agent_guide.md` - Updated for Phase 1-2
- ✅ `docs/process_track.md` - This file
- ✅ `docs/phase_1_2_implementation.md` - Complete implementation docs
- ✅ `QUICKSTART.md` - Quick start guide

---

## Last Updated
**2026-02-06 20:00** - Phase 1-2 implementation complete (v3.0)

**Contributors:** Claude Code (Anthropic)
**Status:** ✅ Ready for Phase 3 implementation
