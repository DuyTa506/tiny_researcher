# Data Flow - Research Assistant (v3.0 - Phase 1-2)

## Complete Pipeline Flow

```mermaid
flowchart TD
    Input([User Request]) --> Planner[PlannerService]
    Planner --> Plan[ResearchPlan]

    Plan --> MemInit[ResearchMemoryManager]
    MemInit --> Session[Create Session]

    Session --> Executor[PlanExecutor]

    subgraph Phase2[Phase 2: Collection with Cache]
        Executor --> Cache{Check Cache}
        Cache -->|Hit| Cached[Return Cached]
        Cache -->|Miss| Tool{Tool Registry}
        Tool --> Arxiv[arxiv_search]
        Tool --> HF[hf_trending]
        Tool --> Collect[collect_url]
        Arxiv & HF & Collect --> CacheStore[Store in Cache]
        CacheStore --> Raw[Raw Papers]
        Cached --> Raw
    end

    subgraph Dedup[Deduplication]
        Raw --> Deduplicator[PaperDeduplicator]
        Deduplicator --> Unique[Unique Papers]
    end

    subgraph Phase3[Phase 3: Persistence]
        Unique --> MongoDB[(MongoDB)]
        Unique --> MemReg[Register in Memory]
        MemReg --> Checkpoint1[Checkpoint: collection]
    end

    subgraph Phase4[Phase 4: Analysis]
        MongoDB --> Analyzer[AnalyzerService]
        Analyzer --> Scored[Scored Papers]
        Scored --> UpdateDB[Update Scores in DB]
        UpdateDB --> Checkpoint2[Checkpoint: analysis]
    end

    subgraph Phase5[Phase 5: PDF Loading]
        Scored --> Filter{Score >= 8?}
        Filter -->|Yes| PDFLoader[PDFLoaderService]
        Filter -->|No| Skip[Skip]
        PDFLoader --> PDFCache{Check PDF Cache}
        PDFCache -->|Hit| CachedPDF[Cached PDF]
        PDFCache -->|Miss| Download[Download PDF]
        Download --> StorePDF[Cache PDF 7d]
        CachedPDF & StorePDF --> WithText[Papers with Full Text]
    end

    subgraph Phase6[Phase 6: Summarization]
        WithText & Skip --> Summarizer[SummarizerService]
        Summarizer --> Summaries[Papers with Summaries]
        Summaries --> Checkpoint3[Checkpoint: summarization]
    end

    subgraph Phase7[Phase 7: Clustering]
        Summaries --> Clusterer[ClustererService]
        Clusterer --> Vector[VectorService]
        Vector --> Clusters[Clusters by Theme]
        Clusters --> Checkpoint4[Checkpoint: clustering]
    end

    subgraph Phase8[Phase 8: Writing]
        Clusters --> Writer[WriterService]
        Writer --> Report[Markdown Report]
    end

    Report --> Complete[Session Complete]

    style Phase2 fill:#e3f2fd
    style Phase4 fill:#e8f5e9
    style Phase5 fill:#fff3e0
    style Phase6 fill:#fce4ec
    style Phase7 fill:#f3e5f5
    style Phase8 fill:#e0f2f1
```

## Paper Processing Flow

```
RAW → DEDUPLICATED → PERSISTED → SCORED → LOADED → SUMMARIZED → CLUSTERED → REPORTED
 ↑         ↑            ↑           ↑         ↑          ↑            ↑           ↑
 │         │            │           │         │          │            │           │
Tool    Dedup       MongoDB     Analyzer   PDF      Summarizer   Clusterer   Writer
Cache                                      Loader
(Redis)                                   (Redis)
```

## Data Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                      │
│        (ResearchPipeline orchestrates all phases)        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Memory Management                       │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   Hot    │  │   Warm   │  │   Cold   │             │
│  │In-Process│→ │  Redis   │→ │ MongoDB  │             │
│  │ Registry │  │Sessions  │  │ Papers   │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    Cache Layer                           │
│                                                          │
│  Tool Cache (Redis)          PDF Cache (Redis)          │
│  - TTL: 1h (ArXiv)           - TTL: 7d                  │
│  - TTL: 30m (HF)             - Key: pdf_url             │
│  - Key: tool+args            - Lazy loading             │
└─────────────────────────────────────────────────────────┘
```

## Full Text Loading Strategy

```mermaid
flowchart LR
    Papers[Papers] --> Score{Relevance Score}
    Score -->|Score < 8| NoLoad[Skip PDF]
    Score -->|Score >= 8| CheckCache{PDF in Cache?}

    CheckCache -->|Yes| UseCached[Use Cached Text]
    CheckCache -->|No| Download[Download PDF]

    Download --> Extract[Extract Text]
    Extract --> Store[Cache 7 days]
    Store --> Use[Use Full Text]
    UseCached --> Use

    NoLoad --> Summary1[Summarize from Abstract]
    Use --> Summary2[Summarize from Full Text]

    style NoLoad fill:#ffebee
    style Use fill:#e8f5e9
```

**Benefits:**
- Save bandwidth (only ~20% of papers typically score ≥8)
- Faster pipeline
- Cost effective (less LLM tokens)
- Cached PDFs avoid re-downloads

## Key Data Structures

### Paper (MongoDB)
```json
{
  "arxiv_id": "2602.04739",
  "title": "...",
  "abstract": "...",
  "pdf_url": "https://arxiv.org/pdf/...",
  "relevance_score": 9,
  "full_text": "... (only if score >= 8) ...",
  "summary": {
    "problem": "...",
    "method": "...",
    "result": "...",
    "one_sentence_summary": "..."
  },
  "status": "completed",
  "plan_id": "abc-123",
  "created_at": "2026-02-06T..."
}
```

### ResearchSession (Memory Manager)
```python
{
  "session_id": "abc-123",
  "topic": "Transformer Models",
  "current_phase": "complete",
  "phases_completed": ["planning", "execution", "analysis", ...],
  "total_papers": 42,
  "unique_papers": 42,
  "high_relevance_papers": 8,
  "plan_id": "xyz-789",
  "report_id": "report-456"
}
```

### ExecutionProgress (Enhanced)
```python
{
  "total_papers_collected": 112,
  "unique_papers": 99,
  "duplicates_removed": 13,
  "high_relevance_papers": 20,
  "relevance_bands": {
    "3-5": 45,
    "6-7": 34,
    "8-10": 20
  },
  "cache_hits": 12,
  "cache_misses": 15,
  "cache_hit_rate": 0.444,
  "avg_step_duration": 3.2,
  "total_duration_seconds": 48.5
}
```

### PipelineResult
```python
{
  "session_id": "abc-123",
  "topic": "...",
  "unique_papers": 42,
  "relevant_papers": 25,
  "high_relevance_papers": 8,
  "papers_with_full_text": 8,
  "papers_with_summaries": 25,
  "clusters_created": 4,
  "cache_hit_rate": 0.45,
  "clusters": [...],
  "report_markdown": "# Research Report...",
  "duration_seconds": 45.3
}
```

## Cache Key Patterns

### Tool Cache
```
tool_cache:arxiv_search:<md5(args)>
tool_cache:hf_trending:<md5(args)>
```

### PDF Cache
```
pdf_cache:<pdf_url>
```

### Session Cache
```
session:<session_id>
checkpoint:<session_id>:<phase_id>
```

## Phase Transitions

```
IDLE → PLANNING → EXECUTION → ANALYSIS → SUMMARIZATION → CLUSTERING → WRITING → COMPLETE
  ↑                                                                                  │
  └──────────────────────────────────────────────────────────────────────────────────┘
                           (New research request)
```

Each transition creates a checkpoint in Redis for resume capability.
