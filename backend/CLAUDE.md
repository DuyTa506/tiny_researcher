# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Research Assistant Backend (v3.0)** is an AI-powered research paper aggregation and analysis system that automatically collects, analyzes, clusters, and summarizes academic papers from multiple sources (arXiv, Hugging Face, URLs), then generates comprehensive Markdown reports.

**Current Status:** Phase 1-2 Complete - Full 8-phase pipeline operational with Redis caching, session management, and complete report generation.

## Project Structure

```
research_assistant/backend/
├── src/
│   ├── core/                   # Core infrastructure
│   │   ├── config.py          # Settings (MongoDB, Redis)
│   │   ├── database.py        # MongoDB connection
│   │   ├── models.py          # Pydantic models
│   │   ├── schema.py          # API schemas
│   │   ├── prompts.py         # LLM prompts
│   │   └── memory_manager.py  # ✨ Session memory (Phase 1-2)
│   ├── tools/                  # Tool system
│   │   ├── registry.py        # Tool registration
│   │   ├── schema.py          # Tool schemas
│   │   ├── cache_manager.py   # ✨ Redis cache (Phase 1-2)
│   │   └── builtin/           # Built-in tools
│   ├── planner/                # Research planning
│   │   ├── service.py         # Plan generation
│   │   ├── executor.py        # ✨ Plan execution (enhanced)
│   │   └── store.py           # Plan storage
│   ├── research/               # Research workflow
│   │   ├── pipeline.py        # ✨ Complete 8-phase pipeline
│   │   ├── analysis/
│   │   │   ├── analyzer.py    # Relevance scoring
│   │   │   ├── pdf_loader.py  # ✨ Selective PDF loading (Phase 1-2)
│   │   │   ├── summarizer.py  # Paper summarization
│   │   │   └── clusterer.py   # Theme clustering
│   │   └── synthesis/
│   │       └── writer.py      # Report generation
│   ├── storage/                # Data persistence
│   │   ├── repositories.py    # MongoDB repos
│   │   └── vector_store.py    # Vector embeddings
│   ├── adapters/               # External integrations
│   │   └── llm.py             # LLM clients
│   └── api/                    # FastAPI endpoints
│       └── main.py
├── scripts/                    # Test scripts
│   ├── test_phase_1_2.py      # ✨ Full pipeline test (NEW)
│   ├── test_research_pipeline.py
│   └── debug_analyzer.py
├── docs/                       # Documentation
│   ├── phase_1_2_implementation.md  # ✨ Current implementation
│   ├── agent_guide.md         # Quick reference
│   ├── checklist.md           # Progress tracking
│   ├── dataflow.md            # Architecture diagrams
│   ├── system_design.md       # System architecture
│   └── process_track.md       # Development tracking
├── pyproject.toml             # Poetry dependencies
├── .env.example               # Environment template
├── QUICKSTART.md              # ✨ Getting started guide
└── CLAUDE.md                  # This file
```

## Development Commands

### Package Management

The project uses **Poetry** for dependency management.

```bash
# Activate environment (Windows)
.\venv\Scripts\Activate.ps1

# Activate environment (Linux/Mac)
source venv/bin/activate

# Install dependencies
poetry install

# Add new package
poetry add <package_name>
```

### Docker Services

**Required services:** MongoDB (database) and Redis (caching/sessions)

```bash
# Start MongoDB
docker run -d -p 27017:27017 --name mongo mongo:7

# Start Redis
docker run -d -p 6379:6379 --name redis redis:7

# Verify services
docker ps

# Stop services
docker stop mongo redis

# Remove containers
docker rm mongo redis
```

### Running Tests

```bash
# Full Phase 1-2 pipeline test (RECOMMENDED)
python scripts/test_phase_1_2.py

# Legacy tests (still functional)
python scripts/test_research_pipeline.py
python scripts/debug_analyzer.py

# Unit tests (future)
pytest tests/
```

## Entry Points

### Main Pipeline
```python
from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest

# Full 8-phase pipeline
pipeline = ResearchPipeline(llm_client, skip_synthesis=False)
result = await pipeline.run(ResearchRequest(topic="AI Research"))
```

### Fast Analysis Only
```python
# Skip synthesis phases (faster, no report)
pipeline = ResearchPipeline(llm_client, skip_synthesis=True)
result = await pipeline.run(request)
```

## Development Strategy

### Code Organization Principles

1. **No over-engineering** - Implement only what's needed
2. **Clear separation of concerns** - Each service has a single responsibility
3. **Async-first** - All I/O operations use async/await
4. **Type hints** - Use Pydantic models and type annotations
5. **Lazy loading** - Only load resources when needed (e.g., PDFs for high-value papers only)

### Architecture Patterns

**Multi-Layer Storage:**
- **Hot:** In-process Python dicts (fast, temporary)
- **Warm:** Redis (medium speed, 24h TTL, for caching/sessions)
- **Cold:** MongoDB (persistent, for long-term storage)

**Caching Strategy:**
- Tool results cached by (tool_name, args) → 1-24h TTL
- PDF content cached by URL → 7 day TTL
- Session data cached by session_id → 24h TTL

**Phase-Based Processing:**
```
Planning → Execution → Persistence → Analysis →
PDF Loading → Summarization → Clustering → Writing
```

Each phase creates a checkpoint for resume capability.

### Testing Philosophy

- **Test-driven when fixing bugs** - Write failing test, then fix
- **Integration tests for pipelines** - Test complete workflows
- **Mock LLMs for unit tests** - Don't call real APIs in tests
- **Snapshot testing for prompts** - Ensure consistent LLM inputs

### LLM Usage

**Current providers:**
- OpenAI (GPT-4, GPT-3.5)
- Google Gemini (gemini-1.5-flash, gemini-1.5-pro)

**Best practices:**
- Use `json_mode=True` for structured outputs
- Always validate and parse LLM responses
- Implement retries for transient failures
- Use smaller models for simple tasks (e.g., relevance scoring with Gemini Flash)

## Notes for Development

### Critical Rules

1. **Always use existing tools** - Don't create duplicate functionality
2. **Read before modifying** - Use `Read` tool to understand existing code
3. **Preserve existing behavior** - Unless explicitly asked to change it
4. **Follow the patterns** - Match existing code style and architecture
5. **Update docs** - Keep `docs/` in sync with code changes

### Database Schema

**MongoDB Collections:**
- `papers` - Research papers with metadata, scores, summaries
- `clusters` - Paper groupings by theme
- `reports` - Generated reports
- `plans` - Research plans

**Redis Keys:**
- `tool_cache:{tool_name}:{md5(args)}` - Tool results
- `pdf_cache:{pdf_url}` - PDF content
- `session:{session_id}` - Session state
- `checkpoint:{session_id}:{phase_id}` - Checkpoints

### Key Configuration

**Environment variables (.env):**
```bash
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=research_assistant
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
```

**Cache TTLs (src/tools/cache_manager.py):**
```python
TTL_CONFIG = {
    "arxiv_search": 3600,     # 1 hour
    "hf_trending": 1800,      # 30 min
    "collect_url": 86400,     # 24 hours
}
```

**PDF threshold (src/research/analysis/pdf_loader.py):**
```python
relevance_threshold = 8.0  # Only load PDFs for score >= 8
```

### Common Patterns

**Async service initialization:**
```python
# Always connect before use
await connect_mongodb()
cache = await get_cache_manager()
```

**Error handling:**
```python
# Graceful degradation
try:
    result = await risky_operation()
except Exception as e:
    logger.warning(f"Operation failed: {e}")
    result = fallback_value
```

**Progress tracking:**
```python
# Use ExecutionProgress for metrics
progress.add_step_result(result)
print(f"Cache hit rate: {progress.cache_hit_rate:.1%}")
```

## Current Limitations & Known Issues

1. **HuggingFace scraper** - Selector may be broken (HF UI changed)
2. **No authentication** - API has no auth (development only)
3. **Single instance** - No distributed processing yet
4. **No API endpoints for pipeline** - Must call directly via Python

## Roadmap

### Phase 3: Adaptive Planning (Next)
- Query parser for intent classification
- Phase templates based on query complexity
- Adaptive planner that chooses workflow

### Phase 4: Conversational Interface
- Multi-turn dialogue support
- Follow-up question handling
- Refinement operations (add papers, change focus)

### Phase 5: Production Readiness
- API endpoints for all operations
- Authentication and rate limiting
- Horizontal scaling with Celery
- Vector search for semantic similarity

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `docker run -d -p 27017:27017 mongo:7`<br>`docker run -d -p 6379:6379 redis:7` |
| Run full pipeline | `python scripts/test_phase_1_2.py` |
| Check Redis cache | `docker exec -it redis redis-cli`<br>`KEYS tool_cache:*` |
| Check MongoDB | `docker exec -it mongo mongosh`<br>`use research_assistant`<br>`db.papers.find().limit(5)` |
| Clear cache | In Redis: `FLUSHDB` |

## Documentation

- **QUICKSTART.md** - Getting started guide
- **docs/phase_1_2_implementation.md** - Current implementation details
- **docs/agent_guide.md** - AI agent quick reference
- **docs/system_design.md** - System architecture
- **docs/dataflow.md** - Pipeline flow diagrams

## Getting Help

For questions about:
- **Architecture** - See `docs/system_design.md`
- **Current features** - See `docs/checklist.md`
- **How to use** - See `QUICKSTART.md`
- **What's next** - See `docs/process_track.md`
