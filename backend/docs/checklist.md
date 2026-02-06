# Backend Checklist

## Phase 1: Foundation ✅
- [x] Project structure (poetry)
- [x] Environment config (.env, config.py)
- [x] Docker compose (MongoDB, Redis)

## Phase 2: Storage ✅
- [x] MongoDB connection (motor async)
- [x] Pydantic models: Paper, Cluster, Report
- [x] Repositories: PaperRepository, ClusterRepository

## Phase 3: Tool Registry ✅
- [x] `@register_tool` decorator
- [x] OpenAI function schema generator
- [x] Built-in tools: arxiv_search, hf_trending, collect_url
- [x] **Redis tool cache layer with TTL**

## Phase 4: Planner ✅
- [x] PlannerService - generates tool-based plans
- [x] PlanStore - in-memory status tracking
- [x] PlanExecutor - executes tools with deduplication
- [x] **Cache manager integration**
- [x] **Enhanced metrics (cache hit rate, avg duration)**

## Phase 5: Analysis Pipeline ✅
- [x] AnalyzerService - batch relevance scoring
- [x] Multi-level deduplication (arxiv_id, fingerprint, title)
- [x] MongoDB persistence integration
- [x] JSON parsing fix for LLM responses
- [x] **Relevance band tracking (3-5, 6-7, 8-10)**

## Phase 6: Content Processing ✅
- [x] **PDFLoaderService - selective full text loading (score >= 8)**
- [x] **SummarizerService - generate paper summaries**
- [x] **ClustererService - group by theme**
- [x] **WriterService - generate final report**

## Phase 7: Memory Management ✅
- [x] **ResearchMemoryManager - hot/warm/cold layers**
- [x] **Session tracking with phase transitions**
- [x] **Checkpoint/restore functionality**
- [x] **Analysis context generation**

## Phase 8: API Layer ⏳
- [x] FastAPI setup
- [x] Plan CRUD endpoints
- [ ] **Pipeline execution endpoint (with session tracking)**
- [ ] **Report retrieval endpoint**
- [ ] **Session management endpoints**

---

## Architecture (Current v3.0 - Phase 1-2)

```
User Input → PlannerService → ResearchPlan
                                   ↓
                         PlanExecutor (with cache)
                                   ↓
          ┌────────────────────────┴────────────────────┐
          ↓                                             ↓
    Tool Registry                             PaperDeduplicator
    (cached results)                                    ↓
          ↓                                      Unique Papers
    ArxivSearcher ────────────────────►              ↓
                                           ResearchMemoryManager
                                          (session tracking)
                                                      ↓
                                           MongoDB (papers)
                                                      ↓
                                          ┌──── AnalyzerService ✅
                                          │    (batch scoring)
                                          ↓
                                   Papers with scores
                                          ↓
                                   PDFLoaderService ✅
                                   (score >= 8 only)
                                          ↓
                                   SummarizerService ✅
                                          ↓
                                   ClustererService ✅
                                          ↓
                                   WriterService ✅
                                          ↓
                                   Final Report (Markdown)
```

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| test_research_pipeline.py | ✅ | 99 papers, scores 3-9 |
| debug_analyzer.py | ✅ | JSON parsing fixed |
| test_mongodb.py | ✅ | CRUD working |
| **test_phase_1_2.py** | ✅ | **Full 8-phase pipeline** |

## Pipeline Phases (v3.0)

1. **Planning** - LLM generates research plan
2. **Execution** - Collect papers (with Redis cache)
3. **Persistence** - Save to MongoDB
4. **Analysis** - Score relevance (abstract-only)
5. **PDF Loading** - Load full text for score >= 8
6. **Summarization** - Generate structured summaries
7. **Clustering** - Group papers by theme
8. **Writing** - Generate final Markdown report

## Metrics Tracked

- Total papers collected
- Unique papers (after dedup)
- Duplicates removed
- Relevant papers (score >= 7)
- High-relevance papers (score >= 8)
- Papers with full text loaded
- Papers with summaries
- Clusters created
- **Cache hit rate**
- **Average step duration**
- **Relevance distribution (3-5, 6-7, 8-10)**

---

## Next Steps (Phase 3+)

### Phase 3: Adaptive Planning
- [ ] Query type detection (simple/comprehensive/url-based)
- [ ] Phase templates based on complexity
- [ ] QueryParser for intent classification

### Phase 4: Conversational Interface
- [ ] Multi-turn dialogue support
- [ ] Follow-up question handling (QAEngine)
- [ ] Refinement operations (add_papers, change_focus)
- [ ] State machine (IDLE → PLANNING → RESEARCHING → INTERACTIVE)

### Phase 5: Vector Store
- [ ] Semantic search over papers
- [ ] "Find similar" functionality
- [ ] Embedding caching
