# Data Flow - Research Assistant

## Pipeline Flow (v2.4)

```mermaid
flowchart TD
    Input([User Request]) --> Planner[PlannerService]
    Planner --> Plan[ResearchPlan]
    
    Plan --> Executor[PlanExecutor]
    
    subgraph Collection["Phase 2: Collection"]
        Executor --> Tool{Tool Registry}
        Tool --> Arxiv[arxiv_search]
        Tool --> HF[hf_trending]
        Tool --> Collect[collect_url]
        Arxiv & HF & Collect --> Raw[Raw Papers]
    end
    
    subgraph Dedup["Deduplication"]
        Raw --> Deduplicator[PaperDeduplicator]
        Deduplicator --> Unique[Unique Papers]
    end
    
    subgraph Persist["Phase 3: Persistence"]
        Unique --> MongoDB[(MongoDB)]
    end
    
    subgraph Analysis["Phase 4: Analysis ✅"]
        MongoDB --> Analyzer[AnalyzerService]
        Analyzer --> Scored[Scored Papers]
    end
    
    subgraph Future["Phase 5-6: TODO"]
        Scored --> Filter{Score >= 8?}
        Filter -->|Yes| PDFLoader[Load Full Text]
        Filter -->|No| Skip[Skip]
        PDFLoader --> Summarizer[SummarizerService]
        Summarizer --> Clusterer[ClustererService]
        Clusterer --> Writer[WriterService]
    end
    
    Writer --> Report([Final Report])
    
    style Analysis fill:#e8f5e9
    style Future fill:#fff3e0
```

## Paper Processing Flow

```
RAW → SCORED → SUMMARIZED → CLUSTERED → REPORTED
 ↑       ↑          ↑           ↑           ↑
 │       │          │           │           │
Collect  Analyze   [TODO]      [TODO]     [TODO]
```

## Full Text Loading Strategy (TODO)

```python
# Only load PDF for high-relevance papers
if paper.relevance_score >= 8:
    pdf_content = await pdf_parser.parse(paper.pdf_url)
    paper.full_text = pdf_content
```

Benefits:
- Save bandwidth (only ~20% of papers)
- Faster pipeline
- Cost effective (less LLM tokens)

## Key Data Structures

### Paper (MongoDB)
```json
{
  "arxiv_id": "2602.04739",
  "title": "...",
  "abstract": "...",
  "pdf_url": "https://arxiv.org/pdf/...",
  "relevance_score": 9,
  "full_text": null,  // TODO: lazy load
  "summary": null,    // TODO: SummarizerService
  "status": "scored"
}
```

### ExecutionProgress
```python
ExecutionProgress(
    total_papers_collected=112,
    unique_papers=99,
    duplicates_removed=13
)
```
