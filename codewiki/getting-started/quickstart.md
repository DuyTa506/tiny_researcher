# Quickstart

```text
Related code:
- docker-compose.yml:1-100
- backend/.env.example:1-50
- README.md:27-94
- backend/src/api/main.py:43-59
```

## Prerequisites

- **Docker & Docker Compose** (recommended) OR
- **Python 3.11+** + **Node.js 18+** (manual setup)
- **LLM API Key**: OpenAI or Google Gemini (at least one required)
- **8GB RAM** minimum for local MongoDB/Redis

## 3-Step Docker Setup (Recommended)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd tiny_researcher

# Copy environment template
cp backend/.env.example backend/.env

# Edit backend/.env - add your API key:
# GEMINI_API_KEY=your_key_here
# OR
# OPENAI_API_KEY=your_key_here
```

### 2. Start All Services

```bash
docker compose up --build
```

This starts:
- **Frontend** at `http://localhost` (Next.js)
- **Backend API** at `http://localhost/api/v1/docs` (FastAPI with OpenAPI docs)
- **MongoDB** at `localhost:27017`
- **Redis** at `localhost:6379`
- **Nginx** reverse proxy at port 80

### 3. Create Your First Research Session

1. Open `http://localhost` in your browser
2. Click "Start Research"
3. Enter a research topic (e.g., "transformer architectures for NLP")
4. The system will:
   - Generate a research plan (5-10 search queries)
   - Execute parallel searches on ArXiv + OpenAlex
   - Screen papers for relevance
   - Extract evidence with page-level citations
   - Generate a grounded Markdown report

Expected time: 2-5 minutes for 10-20 papers.

## Manual Development Setup

### Backend

```bash
cd backend

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spacy model (for text processing)
python -m spacy download en_core_web_sm

# Start MongoDB and Redis
docker run -d -p 27017:27017 --name mongo mongo:7
docker run -d -p 6379:6379 --name redis redis:7

# Configure environment
cp .env.example .env
# Edit .env with your GEMINI_API_KEY or OPENAI_API_KEY

# Run backend
uvicorn src.api.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure API URL (optional, defaults to /api/v1 for nginx proxy)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

# Run frontend
npm run dev
```

Frontend will be available at `http://localhost:3000`

## First-Hour Exploration Guide

### Key Entrypoints

1. **Backend API**: `backend/src/api/main.py`
   - FastAPI app with 7 routers (auth, papers, reports, conversations, sources, planner, websocket)
   - Startup connects MongoDB and creates indexes
   - Health check at `/health`

2. **Research Pipeline**: `backend/src/research/pipeline.py`
   - `ResearchPipeline.run()` orchestrates 10-phase citation-first workflow
   - `_run_citation_pipeline()` for default mode
   - `_run_legacy_pipeline()` for backward-compatible 8-phase mode

3. **Frontend Chat**: `frontend/src/hooks/useResearchChat.ts`
   - SSE connection manager
   - Handles 15+ event types (progress, state_change, message, plan, papers_collected, etc.)
   - Token streaming assembly

4. **Frontend Dashboard**: `frontend/src/app/page.tsx`
   - Main entry screen with stats
   - Recent sessions list
   - Quick access to research/papers/reports

### Key Directories to Explore

| Path | Purpose | Start Here |
|------|---------|------------|
| `backend/src/research/` | Pipeline implementation | `pipeline.py`, `analysis/screener.py`, `synthesis/grounded_writer.py` |
| `backend/src/core/` | Data models and config | `models.py` (Paper, EvidenceSpan, Claim), `prompts.py` |
| `backend/src/storage/` | MongoDB repositories | `repositories.py` (8 repository classes) |
| `backend/src/tools/` | Search tools | `builtin/search.py`, `cache_manager.py` |
| `frontend/src/components/chat/` | Research UI components | `PlanCard/`, `PapersCollectedCard/`, `ClaimsCard/` |
| `frontend/src/services/` | API clients | `conversations.ts`, `papers.ts`, `reports.ts` |

## Expected Outputs

### After Running a Research Session

You should see:

1. **In MongoDB** (`research_assistant` database):
   - `papers` collection: 10-50 papers with metadata, full text, page maps
   - `screening_records`: Include/exclude decisions with reason codes
   - `evidence_spans`: 50-200 verbatim snippets with page locators
   - `study_cards`: Structured extractions (problem, method, datasets, metrics)
   - `claims`: 20-50 atomic citable statements
   - `reports`: Final Markdown report with citations

2. **In Redis** (check with `docker exec -it redis redis-cli`):
   ```
   KEYS tool_cache:*        # Cached search results
   KEYS pdf_pages_cache:*   # Cached PDF content with page maps
   KEYS session:*           # Active session state
   ```

3. **In Frontend**:
   - Real-time activity log showing each phase
   - Papers collected card (preview of papers)
   - Plan card (search queries)
   - Claims card (atomic claims with evidence)
   - Final report (Markdown with citations)

## Next Steps

- **Understand the Pipeline**: Read [Architecture Overview](/architecture/overview) for flow diagrams
- **Explore Components**: See [Core Components](/core-components/overview) for service responsibilities
- **Debug Issues**: Check [Development Guide](/development/overview) for common debugging workflows
- **API Integration**: Read [API Reference](/api-reference/overview) for programmatic access

## Prerequisites

- [toolchain]

## Steps
1. `[command]`

## Expected Output
- [what success looks like]
