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

## Phase 4: Planner ✅
- [x] PlannerService - generates tool-based plans
- [x] PlanStore - in-memory status tracking
- [x] PlanExecutor - executes tools with deduplication

## Phase 5: Analysis Pipeline ✅
- [x] AnalyzerService - batch relevance scoring
- [x] Multi-level deduplication (arxiv_id, fingerprint, title)
- [x] MongoDB persistence integration
- [x] JSON parsing fix for LLM responses

## Phase 6: Content Processing ⏳
- [ ] **Full text loading** - PDF download for score >= 8
- [ ] SummarizerService - generate paper summaries
- [ ] ClustererService - group by theme
- [ ] WriterService - generate report

## Phase 7: API Layer ⏳
- [x] FastAPI setup
- [x] Plan CRUD endpoints
- [ ] Pipeline execution endpoint
- [ ] Report retrieval endpoint

---

## Architecture (Current v2.4)

```
User Input → PlannerService → ResearchPlan
                                   ↓
                            PlanExecutor
                                   ↓
              ┌────────────────────┴────────────────────┐
              ↓                                         ↓
        Tool Registry                          PaperDeduplicator
              ↓                                         ↓
        ArxivSearcher ─────────────────────►   Unique Papers
                                                        ↓
                                              MongoDB (papers)
                                                        ↓
                                        ┌───── AnalyzerService ✅
                                        │         (batch scoring)
                                        ↓
                              Papers with scores
                                        ↓
                        [TODO] Full Text Loader (score >= 8)
                                        ↓
                        [TODO] SummarizerService
                                        ↓
                        [TODO] WriterService → Report
```

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| test_research_pipeline.py | ✅ | 99 papers, scores 3-9 |
| debug_analyzer.py | ✅ | JSON parsing fixed |
| test_mongodb.py | ✅ | CRUD working |
