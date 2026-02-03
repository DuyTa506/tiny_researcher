# Backend Checklist

> **Checklist for Backend AI Agent** to track implementation progress.

## Phase 1: Foundation Setup
- [ ] **Project Init**: Setup Python Poetry project structure.
- [ ] **Environment**: Configure `.env`, `config.py` (Pydantic Settings).
- [ ] **Database**: Setup SQLAlchemy Async Engine & Alembic Migrations.
- [ ] **Docker**: Create `docker-compose.yml` (Postgres, Redis, Qdrant).

## Phase 2: Domain Modeling
- [ ] **Models**: Implement `Source`, `Paper`, `Report`, `Cluster` tables.
- [ ] **Migrations**: Generate and apply initial schema.
- [ ] **Repositories**: Create CRUD repositories for async DB access.

## Phase 3: Core Services (The "Brains")
- [ ] **Ingestion Service**:
    - [ ] Implement `Collector` (RSS parsing).
    - [ ] Implement `Searcher` (ArXiv API client).
- [ ] **Analyzer Service**:
    - [ ] Keyword/Time filtering logic.
    - [ ] LLM Adapter setup (Gemini/OpenAI).
    - [ ] `summarize_paper` prompt engineering.
- [ ] **Cluster Service**:
    - [ ] Embedding generation (Sentence-Transformers).
    - [ ] HDBSCAN clustering logic.
    - [ ] LLM Cluster Labeling.
- [ ] **Writer Service**:
    - [ ] Cluster summary synthesis.
    - [ ] Markdown report generation.

## Phase 4: API Layer
- [ ] **FastAPI Setup**: Main app factory, CORS, Exception Handlers.
- [ ] **Endpoints**:
    - [ ] `POST /sources`: Add monitoring source.
    - [ ] `GET /papers`: List papers with filters.
    - [ ] `POST /ingestion/trigger`: Manual trigger.
    - [ ] `POST /reports/generate`: On-demand report.

## Phase 5: Async Workers & Integration
- [ ] **Celery**: Configure Worker & Redis Broker.
- [ ] **Tasks**: Define async tasks for Ingestion and Reporting.
- [ ] **n8n Integration**: Setup Webhooks for notification callbacks.

## Phase 6: Testing & Validation
- [ ] **Unit Tests**: Services logic (Mock Repository/LLM).
- [ ] **Integration Tests**: API → DB flow.
- [ ] **Seed Data**: Create script to populate dummy data for Frontend dev.
