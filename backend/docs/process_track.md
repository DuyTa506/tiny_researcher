# Process Track - Research Assistant Backend

> **Ongoing work and issues tracking**

---

## Current Status: ✅ Analysis Pipeline Working

**Last Run Results (2026-02-05):**
- Papers collected: 112
- Unique (dedup): 99
- High relevance (>=7): ~20 papers
- Score range: 3-9

---

## Completed Features ✅

### 1. PlanExecutor + Deduplication ✅
- Multi-level dedup: arxiv_id → fingerprint → title similarity
- Quality metrics tracking

### 2. MongoDB Integration ✅
- Models: Paper, Cluster, Report
- Repositories with async CRUD

### 3. AnalyzerService ✅
- Batch relevance scoring (abstract-only)
- **Bug fixed**: JSON parsing now handles wrapped responses (`{papers:[...]}`)

### 4. Tool Registry ✅
- `arxiv_search`, `arxiv_search_keywords` (fixed query param)
- `hf_trending` (selector broken - HF UI changed)
- `collect_url`

---

## Next Steps (Not Started)

### 1. Full Text Loading for High-Score Papers
```
Score >= 8 → Load PDF → Extract text → Store in paper.full_text
```
- **Location**: SummarizerService or new PDFLoaderService
- **When**: After analysis, before summarization
- **Tool**: `src/utils/pdf_parser.py` (exists)

### 2. SummarizerService Integration
- Generate summaries for relevant papers
- Store in `paper.summary`

### 3. ClustererService Integration
- Group papers by theme
- Create Cluster documents

### 4. WriterService Integration
- Generate final research report

---

## Known Issues

| Issue | Status | Priority |
|-------|--------|----------|
| HF scraper selector broken | Open | Low |
| Qdrant shutdown warning | Ignore | Low |

---

## Test Commands

```bash
# Start MongoDB
docker run -d -p 27017:27017 --name mongo mongo:7

# Run tests
python scripts/test_research_pipeline.py
python scripts/debug_analyzer.py
```

---

## Last Updated
**2026-02-05 16:44** - Analysis pipeline verified working
