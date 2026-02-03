# Agent Guide - Research Assistant Framework

> **Tài liệu dành cho AI Agents** để hiểu rõ cấu trúc project, coding standards, và architecture patterns.

---

## Project Structure

```
research_assistant/
├── src/
│   ├── core/                      # Core domain models & database
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic/SQLAlchemy models
│   │   ├── database.py            # DB connection & session
│   │   └── config.py              # Configuration management
│   │
│   ├── services/                  # Business logic services
│   │   ├── __init__.py
│   │   ├── planner.py             # Input routing logic
│   │   ├── ingestion/             # Data acquisition
│   │   │   ├── __init__.py
│   │   │   ├── collector.py      # RSS/URL fetching
│   │   │   └── searcher.py       # API search (ArXiv, Semantic Scholar)
│   │   ├── analyzer.py            # Filter & relevance check
│   │   ├── summarizer.py          # LLM paper summarization
│   │   ├── clusterer.py           # Research direction clustering
│   │   └── writer.py              # Report generation
│   │
│   ├── adapters/                  # External integrations
│   │   ├── __init__.py
│   │   ├── llm.py                 # LLM client (Gemini, OpenAI)
│   │   ├── vector_store.py        # Qdrant/Pinecone client
│   │   └── delivery.py            # Email/Notion/Slack delivery
│   │
│   ├── api/                       # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app instance
│   │   ├── routes/
│   │   │   ├── sources.py         # CRUD for sources
│   │   │   ├── papers.py          # Paper management
│   │   │   └── reports.py         # Report generation endpoints
│   │   └── dependencies.py        # Dependency injection
│   │
│   ├── workers/                   # Async task workers
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery configuration
│   │   └── tasks.py               # Background tasks
│   │
│   ├── cli/                       # Command-line interface
│   │   ├── __init__.py
│   │   └── main.py                # CLI commands (Typer)
│   │
│   └── utils/                     # Utilities
│       ├── __init__.py
│       ├── logger.py              # Structured logging
│       ├── validators.py          # Input validation
│       └── text_processing.py     # Text normalization
│
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   │   ├── test_planner.py
│   │   ├── test_analyzer.py
│   │   └── test_summarizer.py
│   ├── integration/               # Integration tests
│   │   ├── test_ingestion_flow.py
│   │   └── test_report_generation.py
│   └── fixtures/                  # Test data
│       ├── sample_papers.json
│       └── mock_responses.py
│
├── migrations/                    # Alembic DB migrations
│   ├── env.py
│   └── versions/
│
├── docker/                        # Docker configurations
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── docs/                          # Documentation
│   ├── design.md                  # System design
│   ├── dataflow.md                # Data flow diagrams
│   ├── erd.md                     # Database schema
│   ├── business-logic.md          # Business rules
│   └── agent.md                   # This file
│
├── scripts/                       # Utility scripts
│   ├── seed_db.py                 # Database seeding
│   └── migrate_embeddings.py      # Data migration
│
├── .env.example                   # Environment variables template
├── pyproject.toml                 # Poetry dependencies
├── pytest.ini                     # Pytest configuration
├── alembic.ini                    # Alembic configuration
└── README.md                      # Project overview
```

---

## Tech Stack

### Core Framework
- **Language**: Python 3.11+
- **API Framework**: FastAPI (async support)
- **Task Queue**: Celery + Redis
- **Package Manager**: Poetry

### Database
- **Primary DB**: PostgreSQL 15+
  - Extension: `pgvector` (for embeddings)
- **Vector DB**: Qdrant (self-hosted or cloud)
- **Cache**: Redis 7+
- **ORM**: SQLAlchemy 2.0 (async mode)
- **Migrations**: Alembic

### AI/ML
- **LLM Provider**: Google Gemini API (primary), OpenAI (fallback)
- **Embeddings**: `sentence-transformers` (all-MiniLM-L6-v2)
- **Clustering**: `scikit-learn` (HDBSCAN, KMeans)
- **NLP**: `spaCy` (for text preprocessing)

### External APIs
- **ArXiv**: `arxiv` Python package
- **Semantic Scholar**: REST API
- **PubMed** (optional): Biopython

### Delivery
- **Email**: SMTP (Gmail, SendGrid)
- **Notion**: Notion API SDK
- **Slack**: Slack SDK

### DevOps
- **Containerization**: Docker + Docker Compose
- **Orchestration** (future): Kubernetes
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structlog + ELK Stack

---

## Architecture Patterns

### 1. Hexagonal Architecture (Ports & Adapters)

**Core Principle**: Business logic độc lập với infrastructure.

```
┌─────────────────────────────────────────┐
│         API / CLI (Driving)             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Application Layer               │
│  (Services: Planner, Analyzer, etc.)    │
└──────────────┬──────────────────────────┘
               │
               ├──► LLM Adapter (Gemini/OpenAI)
               ├──► Vector Store Adapter (Qdrant)
               └──► Delivery Adapter (Email/Notion)
```

**Ví dụ**:
```python
# Core service không biết về infrastructure
class SummarizerService:
    def __init__(self, llm_client: LLMClientInterface):
        self.llm = llm_client  # Dependency injection
    
    def summarize(self, paper: Paper) -> Summary:
        prompt = self._build_prompt(paper.abstract)
        response = self.llm.generate(prompt)
        return self._parse_response(response)

# Adapter cho Gemini
class GeminiAdapter(LLMClientInterface):
    def generate(self, prompt: str) -> str:
        # Implementation-specific code
        pass
```

---

### 2. Repository Pattern

**Purpose**: Abstract database operations.

```python
# Abstract interface
class PaperRepository(ABC):
    @abstractmethod
    async def save(self, paper: Paper) -> Paper:
        pass
    
    @abstractmethod
    async def find_by_fingerprint(self, fingerprint: str) -> Optional[Paper]:
        pass

# PostgreSQL implementation
class PostgresPaperRepository(PaperRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save(self, paper: Paper) -> Paper:
        self.session.add(paper)
        await self.session.commit()
        return paper
```

---

### 3. Service Layer Pattern

**Purpose**: Encapsulate business logic.

```python
class IngestionService:
    def __init__(
        self,
        paper_repo: PaperRepository,
        analyzer: AnalyzerService,
        summarizer: SummarizerService
    ):
        self.paper_repo = paper_repo
        self.analyzer = analyzer
        self.summarizer = summarizer
    
    async def process_paper(self, raw_paper: dict) -> Optional[Paper]:
        # Orchestrate business logic
        paper = Paper.from_dict(raw_paper)
        
        if await self._is_duplicate(paper):
            return None
        
        if not await self.analyzer.is_relevant(paper):
            return None
        
        paper.summary = await self.summarizer.summarize(paper)
        return await self.paper_repo.save(paper)
```

---

### 4. Factory Pattern

**Purpose**: Object creation logic.

```python
class IngestionFactory:
    @staticmethod
    def create_ingestion_engine(source_type: str) -> IngestionEngine:
        if source_type == "rss":
            return RSSCollector()
        elif source_type == "keyword":
            return APISearcher()
        else:
            raise ValueError(f"Unknown source type: {source_type}")
```

---

## Code Style Guidelines

### General Python Style
- **Follow**: PEP 8
- **Linter**: `ruff` (replaces flake8, isort, black)
- **Type Hints**: Required for all public functions
- **Docstrings**: Google style

```python
def calculate_relevance(paper: Paper, topic: Topic) -> float:
    """Calculate relevance score between paper and topic.
    
    Args:
        paper: The paper to evaluate
        topic: The topic to compare against
        
    Returns:
        Relevance score between 0 and 10
        
    Raises:
        ValueError: If paper.abstract is empty
    """
    if not paper.abstract:
        raise ValueError("Paper must have abstract")
    
    # Implementation...
    return score
```

---

### Async/Await Conventions
- **Database operations**: Always async
- **External API calls**: Always async
- **LLM calls**: Can be sync (if using sync SDK) but wrap in `asyncio.to_thread()`

```python
# Good
async def fetch_papers(source: Source) -> List[Paper]:
    async with httpx.AsyncClient() as client:
        response = await client.get(source.url)
    return parse_papers(response)

# Avoid blocking I/O in async functions
async def bad_example():
    papers = requests.get(url)  # ❌ Blocks event loop
```

---

### Error Handling
- **Custom Exceptions**: Inherit from base `ResearchAssistantException`
- **Logging**: Use structured logs

```python
# Custom exceptions
class IngestionError(ResearchAssistantException):
    """Raised when ingestion fails"""

# Usage
try:
    papers = await searcher.search(query)
except RateLimitError as e:
    logger.warning("rate_limit_exceeded", query=query, error=str(e))
    await asyncio.sleep(60)
    papers = await searcher.search(query)
```

---

### Configuration Management
- **Environment Variables**: Use `.env` file (12-factor app)
- **Validation**: Pydantic Settings

```python
# src/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str
    vector_db_url: str = "http://localhost:6333"  # Default
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Testing Strategy

### Test Pyramid
```
        ┌─────────┐
        │   E2E   │  (5%)
        ├─────────┤
        │Integration│ (15%)
        ├─────────┤
        │   Unit    │ (80%)
        └─────────┘
```

### Unit Tests
- **Coverage Target**: 80%+
- **Framework**: pytest + pytest-asyncio
- **Mocking**: pytest-mock, unittest.mock

```python
# tests/unit/test_analyzer.py
import pytest
from src.services.analyzer import AnalyzerService

@pytest.fixture
def analyzer(mock_llm_client):
    return AnalyzerService(llm_client=mock_llm_client)

@pytest.mark.asyncio
async def test_relevance_high_score(analyzer, sample_paper):
    # Mock LLM response
    analyzer.llm.generate.return_value = '{"score": 9.5, "reasoning": "..."}'
    
    result = await analyzer.is_relevant(sample_paper)
    
    assert result is True
    analyzer.llm.generate.assert_called_once()
```

---

### Integration Tests
- **Database**: Use test DB (Docker testcontainers)
- **External APIs**: Mock with `responses` or VCR.py

```python
# tests/integration/test_ingestion_flow.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.mark.integration
async def test_full_ingestion_flow(postgres_container):
    # Setup DB
    db_url = postgres_container.get_connection_url()
    
    # Run flow
    service = IngestionService(db_url=db_url)
    result = await service.process_source(source_id)
    
    # Assert
    assert result.papers_added > 0
```

---

### Test Commands
```bash
# Run all tests
poetry run pytest

# Unit only
poetry run pytest tests/unit

# With coverage
poetry run pytest --cov=src --cov-report=html

# Watch mode (for TDD)
poetry run ptw
```

---

## Running the Application

### Local Development

```bash
# 1. Install dependencies
poetry install

# 2. Setup environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start services (DB, Redis)
docker-compose up -d postgres redis qdrant

# 4. Run migrations
poetry run alembic upgrade head

# 5. Start API server
poetry run uvicorn src.api.main:app --reload

# 6. Start Celery worker (another terminal)
poetry run celery -A src.workers.celery_app worker --loglevel=info
```

---

### Docker Deployment

```bash
# Build and run all services
docker-compose up --build

# Services will be available:
# - API: http://localhost:8000
# - Postgres: localhost:5432
# - Qdrant: http://localhost:6333
# - Redis: localhost:6379
```

---

### CLI Usage

```bash
# Add a source
poetry run python -m src.cli add-source \
    --type keyword \
    --value "Network Intrusion Detection" \
    --schedule daily

# Generate report
poetry run python -m src.cli generate-report \
    --topic-id <uuid> \
    --days 7

# Seed database with sample data
poetry run python scripts/seed_db.py
```

---

## API Endpoints

### Sources
- `POST /api/v1/sources` - Create source
- `GET /api/v1/sources` - List sources
- `PUT /api/v1/sources/{id}` - Update source
- `DELETE /api/v1/sources/{id}` - Delete source

### Papers
- `GET /api/v1/papers` - List papers (with filters)
- `GET /api/v1/papers/{id}` - Get paper details
- `GET /api/v1/papers/{id}/similar` - Find similar papers

### Reports
- `POST /api/v1/reports/generate` - Generate new report
- `GET /api/v1/reports` - List reports
- `GET /api/v1/reports/{id}` - Get report content

---

## Common Development Tasks

### Adding a New LLM Provider

1. Create adapter in `src/adapters/llm.py`
2. Implement `LLMClientInterface`
3. Add factory method
4. Update config
5. Write tests

### Adding a New Data Source

1. Create collector/searcher in `src/services/ingestion/`
2. Implement parsing logic
3. Update `IngestionFactory`
4. Add integration test
5. Document in README

### Database Schema Change

1. Create migration
   ```bash
   poetry run alembic revision -m "add_feedback_table"
   ```
2. Edit migration file in `migrations/versions/`
3. Apply migration
   ```bash
   poetry run alembic upgrade head
   ```
4. Update models in `src/core/models.py`

---

## Monitoring & Debugging

### Logging

```python
from src.utils.logger import logger

logger.info("paper_ingested", paper_id=paper.id, source=source.type)
logger.error("llm_call_failed", error=str(e), retry_count=3)
```

### Metrics (Prometheus)

```python
from prometheus_client import Counter, Histogram

papers_ingested = Counter('papers_ingested_total', 'Total papers ingested')
llm_latency = Histogram('llm_call_duration_seconds', 'LLM call duration')

with llm_latency.time():
    result = await llm.generate(prompt)
papers_ingested.inc()
```

---

## Best Practices

### 1. Dependency Injection
✅ **Good**: Inject dependencies via constructor
```python
class ReportService:
    def __init__(self, clusterer: ClustererService, writer: WriterService):
        self.clusterer = clusterer
        self.writer = writer
```

❌ **Bad**: Direct instantiation
```python
class ReportService:
    def __init__(self):
        self.clusterer = ClustererService()  # Hard-coded dependency
```

### 2. Configuration
✅ **Good**: Environment variables
```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
```

❌ **Bad**: Hardcoded secrets
```python
GEMINI_API_KEY = "AIza..."  # Never commit secrets!
```

### 3. Error Handling
✅ **Good**: Specific exceptions + logging
```python
try:
    result = await external_api.call()
except RateLimitError:
    logger.warning("rate_limited")
    await asyncio.sleep(60)
except Exception as e:
    logger.exception("unexpected_error")
    raise
```

❌ **Bad**: Silent failures
```python
try:
    result = await external_api.call()
except:
    pass  # ❌ Swallows all errors
```

---

## Migration Path (MVP → Production)

### Phase 1: MVP (1-2 weeks)
- ✅ Core services (Planner, Ingestion, Analyzer, Summarizer)
- ✅ SQLite database
- ✅ CLI interface
- ✅ Basic testing

### Phase 2: API (1 week)
- ✅ FastAPI endpoints
- ✅ JWT authentication
- ✅ Swagger documentation

### Phase 3: Async Processing (1 week)
- ✅ Celery workers
- ✅ Redis queue
- ✅ Scheduled tasks

### Phase 4: Production Ready (2 weeks)
- ✅ PostgreSQL migration
- ✅ Docker deployment
- ✅ Monitoring & logging
- ✅ CI/CD pipeline
