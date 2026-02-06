# Agent Guide - Research Assistant (v3.0)

> Quick reference for AI Agents working on this codebase

## Current State (v3.0 - Phase 1-2 Complete)

| Component | Status | Location |
|-----------|--------|------------|
| PlanExecutor | ✅ Enhanced | `src/planner/executor.py` |
| AnalyzerService | ✅ Working | `src/research/analysis/analyzer.py` |
| PaperRepository | ✅ Working | `src/storage/repositories.py` |
| **ToolCacheManager** | ✅ **NEW** | `src/tools/cache_manager.py` |
| **ResearchMemoryManager** | ✅ **NEW** | `src/core/memory_manager.py` |
| **PDFLoaderService** | ✅ **NEW** | `src/research/analysis/pdf_loader.py` |
| SummarizerService | ✅ Integrated | `src/research/analysis/summarizer.py` |
| ClustererService | ✅ Integrated | `src/research/analysis/clusterer.py` |
| WriterService | ✅ Integrated | `src/research/synthesis/writer.py` |

## Project Structure

```
backend/src/
├── core/
│   ├── schema.py           # API schemas
│   ├── models.py           # MongoDB models
│   ├── database.py         # MongoDB connection
│   ├── config.py           # Settings (MongoDB/Redis URLs)
│   └── memory_manager.py   # ✅ NEW: Session memory
├── tools/
│   ├── builtin/            # arxiv, huggingface, collector
│   ├── registry.py         # Tool registration
│   └── cache_manager.py    # ✅ NEW: Redis cache
├── planner/
│   ├── executor.py         # ✅ ENHANCED: Cache + metrics
│   └── service.py          # PlannerService
├── research/
│   ├── analysis/
│   │   ├── analyzer.py     # Relevance scoring
│   │   ├── pdf_loader.py   # ✅ NEW: Selective PDF loading
│   │   ├── summarizer.py   # ✅ INTEGRATED
│   │   └── clusterer.py    # ✅ INTEGRATED
│   ├── synthesis/
│   │   └── writer.py       # ✅ INTEGRATED: Report generation
│   └── pipeline.py         # ✅ COMPLETE: 8-phase pipeline
└── storage/
    └── repositories.py     # MongoDB repos
```

## Quick Commands

```bash
# Start services
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6379:6379 redis:7

# Activate environment
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# Run full pipeline test
python scripts/test_phase_1_2.py

# Run old tests (still work)
python scripts/test_research_pipeline.py
python scripts/debug_analyzer.py
```

## Key Classes & Usage

### ResearchPipeline (Complete 8-Phase)
```python
from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest

pipeline = ResearchPipeline(llm_client, skip_synthesis=False)
request = ResearchRequest(topic="AI Research")

result = await pipeline.run(request)

# Access results
print(f"Session: {result.session_id}")
print(f"Papers: {result.unique_papers}")
print(f"Relevant: {result.relevant_papers}")
print(f"High-value: {result.high_relevance_papers}")
print(f"Clusters: {result.clusters_created}")
print(f"Cache hit rate: {result.cache_hit_rate:.1%}")
print(f"Report:\n{result.report_markdown}")
```

### ToolCacheManager
```python
from src.tools.cache_manager import get_cache_manager

cache = await get_cache_manager()

# Check cache
result = await cache.get("arxiv_search", query="AI")
if result is None:
    # Execute and cache
    result = await execute_tool(...)
    await cache.set("arxiv_search", result, query="AI")

# Metrics
metrics = cache.get_metrics()
print(f"Hit rate: {metrics['cache_hit_rate']:.1%}")
```

### ResearchMemoryManager
```python
from src.core.memory_manager import ResearchMemoryManager

memory = ResearchMemoryManager()
await memory.connect()

# Create session
session_id = await memory.create_session("AI Topic", plan_id="...")

# Register papers
for paper in papers:
    await memory.register_paper(session_id, paper)

# Phase transitions
await memory.transition_phase(session_id, "analysis")

# Checkpoints
await memory.checkpoint(session_id, "analysis")

# Restore
session = await memory.restore_from_checkpoint(session_id, "analysis")

# Get context
context = await memory.get_analysis_context(session_id)
```

### PDFLoaderService
```python
from src.research.analysis.pdf_loader import PDFLoaderService

loader = PDFLoaderService(
    cache_manager=cache,
    relevance_threshold=8.0  # Only score >= 8
)

# Load for single paper
success = await loader.load_full_text(paper)

# Batch load
loaded_count = await loader.load_full_text_batch(papers)
```

## Pipeline Phases

The complete pipeline now has 8 phases:

1. **Planning** - Generate research plan
2. **Execution** - Collect papers (with cache)
3. **Persistence** - Save to MongoDB
4. **Analysis** - Score relevance
5. **PDF Loading** - Load full text (score >= 8)
6. **Summarization** - Generate summaries
7. **Clustering** - Group by theme
8. **Writing** - Generate report

Each phase creates a checkpoint for resume capability.

## Implementation Tasks Completed (Phase 1-2)

✅ **Task 1:** Redis tool cache layer
✅ **Task 2:** ResearchMemoryManager
✅ **Task 3:** Selective full-text loading
✅ **Task 4:** Wire clustering service
✅ **Task 5:** Wire summarizer service
✅ **Task 6:** Wire writer service
✅ **Task 7:** Enhanced metrics

## Next Implementation Tasks (Phase 3+)

### Phase 3: Adaptive Planning
1. Query type detection (simple/comprehensive/url-based)
2. Phase templates based on complexity
3. QueryParser for intent classification
4. Adaptive planner that chooses phases based on query type

### Phase 4: Conversational Interface
1. Multi-turn dialogue support
2. IntentClassifier (research_query | follow_up | refinement)
3. QAEngine for answering questions about papers
4. Refinement handlers (add_papers, change_focus, deep_dive)
5. State machine (IDLE → PLANNING → RESEARCHING → INTERACTIVE)

## Key Metrics

The pipeline now tracks:
- Cache hit rate
- Average step duration
- Relevance bands (3-5, 6-7, 8-10)
- High-relevance paper count
- Papers with full text loaded
- Papers with summaries
- Clusters created

## Common Workflows

### Run Full Pipeline
```python
pipeline = ResearchPipeline(llm)
result = await pipeline.run(ResearchRequest(topic="AI"))
```

### Run Without Synthesis (Fast)
```python
pipeline = ResearchPipeline(llm, skip_synthesis=True)
result = await pipeline.run(request)
# Only runs: Planning → Execution → Persistence → Analysis
```

### Resume from Checkpoint
```python
memory = ResearchMemoryManager()
await memory.connect()

# Restore session
session = await memory.restore_from_checkpoint(
    session_id="abc-123",
    phase_id="analysis"
)

# Continue from there...
```

## Testing

### Unit Tests
```bash
pytest tests/
```

### Integration Tests
```bash
# Full pipeline (v3.0)
python scripts/test_phase_1_2.py

# Original tests (still work)
python scripts/test_research_pipeline.py
python scripts/debug_analyzer.py
```

## Configuration

### Cache TTLs
Edit `src/tools/cache_manager.py`:
```python
TTL_CONFIG = {
    "arxiv_search": 3600,     # 1 hour
    "hf_trending": 1800,      # 30 min
    "collect_url": 86400,     # 24 hours
}
```

### PDF Threshold
Edit `src/research/analysis/pdf_loader.py`:
```python
relevance_threshold = 8.0  # Minimum score to load PDF
```

### Session TTL
Edit `src/core/memory_manager.py`:
```python
SESSION_TTL = 86400  # 24 hours
```

## Debugging

### Check Redis Cache
```bash
docker exec -it redis redis-cli
KEYS tool_cache:*
GET tool_cache:arxiv_search:...
```

### Check MongoDB
```bash
docker exec -it mongo mongosh
use research_assistant
db.papers.find().limit(5)
db.papers.countDocuments({relevance_score: {$gte: 8}})
```

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Architecture Patterns

### Multi-Layer Storage
- **Hot:** In-process (fast, temporary)
- **Warm:** Redis (medium, 24h TTL)
- **Cold:** MongoDB (slow, permanent)

### Lazy Loading
- Full text only loaded when needed (score >= 8)
- PDFs cached to avoid re-downloads
- Tools cached to avoid re-execution

### Checkpointing
- Automatic at phase boundaries
- Manual via `memory.checkpoint(session_id, phase_id)`
- Restore via `memory.restore_from_checkpoint()`

## Quick Reference

| Need | Use |
|------|-----|
| Run full pipeline | `ResearchPipeline(llm).run(request)` |
| Check cache | `ToolCacheManager.get()` |
| Track session | `ResearchMemoryManager.create_session()` |
| Load PDFs | `PDFLoaderService.load_full_text_batch()` |
| Generate report | Automatic in phase 8 |
| Resume work | `memory.restore_from_checkpoint()` |
