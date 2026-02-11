# Architecture Overview

```text
Related code:
- backend/src/research/pipeline.py:148-733
- backend/docs/dataflow.md:1-331
- backend/src/planner/adaptive_planner.py:1-200
- backend/src/storage/repositories.py:1-500
- frontend/src/hooks/useResearchChat.ts:1-400
```

## Design Rationale

The architecture is designed around **three core principles**:

1. **Citation Integrity**: Every claim in the final report must be traceable to specific evidence with page-level locators. This prevents LLM hallucination and ensures academic rigor.

2. **3-Tier Memory**: Hot (in-process) → Warm (Redis) → Cold (MongoDB) balances latency and persistence. Expensive operations (LLM calls, PDF downloads) are cached aggressively.

3. **Async-First Streaming**: SSE (Server-Sent Events) provides real-time pipeline updates without WebSocket complexity. All I/O operations use `async/await` for concurrent processing.

**Why this matters**: Traditional literature review tools either produce unreliable LLM-generated summaries or require manual citation tracking. Tiny Researcher automates the full workflow while enforcing evidence-based claims.

## Component Diagram

```mermaid
C4Container
    title Container Diagram - Tiny Researcher

    Person(researcher, "Researcher")

    Container_Boundary(frontend_boundary, "Frontend") {
        Container(nextjs, "Next.js App", "React 19, TypeScript", "Interactive research workspace")
        Container(sse_hook, "useResearchChat", "React Hook", "SSE connection manager")
    }

    Container_Boundary(backend_boundary, "Backend") {
        Container(fastapi, "FastAPI", "Python 3.11", "REST API + SSE streaming")
        Container(pipeline, "ResearchPipeline", "Python", "10-phase orchestrator")
        Container(planner, "AdaptivePlannerService", "Python", "Query-aware planning")
        Container(tools, "Search Tools", "Python", "ArXiv + OpenAlex")
    }

    Container_Boundary(data_boundary, "Data Stores") {
        ContainerDb(mongo, "MongoDB", "Motor async", "8 collections (papers, claims, etc.)")
        ContainerDb(redis, "Redis", "aioredis", "Tool cache, PDF cache, sessions")
        ContainerDb(qdrant, "Qdrant", "Vector DB", "Semantic embeddings")
    }

    Rel(researcher, nextjs, "Uses", "HTTPS")
    Rel(nextjs, sse_hook, "Uses")
    Rel(sse_hook, fastapi, "SSE stream", "HTTP/SSE")
    Rel(fastapi, pipeline, "Orchestrates")
    Rel(pipeline, planner, "Plans research")
    Rel(pipeline, tools, "Searches papers")
    Rel(pipeline, mongo, "Persists", "async")
    Rel(pipeline, redis, "Caches", "async")
    Rel(pipeline, qdrant, "Embeds", "HTTP")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

**Key Containers:**

- **Next.js App**: Modern frontend with App Router, React Query for server state, CSS Modules for styling
- **FastAPI**: Async API with 7 routers (auth, papers, reports, conversations, sources, planner, websocket)
- **ResearchPipeline**: Core orchestrator managing 10-phase citation-first workflow
- **MongoDB**: Primary data store with 8 collections (papers, evidence_spans, study_cards, claims, reports, etc.)
- **Redis**: Cache layer with 3 key patterns (tool results, PDF content, sessions)

## Data Flow Diagram

```mermaid
graph TB
    subgraph "Phase B: Planning"
        User[User Topic] --> AdaptivePlanner
        AdaptivePlanner --> QueryType{Query Type?}
        QueryType -->|QUICK| QuickConfig[Skip screening/audit]
        QueryType -->|FULL| FullConfig[All 10 phases]
    end

    subgraph "Phase C: Collection"
        QuickConfig & FullConfig --> PlanExecutor
        PlanExecutor --> ToolRegistry[Search Tool]
        ToolRegistry --> Parallel[Parallel Execution]
        Parallel --> ArXiv[ArXiv API]
        Parallel --> OpenAlex[OpenAlex API]
        ArXiv & OpenAlex --> Dedup[4-Level Dedup]
        Dedup --> MongoDB[(MongoDB)]
    end

    subgraph "Phase D: Screening"
        MongoDB --> Screener[ScreenerService]
        Screener --> LLMBatch[Batch LLM Calls]
        LLMBatch --> Tier{3-Tier Decision}
        Tier -->|core| Included[Included Papers]
        Tier -->|background| Background[Background Papers]
        Tier -->|exclude| Excluded[Excluded Papers]
    end

    subgraph "Phase E-F: Evidence"
        Included --> HITLGate{HITL Approval?}
        HITLGate -->|Approved| PDFLoader[PDFLoaderService]
        PDFLoader --> PDFCache[(Redis PDF Cache)]
        PDFCache --> Extractor[EvidenceExtractorService]
        Extractor --> StudyCards[StudyCards]
        Extractor --> EvidenceSpans[EvidenceSpans + Locators]
    end

    subgraph "Phase G-H: Synthesis"
        EvidenceSpans --> Clusterer[ClustererService]
        StudyCards --> Clusterer
        Clusterer --> Qdrant[(Qdrant)]
        Qdrant --> Clusters[Theme Clusters]
        Clusters --> Taxonomy[TaxonomyBuilder]
        Taxonomy --> ClaimGen[ClaimGeneratorService]
        ClaimGen --> Claims[Atomic Claims]
        Taxonomy --> GapMiner[GapMinerService]
        GapMiner --> Gaps[Future Directions]
        Claims --> Writer[GroundedWriterService]
        Gaps --> Writer
        Writer --> Report[Markdown Report]
    end

    subgraph "Phase I: Audit"
        Report --> Auditor[CitationAuditService]
        Claims --> Auditor
        EvidenceSpans --> Auditor
        Auditor --> LLMJudge[LLM Judge]
        LLMJudge -->|Failed| Repair[Auto-Repair]
        Repair --> LLMJudge
        LLMJudge -->|Passed| PublishedReport[Published Report]
    end

    style Phase B fill:#e3f2fd
    style Phase C fill:#fff9c4
    style Phase D fill:#fff3e0
    style Phase E-F fill:#fce4ec
    style Phase G-H fill:#e8f5e9
    style Phase I fill:#e0f2f1
```

**Critical Paths:**

1. **Happy Path** (FULL mode, 20 papers):
   - Planning (5s) → Collection (30s) → Screening (15s) → PDF Loading (45s) → Evidence Extraction (60s) → Clustering (20s) → Synthesis (40s) → Audit (25s)
   - Total: ~4 minutes

2. **QUICK Mode** (concept check, 5 papers):
   - Planning (3s) → Collection (10s) → Scoring (5s) → Simple Report (5s)
   - Total: ~30 seconds

3. **Error Recovery**:
   - All phases create Redis checkpoints (`checkpoint:{session_id}:{phase_id}`)
   - Pipeline can resume from last checkpoint if interrupted
   - HITL gates allow user to reject/modify before expensive operations

## Deployment View

```mermaid
C4Deployment
    title Deployment - Docker Compose

    Deployment_Node(docker, "Docker Host", "Linux/macOS/Windows") {
        Deployment_Node(nginx_container, "Nginx Container", "Alpine Linux") {
            Container(nginx, "Nginx", "1.25", "Reverse proxy")
        }

        Deployment_Node(frontend_container, "Frontend Container", "Node 18") {
            Container(nextjs_prod, "Next.js", "16.1", "Production build")
        }

        Deployment_Node(backend_container, "Backend Container", "Python 3.11") {
            Container(uvicorn, "Uvicorn", "FastAPI", "ASGI server")
        }

        Deployment_Node(mongo_container, "MongoDB Container", "Mongo 7") {
            ContainerDb(mongo_db, "MongoDB", "7.0", "Primary data store")
        }

        Deployment_Node(redis_container, "Redis Container", "Redis 7") {
            ContainerDb(redis_db, "Redis", "7.0", "Cache layer")
        }
    }

    Rel(nginx, nextjs_prod, "Proxies /", "HTTP")
    Rel(nginx, uvicorn, "Proxies /api/v1", "HTTP")
    Rel(uvicorn, mongo_db, "Persists", "MongoDB protocol")
    Rel(uvicorn, redis_db, "Caches", "Redis protocol")

    UpdateLayoutConfig($c4ShapeInRow="2")
```

**Port Mapping (docker-compose.yml):**
- `nginx`: 80 → Host 80 (main entry point)
- `nextjs`: 3000 → internal
- `backend`: 8000 → internal
- `mongo`: 27017 → Host 27017 (optional external access)
- `redis`: 6379 → Host 6379 (optional external access)

## Tech Debt Notes

### Debt 1: No Horizontal Scaling

**Problem**: All processing happens in-request with SSE streaming. No background workers (Celery/RQ). Single FastAPI instance handles all requests.

**Impact**:
- Cannot process >10 concurrent research sessions efficiently
- Long-running pipelines (100+ papers) block other requests

**Mitigation Strategy**:
- Phase 1: Add Redis-backed job queue with Celery workers
- Phase 2: Distribute PDF loading and LLM calls across worker pool
- Phase 3: Stateless pipeline orchestration with event sourcing

**Estimated Effort**: 2-3 weeks

### Debt 2: No Vector Search for Deduplication

**Problem**: Current deduplication uses DOI → fingerprint → title similarity. Semantically similar papers with different titles slip through.

**Impact**:
- ~5% duplicate papers in final report
- Wasted LLM tokens on redundant evidence extraction

**Mitigation Strategy**:
- Add Qdrant-based semantic deduplication after fingerprint matching
- Generate embeddings for all paper abstracts
- Cluster with cosine similarity >0.9 threshold
- Keep only highest-relevance paper from each cluster

**Estimated Effort**: 1 week

### Debt 3: Frontend SSE Reconnection

**Problem**: `useResearchChat` hook doesn't implement exponential backoff reconnection. If SSE connection drops, user must refresh page.

**Impact**:
- Poor UX during network interruptions
- Lost progress updates (though pipeline continues server-side)

**Mitigation Strategy**:
- Add retry logic with exponential backoff (1s, 2s, 4s, 8s, 16s max)
- Implement last-event-id tracking for resume
- Show toast notification during reconnection attempts

**Estimated Effort**: 2 days
