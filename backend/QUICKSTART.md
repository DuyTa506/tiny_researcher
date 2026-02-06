# Quick Start Guide - Phase 1-2

## Prerequisites

1. **Python 3.11+**
2. **Docker** (for MongoDB and Redis)
3. **Poetry** (for dependency management)

## Setup

### 1. Start Services

```bash
# Start MongoDB
docker run -d -p 27017:27017 --name mongo mongo:7

# Start Redis
docker run -d -p 6379:6379 --name redis redis:7

# Verify services are running
docker ps
```

### 2. Install Dependencies

```bash
# Activate virtual environment (Windows)
.\venv\Scripts\Activate.ps1

# Or create new venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
poetry install
```

### 3. Configure Environment

```bash
# Copy example env
cp .env.example .env

# Edit .env and add your API keys
# GEMINI_API_KEY=your_key_here
# or
# OPENAI_API_KEY=your_key_here
```

## Running the Pipeline

### Option 1: Use the Test Script

```bash
python scripts/test_phase_1_2.py
```

This will run the full pipeline with:
- ✅ Tool caching (Redis)
- ✅ Memory management (session tracking)
- ✅ Paper collection and deduplication
- ✅ Relevance analysis
- ✅ Selective PDF loading (score ≥ 8)
- ✅ Summarization
- ✅ Clustering
- ✅ Report generation

### Option 2: Use in Your Code

```python
import asyncio
from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest
from src.adapters.llm import GeminiClient  # or OpenAIClient

async def main():
    # Initialize LLM client
    llm = GeminiClient(api_key="your_key")

    # Create pipeline
    pipeline = ResearchPipeline(
        llm_client=llm,
        skip_analysis=False,      # Enable analysis
        skip_synthesis=False      # Enable full pipeline
    )

    # Create request
    request = ResearchRequest(
        topic="Transformer Models in NLP",
        keywords=["transformer", "BERT", "attention"]
    )

    # Run pipeline
    result = await pipeline.run(request)

    # Access results
    print(f"Papers collected: {result.unique_papers}")
    print(f"Relevant papers: {result.relevant_papers}")
    print(f"High-value papers: {result.high_relevance_papers}")
    print(f"Clusters: {result.clusters_created}")
    print(f"Cache hit rate: {result.cache_hit_rate:.1%}")
    print(f"\nReport:\n{result.report_markdown}")

    # Cleanup
    if pipeline.cache_manager:
        await pipeline.cache_manager.close()
    if pipeline.memory_manager:
        await pipeline.memory_manager.close()

asyncio.run(main())
```

## Expected Output

```
INFO - Phase 1: Generating research plan...
INFO - Phase 2: Executing plan (collecting papers)...
INFO - Cache HIT for tool: arxiv_search
INFO - Collected 42 unique papers
INFO - Phase 3: Saving papers to MongoDB...
INFO - Saved 42 papers to MongoDB
INFO - Phase 4: Analyzing relevance...
INFO - Analysis complete: 25 relevant papers
INFO - Phase 5: Loading full text for high-relevance papers...
INFO - Loaded full text for 6 papers
INFO - Phase 6: Generating summaries...
INFO - Generated 25 summaries
INFO - Phase 7: Clustering papers by theme...
INFO - Created 4 clusters
INFO - Phase 8: Generating final report...
INFO - Generated report (12543 chars)
INFO - Pipeline complete in 45.3s

✅ Pipeline completed successfully!

📊 Results:
  - Papers collected: 42
  - Relevant: 25
  - High-value (≥8): 6
  - Clusters: 4
  - Cache hit rate: 45.2%
```

## Understanding the Pipeline

### Phase Flow

```
1. Planning        - LLM generates research steps
2. Execution       - Tools collect papers (cached)
3. Persistence     - Save to MongoDB
4. Analysis        - Score relevance (abstract-only)
5. PDF Loading     - Selective (only score ≥ 8)
6. Summarization   - Structured summaries
7. Clustering      - Group by theme
8. Report Writing  - Markdown report
```

### Memory Checkpoints

The pipeline creates checkpoints at:
- After collection (Phase 3)
- After analysis (Phase 4)
- After summarization (Phase 6)
- After clustering (Phase 7)

You can restore from checkpoints:

```python
memory = ResearchMemoryManager()
await memory.connect()

# Restore from checkpoint
session = await memory.restore_from_checkpoint(
    session_id="abc-123",
    phase_id="analysis"
)
```

## Monitoring

### Check Redis Cache

```bash
# Connect to Redis CLI
docker exec -it redis redis-cli

# Check cache keys
KEYS tool_cache:*

# Get cache stats
INFO stats
```

### Check MongoDB Data

```bash
# Connect to MongoDB
docker exec -it mongo mongosh

# Use database
use research_assistant

# Check collections
show collections

# Query papers
db.papers.find().limit(5)

# Count by relevance
db.papers.countDocuments({relevance_score: {$gte: 8}})
```

## Troubleshooting

### "Redis connection failed"
- **Symptom:** Warning in logs
- **Impact:** Pipeline continues but without caching
- **Fix:** Ensure Redis is running: `docker start redis`

### "MongoDB connection failed"
- **Symptom:** Error and pipeline stops
- **Fix:** Ensure MongoDB is running: `docker start mongo`

### "PDF download failed"
- **Symptom:** Warning for specific papers
- **Impact:** Paper continues without full text
- **Fix:** Check network connectivity, PDF URL validity

### Low cache hit rate
- **Expected:** First run = 0% (nothing cached yet)
- **Expected:** Second run on same topic = 50-80%
- **If always 0%:** Check Redis connection

## Performance Tips

### 1. Use Cache Wisely
```python
# Run same query twice - second run uses cache
result1 = await pipeline.run(request)  # Fresh data
result2 = await pipeline.run(request)  # Cached (much faster!)
```

### 2. Adjust PDF Threshold
```python
# Lower threshold = more PDFs loaded (slower, more detailed)
loader = PDFLoaderService(cache, relevance_threshold=7.0)

# Higher threshold = fewer PDFs (faster, less detailed)
loader = PDFLoaderService(cache, relevance_threshold=9.0)
```

### 3. Skip Synthesis for Speed
```python
# Analysis only (fast)
pipeline = ResearchPipeline(llm, skip_synthesis=True)

# Full pipeline (slower, complete report)
pipeline = ResearchPipeline(llm, skip_synthesis=False)
```

## What's Next?

After Phase 1-2, you can:
1. ✅ Run full research workflows
2. ✅ Get complete Markdown reports
3. ✅ Track sessions with memory manager
4. ✅ Benefit from Redis caching

Next phases will add:
- **Phase 3:** Adaptive planning (simple vs deep queries)
- **Phase 4:** Conversational interface (multi-turn)
- **Phase 5:** Vector search (semantic similarity)

## Resources

- **Full Docs:** `docs/phase_1_2_implementation.md`
- **API Reference:** See `src/research/pipeline.py` docstrings
- **Examples:** `scripts/test_phase_1_2.py`
