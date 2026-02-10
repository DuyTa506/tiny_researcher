# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Research Assistant Backend (v4.0)** is an AI-powered research paper aggregation and analysis system that automatically collects, screens, extracts evidence, and synthesizes citation-grounded Markdown reports from multiple sources (arXiv, OpenAlex, Hugging Face, URLs).

**Current Status:** Citation-First Workflow (v4.0) - Full 10-phase citation-first pipeline with screening, evidence extraction, study cards, claims, citation audit, taxonomy/gap mining, HITL approval gates, plus backward-compatible legacy 8-phase mode.

## Project Structure

```
research_assistant/backend/
├── src/
│   ├── core/                   # Core infrastructure
│   │   ├── config.py          # Settings (MongoDB, Redis)
│   │   ├── database.py        # MongoDB connection + collection constants
│   │   ├── models.py          # Pydantic models (Paper, EvidenceSpan, StudyCard, Claim, etc.)
│   │   ├── schema.py          # API schemas (ResearchRequest, ResearchPlan)
│   │   ├── prompts.py         # LLM prompts (screening, evidence, claims, audit, gaps)
│   │   └── memory_manager.py  # Session memory, phase transitions (Phase 1-2)
│   ├── tools/                  # Tool system
│   │   ├── registry.py        # Tool registration
│   │   ├── schema.py          # Tool schemas
│   │   ├── cache_manager.py   # Redis cache (Phase 1-2)
│   │   └── builtin/           # Built-in tools
│   ├── planner/                # Research planning
│   │   ├── service.py         # Plan generation
│   │   ├── executor.py        # Plan execution (enhanced)
│   │   ├── store.py           # Plan storage
│   │   ├── query_parser.py    # Query parsing (QUICK/FULL)
│   │   └── adaptive_planner.py # Adaptive planning with citation-first phase templates
│   ├── conversation/           # Conversational interface
│   │   ├── context.py         # ConversationContext, DialogueState, message history
│   │   ├── intent.py          # IntentClassifier, UserIntent (with conversation history)
│   │   ├── clarifier.py       # Query clarification (with conversation history)
│   │   └── dialogue.py        # DialogueManager (short-term memory via last 6 messages)
│   ├── research/               # Research workflow
│   │   ├── pipeline.py        # 10-phase citation-first pipeline (+ legacy 8-phase)
│   │   ├── gates.py           # ✨ HITL approval gates (PDF/URL/token budget)
│   │   ├── analysis/
│   │   │   ├── analyzer.py    # Relevance scoring
│   │   │   ├── screener.py    # ✨ Systematic paper screening (include/exclude)
│   │   │   ├── pdf_loader.py  # PDF loading with page mapping + domain filtering
│   │   │   ├── evidence_extractor.py  # ✨ Schema-driven evidence extraction → StudyCards
│   │   │   ├── taxonomy.py    # ✨ TaxonomyBuilder + gap detection
│   │   │   ├── summarizer.py  # Paper summarization (legacy)
│   │   │   └── clusterer.py   # Theme clustering
│   │   ├── ingestion/
│   │   │   ├── searcher.py        # ArxivSearcher + OpenAlexSearcher
│   │   │   └── query_refiner.py   # LLM + heuristic query refinement
│   │   └── synthesis/
│   │       ├── claim_generator.py   # ✨ Evidence → atomic claims
│   │       ├── grounded_writer.py   # ✨ Citation-grounded report writer
│   │       ├── citation_audit.py    # ✨ LLM judge + auto-repair for citations
│   │       ├── gap_miner.py         # ✨ Future directions from taxonomy holes
│   │       └── writer.py           # Report generation (legacy)
│   ├── storage/                # Data persistence
│   │   ├── repositories.py    # MongoDB repos (8 repositories)
│   │   └── vector_store.py    # Vector embeddings
│   ├── utils/                  # Utilities
│   │   └── pdf_parser.py      # PDF fetching with page mapping + snippet locator
│   ├── adapters/               # External integrations
│   │   └── llm.py             # LLM clients
│   └── api/                    # FastAPI endpoints
│       └── main.py
├── scripts/                    # Test scripts
│   ├── test_api.py            # API integration test
│   ├── test_cli.py            # CLI test
│   ├── test_phase_1_2.py      # Full pipeline test
│   ├── test_phase_3.py        # Adaptive planning test
│   ├── test_phase_4.py        # Conversational interface test
│   ├── test_openalex.py       # Multi-source search + URL extraction test
│   ├── test_research_pipeline.py
│   └── debug_analyzer.py
├── docs/                       # Documentation
│   ├── phase_5_api_integration.md  # API implementation
│   ├── phase_1_2_implementation.md
│   ├── agent_guide.md         # Quick reference
│   ├── checklist.md           # Progress tracking
│   ├── dataflow.md            # Architecture diagrams
│   ├── system_design.md       # System architecture
│   └── process_track.md       # Development tracking
├── requirements.txt            # pip dependencies
├── requirements-dev.txt        # Development dependencies
├── pyproject.toml             # Poetry config (legacy)
├── .env.example               # Environment template
├── QUICKSTART.md              # Getting started guide
└── CLAUDE.md                  # This file
```

## Development Commands

### Package Management

The project uses **pip** or **uv** for dependency management.

```bash
# Using pip (traditional)
# Activate environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Add new package
pip install <package_name>
# Then update requirements.txt:
pip freeze > requirements.txt
```

```bash
# Using uv (faster alternative)
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Add new package
uv pip install <package_name>
# Then update requirements.txt:
uv pip freeze > requirements.txt
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
# Full Phase 1-2 pipeline test
python scripts/test_phase_1_2.py

# Phase 3 adaptive planning test
python scripts/test_phase_3.py

# Phase 4 conversational interface test
python scripts/test_phase_4.py

# Multi-source search + URL extraction test
python scripts/test_openalex.py

# Legacy tests (still functional)
python scripts/test_research_pipeline.py
python scripts/debug_analyzer.py

# Unit tests (future)
pytest tests/
```

## Entry Points

### Citation-First Pipeline (Default, Two-Step with Review)
```python
from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest

# Citation-first is the default (use_citation_workflow=True)
pipeline = ResearchPipeline(llm_client, use_adaptive_planner=True)

# Step 1: Generate plan for review
request = ResearchRequest(topic="transformer models", max_pdf_download=20)
adaptive_plan = await pipeline.generate_adaptive_plan(request)

# Human reviews plan
print(adaptive_plan.to_display())
# "Mode: FULL"
# "Phases: planning, execution, persistence, screening, ..."

# Human can edit
adaptive_plan.plan.steps[0].queries.append("BERT")

# Step 2: Execute approved plan (10-phase citation-first)
result = await pipeline.execute_plan(request, adaptive_plan=adaptive_plan)
# result includes: study_cards, evidence_spans, claims, taxonomy, future_directions
```

### Legacy Pipeline (8-Phase, No Citation Tracking)
```python
# Disable citation workflow for legacy 8-phase mode
pipeline = ResearchPipeline(llm_client, use_citation_workflow=False)
result = await pipeline.run(ResearchRequest(topic="AI Research"))
```

### One-Shot (No Review, for Automation)
```python
pipeline = ResearchPipeline(llm_client)
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

**Phase-Based Processing (Citation-First, v4.0):**
```
Planning → Collection+Dedup → Persistence → Screening → HITL Gate →
PDF Loading (with pages) → Evidence Extraction → Clustering → Taxonomy →
Claims + Gaps → Grounded Report → Citation Audit → Publish
```

**Legacy Phase-Based Processing (v3.x):**
```
Planning → Execution → Persistence → Analysis →
PDF Loading → Summarization → Clustering → Writing
```

Each phase creates a checkpoint for resume capability.

**Citation-First Core Concepts:**
- **EvidenceSpan** - Verbatim snippet with locator (page/section/char offsets) + confidence
- **StudyCard** - Schema-driven extraction (problem, method, datasets, metrics, results, limitations)
- **Claim** - Atomic citable statement backed by ≥1 evidence spans
- **ScreeningRecord** - Systematic include/exclude decision with reason codes
- **TaxonomyMatrix** - Multi-dimensional (themes × datasets × metrics) for gap detection
- **HITL Gates** - Human approval for PDF downloads, external URLs, token budgets

**Unified Search Tool Architecture:**
- **Single `search` tool** - Replaces legacy `arxiv_search`, `arxiv_search_keywords`, `openalex_search`
- **Parallel execution** - ArXiv + OpenAlex run concurrently via `asyncio.gather` (not sequential fallback)
- **Multi-source deduplication** - 4-level strategy:
  1. ArXiv ID matching (arxiv_id)
  2. DOI matching (doi, normalized lowercase)
  3. Fingerprint matching (md5 hash of title + first author)
  4. Title similarity (SequenceMatcher ≥0.85 threshold)
- **OpenAlex filtering** - Only papers with `has_fulltext:true` (PDF content available)
- **ArXiv rate limiting** - Global semaphore (1 concurrent) + 3.5s interval between requests
- **URL extraction** - Regex pattern in intent classifier extracts URLs from user messages → `ConversationContext.pending_urls` → `ResearchRequest.sources`
- **Query refinement** - When results are poor quality (<20% title-keyword match), auto-refines query:
  - LLM-based refinement (Gemini Flash) suggests better academic terms
  - Heuristic fallback: removes version numbers, tries 2-word pairs (never single words), adds "survey"
  - Max 2 retry attempts with quality checks between rounds
  - Example: "DeepSeek OCR 1 and 2" → tries "DeepSeek OCR" → tries "DeepSeek OCR survey"
- **OpenAlex query condensing** - Long queries condensed to max 4 significant words (OpenAlex `title_and_abstract.search` requires ALL terms to match, so long queries return 0)
- **PDF domain filtering** - Blocklist of 16 paywalled publisher domains (ACM, Springer, Elsevier, IEEE, etc.) to skip 403 errors
- **Report filename sanitization** - Extracts ASCII/English terms only from topic for clean filenames (handles Vietnamese/CJK input)

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
- `papers` - Research papers with metadata, scores, summaries, page_map, pdf_hash
- `clusters` - Paper groupings by theme
- `reports` - Generated reports
- `plans` - Research plans
- `screening_records` - Include/exclude decisions with reason codes (citation-first)
- `evidence_spans` - Verbatim snippets with locators and confidence (citation-first)
- `study_cards` - Schema-driven paper extractions (citation-first)
- `claims` - Atomic citable statements with evidence span IDs (citation-first)

**Redis Keys:**
- `tool_cache:{tool_name}:{md5(args)}` - Tool results
- `pdf_cache:{pdf_url}` - PDF content
- `pdf_pages_cache:{pdf_url}` - PDF content with page mapping (citation-first)
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
OPENALEX_MAILTO=your_email@example.com  # For polite pool (10 req/sec)
```

**Cache TTLs (src/tools/cache_manager.py):**
```python
TTL_CONFIG = {
    "search": 3600,           # 1 hour (unified search: ArXiv + OpenAlex)
    "hf_trending": 1800,      # 30 min
    "collect_url": 86400,     # 24 hours
}
```

**PDF loading (src/research/analysis/pdf_loader.py):**
```python
relevance_threshold = 8.0  # Only load PDFs for score >= 8
# Blocked domains: dl.acm.org, link.springer.com, www.sciencedirect.com,
# ieeexplore.ieee.org, www.nature.com, etc. (16 paywalled publishers)
# Allowed domains: arxiv.org, openreview.net, aclanthology.org, etc.
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

1. **ArXiv rate limiting** - 3.5s interval between requests (global semaphore)
2. **OpenAlex polite pool** - Requires OPENALEX_MAILTO env var for 10 req/sec limit (otherwise 100 req/day)
3. **No anchor-term constraint** - Refined queries are not required to share core terms with the original query, allowing topic drift
4. **No authentication** - API has no auth (development only)
5. **Single instance** - No distributed processing yet

## Roadmap

### Phase 3: Adaptive Planning ✅ COMPLETE
- [x] QueryParser for intent classification
- [x] ResearchQuery model - structured query representation
- [x] AdaptivePlannerService - choose phases based on query type
- [x] Phase templates (QUICK: 4 phases, FULL: 10+ phases)

### Phase 4: Conversational Interface ✅ COMPLETE
- [x] ConversationContext - multi-turn state management
- [x] DialogueManager - conversation flow orchestration
- [x] IntentClassifier - user intent detection (approve, reject, edit, etc.)
- [x] Human-in-the-loop workflow - generate_plan() → review → execute_plan()
- [x] State machine - IDLE → PLANNING → REVIEWING → EXECUTING → COMPLETE
- [x] State persistence (activity_log + detailed_state)
- [x] Short-term conversational memory (last 6 messages passed to all LLM prompts)
- [x] Conversation history in intent classification, clarification, and chat responses

### Phase 5: API Layer ✅ COMPLETE
- [x] REST endpoints for conversations
- [x] WebSocket for real-time updates
- [x] SSE streaming support

### Phase 6: Citation-First Workflow ✅ COMPLETE
- [x] ScreenerService - systematic include/exclude with reason codes
- [x] EvidenceExtractorService - schema-driven extraction → StudyCards + EvidenceSpans
- [x] ClaimGeneratorService - evidence → atomic claims with evidence_span_ids
- [x] GroundedWriterService - citation-grounded Markdown report generation
- [x] CitationAuditService - LLM judge verifying evidence supports claims + auto-repair
- [x] GapMinerService - future directions from taxonomy holes + contradictions
- [x] TaxonomyBuilder - multi-dimensional matrix (themes × datasets × metrics)
- [x] ApprovalGateManager - HITL gates for PDF downloads, external URLs, token budgets
- [x] PDF page mapping + snippet locator (pdf_parser.py enhancements)
- [x] 4 new MongoDB repositories (ScreeningRecord, EvidenceSpan, StudyCard, Claim)
- [x] 7 new LLM prompt templates
- [x] Pipeline restructured to 10-phase flow with legacy fallback

### Phase 7: Multi-Source Search Integration ✅ COMPLETE
- [x] OpenAlex API integration with has_fulltext filter (papers with PDF content only)
- [x] Unified `search` tool - single interface for ArXiv + OpenAlex with automatic fallback routing
- [x] DOI-level deduplication across sources (arxiv_id → DOI → fingerprint → title similarity)
- [x] URL extraction from user messages (regex-based, stored in ConversationContext.pending_urls)
- [x] Source normalization in Paper.from_dict (arxiv_api → arxiv, openalex preserved)
- [x] Inverted index abstract reconstruction for OpenAlex responses

### Phase 8: Parallel Search + Query Refinement + Quality Fixes ✅ COMPLETE
- [x] Parallel multi-source search (ArXiv + OpenAlex via asyncio.gather)
- [x] Quality-aware result checking (title-keyword relevance ratio < 20% = poor)
- [x] QueryRefiner service with LLM-based query improvement (Gemini Flash)
- [x] Heuristic fallback refinement (remove versions, 2-word pairs, add "survey"; never single-word queries)
- [x] OpenAlex query condensing (max 4 significant words for title_and_abstract.search compatibility)
- [x] PDF domain filtering (blocklist of 16 paywalled publishers to skip 403 errors)
- [x] Report filename sanitization (ASCII-only English terms for non-English topics)
- [x] ClaimGenerator theme_id type fix (int → str conversion)
- [x] Retry loop with max 2 attempts and quality checks between rounds
- [x] End-to-end test coverage (8 tests: registration, parallel, OpenAlex, dedup, Paper model, URLs, heuristic, quality-aware)

### Phase 9: Prompt Contract Hardening + Evidence Traceability ✅ COMPLETE
- [x] `_JSON_CONTRACT` prefix on all JSON-returning prompts (valid JSON, no fences, no hallucination)
- [x] `_LANGUAGE_RULE` suffix on multilingual prompts (output in {language}, queries in English)
- [x] Planner tool validation: `tool` field constrained to registered tool names, invalid tools → null
- [x] Planner `expected_output` field on each step (list_papers, study_cards, taxonomy, report, analysis)
- [x] Planner prompt forbids search steps in synthesis/writing phases
- [x] `get_tools_description()` now includes parameter schema (name, type, required) for LLM
- [x] 3-tier screening: `core|background|exclude` replaces binary include/exclude
  - Surveys now classified as `background` instead of excluded
  - ScreeningRecord model has `tier` field with backward-compatible `include` boolean
  - Screening prompt includes `paper_id` echo for stable cross-batch referencing
- [x] Deterministic span_id: `{paper_id}#{sha1(snippet)[:8]}` replaces random UUID
  - Reproducible across runs, prevents hallucinated span IDs
- [x] Citation audit severity: `minor|major` classification
  - Minor: wording imprecise → flag as uncertain only
  - Major: claim unsupported → conservative rewrite
  - AuditResult tracks `failed_major` and `failed_minor` counts
- [x] Anti-hallucination rules in CLAIM_GENERATION and EVIDENCE_EXTRACTION prompts
- [x] Relevance scoring rubric (0-3/4-6/7-8/9-10) in ANALYZER_RELEVANCE prompt

### Future: Production Readiness
- [ ] Authentication and rate limiting
- [ ] Horizontal scaling with Celery
- [ ] Vector search for semantic similarity

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `docker run -d -p 27017:27017 mongo:7`<br>`docker run -d -p 6379:6379 redis:7` |
| Run full pipeline | `python scripts/test_phase_1_2.py` |
| Run adaptive planning test | `python scripts/test_phase_3.py` |
| Run conversational test | `python scripts/test_phase_4.py` |
| Run multi-source search test | `python scripts/test_openalex.py` |
| Check Redis cache | `docker exec -it redis redis-cli`<br>`KEYS tool_cache:*` |
| Check MongoDB | `docker exec -it mongo mongosh`<br>`use research_assistant`<br>`db.papers.find().limit(5)` |
| Clear cache | In Redis: `FLUSHDB` |

## Documentation

- **QUICKSTART.md** - Getting started guide
- **docs/agent_guide.md** - AI agent quick reference
- **docs/system_design.md** - System architecture
- **docs/dataflow.md** - Pipeline flow diagrams

## Getting Help

For questions about:
- **Architecture** - See `docs/system_design.md`
- **How to use** - See `QUICKSTART.md`
