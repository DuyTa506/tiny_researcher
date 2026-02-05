# System Design - Research Assistant

## Architecture (v2.3)

```mermaid
graph TB
    User[User] --> API[FastAPI]
    
    subgraph Core["Core Pipeline"]
        API --> Planner[PlannerService]
        Planner --> Executor[PlanExecutor]
        Executor --> Tools[Tool Registry]
        Executor --> Dedup[PaperDeduplicator]
    end
    
    subgraph Storage["Storage"]
        Dedup --> Repo[Repositories]
        Repo --> MongoDB[(MongoDB)]
    end
    
    subgraph Analysis["Analysis"]
        MongoDB --> Analyzer[AnalyzerService]
        Analyzer --> Summarizer[SummarizerService]
        Summarizer --> Writer[WriterService]
    end
    
    Writer --> Report[Report]
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Database | MongoDB 7 (motor) |
| Cache | Redis 7 |
| API | FastAPI |
| LLM | OpenAI / Gemini |

## Key Features

### PaperDeduplicator
- Level 1: ArXiv ID
- Level 2: Fingerprint (title + author hash)
- Level 3: Title similarity (85%)

### AnalyzerService
- Batch processing (10 papers/batch)
- Abstract-only (no full text)
- Relevance threshold: 7.0

## Collections

| Collection | Description |
|------------|-------------|
| papers | Research papers with scores |
| clusters | Paper groupings by theme |
| reports | Generated reports |
