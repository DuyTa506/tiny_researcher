# Agent Guide - Research Assistant

> Quick reference for AI Agents working on this codebase

## Current State (v2.4)

| Component | Status | Location |
|-----------|--------|----------|
| PlanExecutor | ✅ Working | `src/planner/executor.py` |
| AnalyzerService | ✅ Working | `src/research/analysis/analyzer.py` |
| PaperRepository | ✅ Working | `src/storage/repositories.py` |
| SummarizerService | ⏳ TODO | `src/research/analysis/summarizer.py` |
| WriterService | ⏳ TODO | `src/research/synthesis/writer.py` |

## Project Structure

```
backend/src/
├── core/
│   ├── schema.py         # API schemas
│   ├── models.py         # MongoDB models
│   └── database.py       # MongoDB connection
├── tools/
│   └── builtin/          # arxiv, huggingface, collector
├── planner/
│   ├── executor.py       # PlanExecutor + Deduplicator
│   └── service.py        # PlannerService
├── research/
│   ├── analysis/         # Analyzer, Summarizer
│   ├── synthesis/        # Writer
│   └── pipeline.py       # ResearchPipeline orchestrator
└── storage/
    └── repositories.py   # MongoDB repos
```

## Quick Commands

```bash
# Start MongoDB
docker run -d -p 27017:27017 mongo:7

# Run pipeline
python scripts/test_research_pipeline.py

# Debug analyzer
python scripts/debug_analyzer.py
```

## Key Classes

### ResearchPipeline
```python
from src.research.pipeline import ResearchPipeline
pipeline = ResearchPipeline(llm_client)
result = await pipeline.run_quick("topic")
```

### AnalyzerService
```python
from src.research.analysis.analyzer import AnalyzerService
analyzer = AnalyzerService(llm_client)
relevant, irrelevant = await analyzer.score_and_persist(papers, topic)
```

## Next Implementation Tasks

1. **Full Text Loading** - Load PDF for papers with score >= 8
2. **SummarizerService** - Generate summaries using full text
3. **ClustererService** - Group papers by theme
4. **WriterService** - Generate final report
