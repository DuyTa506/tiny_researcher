# Development Overview

```text
Related code:
- backend/.env.example:1-50
- backend/scripts/test_phase_1_2.py:1-150
- frontend/package.json:1-100
- docker-compose.yml:1-150
```

## Local Development Workflow

### Backend Development

```bash
# 1. Setup
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Start dependencies
docker run -d -p 27017:27017 --name mongo mongo:7
docker run -d -p 6379:6379 --name redis redis:7

# 3. Configure environment
cp .env.example .env
# Edit .env: Add GEMINI_API_KEY or OPENAI_API_KEY

# 4. Run with hot reload
uvicorn src.api.main:app --reload --port 8000

# 5. Test
python scripts/test_phase_1_2.py  # Full pipeline test
pytest tests/  # Unit tests (when available)
```

### Frontend Development

```bash
# 1. Setup
cd frontend
npm install

# 2. Configure API URL (optional)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

# 3. Run dev server
npm run dev

# 4. Test
npm run lint
npm run build  # Check for build errors
```

## Debugging Tips

### Backend Debugging

**1. Enable Debug Logging**

```python
# In backend/src/api/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**2. Inspect MongoDB State**

```bash
# Connect to MongoDB
docker exec -it mongo mongosh

# Switch to database
use research_assistant

# Check paper count and status
db.papers.countDocuments()
db.papers.find({}, {title: 1, status: 1, relevance_score: 1}).limit(10)

# Check evidence spans
db.evidence_spans.countDocuments()
db.evidence_spans.find({}, {snippet: 1, field: 1, confidence: 1}).limit(5)

# Check claims
db.claims.countDocuments()
db.claims.find({}, {claim_text: 1, evidence_span_ids: 1}).limit(5)
```

**3. Inspect Redis Cache**

```bash
# Connect to Redis
docker exec -it redis redis-cli

# Check cached keys
KEYS tool_cache:*
KEYS pdf_pages_cache:*
KEYS session:*

# Inspect tool cache
GET tool_cache:search:<md5_hash>

# Clear cache
FLUSHDB
```

**4. Trace a Research Session**

```bash
# Watch MongoDB insertions in real-time
docker exec -it mongo mongosh

use research_assistant
db.papers.watch()

# In another terminal, run test
python backend/scripts/test_phase_1_2.py
```

**5. Debug LLM Prompts**

```python
# In backend/src/core/prompts.py, add logging
import logging
logger = logging.getLogger(__name__)

def get_screening_prompt(topic, paper_title, abstract):
    prompt = f"..."
    logger.debug(f"SCREENING PROMPT:\n{prompt}")  # Add this line
    return prompt
```

### Frontend Debugging

**1. Monitor SSE Stream**

```typescript
// In frontend/src/hooks/useResearchChat.ts
const connectSSE = (id: string) => {
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    console.log('[SSE] Raw event:', event);  // Add this
    const parsed = JSON.parse(event.data);
    console.log('[SSE] Parsed:', parsed);    // Add this
    // ...
  };
};
```

**2. Inspect React Query Cache**

```bash
# Install React Query Devtools (already in dependencies)
# Open browser DevTools → React Query tab
# View cached queries, mutations, and refetch behavior
```

**3. Debug API Calls**

```typescript
// In frontend/src/services/conversations.ts
export const conversationService = {
  async sendMessage(id: string, content: string) {
    console.log('[API] Sending message:', { id, content });
    const response = await api.post(`/conversations/${id}/messages`, { content });
    console.log('[API] Response:', response.data);
    return response;
  },
};
```

## Common Debugging Scenarios

### Scenario 1: Pipeline Hangs During PDF Loading

**Symptoms**: Progress stops at "Loading full text..." phase

**Debug Steps**:
1. Check backend logs for PDF download errors
2. Verify PDF URLs are accessible: `curl -I <pdf_url>`
3. Check Redis cache: `KEYS pdf_pages_cache:*`
4. Test PDF parser directly:
   ```python
   from src.utils.pdf_parser import extract_text_with_pages
   result = extract_text_with_pages("https://arxiv.org/pdf/2301.00001.pdf")
   print(len(result['full_text']), len(result['page_map']))
   ```

**Common Causes**:
- Paywalled PDFs (403 errors)
- Network timeouts
- Malformed PDF structure

### Scenario 2: SSE Connection Drops

**Symptoms**: Frontend shows "Connection lost" or stops receiving updates

**Debug Steps**:
1. Check browser console for EventSource errors
2. Verify backend is still running: `curl http://localhost:8000/health`
3. Test SSE endpoint directly:
   ```bash
   curl -N http://localhost:8000/api/v1/conversations/<id>/stream
   ```
4. Check for proxy timeouts (Nginx default: 60s)

**Common Causes**:
- Long-running LLM calls exceeding timeout
- Network interruptions
- Backend crash (check logs)

### Scenario 3: LLM Returns Invalid JSON

**Symptoms**: `JSONDecodeError` in backend logs, phase fails

**Debug Steps**:
1. Enable debug logging for LLM responses
2. Check prompt for `json_mode=True` flag
3. Inspect raw LLM response:
   ```python
   # In adapters/llm.py
   result = await self.llm.generate(prompt, json_mode=True)
   logger.debug(f"Raw LLM response: {result}")
   ```
4. Verify prompt includes JSON schema example

**Common Causes**:
- Gemini Flash hallucinating non-JSON responses
- Prompt too complex for JSON mode
- Missing `_JSON_CONTRACT` prefix in prompt

## Test Strategy

### Manual Testing (Current)

**Backend Integration Tests**:
- `backend/scripts/test_phase_1_2.py` - Full 10-phase citation-first pipeline
- `backend/scripts/test_phase_3.py` - Adaptive planning (QUICK vs FULL)
- `backend/scripts/test_openalex.py` - Multi-source search + deduplication

**Running Tests**:
```bash
cd backend
python scripts/test_phase_1_2.py  # Requires LLM API key
```

**Expected Output**:
- Planning: ResearchPlan with 5-10 queries
- Collection: 20-50 papers from ArXiv + OpenAlex
- Screening: Include/exclude decisions with reason codes
- Evidence: StudyCards + EvidenceSpans with page locators
- Synthesis: Grounded Markdown report with citations
- Audit: Citation audit results (pass rate 90%+)

### Unit Testing (Planned)

**Priority Test Targets**:
1. `PaperDeduplicator` - 4-level deduplication logic
2. `TaxonomyBuilder` - Matrix construction from study cards
3. `CitationAuditService` - Claim-evidence matching logic
4. `useResearchChat` - SSE event handling and state updates

**Test Framework**: pytest (backend), Vitest (frontend)

### E2E Testing (Future)

**Playwright Scenarios**:
1. Create research session → View plan → Approve → View report
2. Resume interrupted session from checkpoint
3. Download report as Markdown/HTML
4. Search and filter papers

## Tracing a Request End-to-End

**Example: User submits "transformer architectures"**

```
1. Frontend (useResearchChat)
   → POST /api/v1/conversations
   → conversationId = "abc-123"
   → POST /api/v1/conversations/abc-123/messages { content: "transformer architectures" }

2. Backend (conversation.router)
   → create_message(conversation_id="abc-123", content="...")
   → ResearchRequest(topic="transformer architectures")
   → ResearchPipeline.run(request)

3. Pipeline Execution (with SSE updates)
   → Phase B: AdaptivePlannerService classifies as FULL
   → notify("planning", "Generating research plan...")
     → SSE: event=progress, data={"phase": "planning", "message": "..."}

   → Phase C: PlanExecutor executes search queries
   → notify("execution", "Collecting papers...", papers=25)
     → SSE: event=papers_collected, data={"papers": [...]}

   → Phase D: ScreenerService screens papers
   → notify("screening", "Screening 25 papers...")
     → SSE: event=screening_summary, data={"included": 18, "excluded": 7}

   → Phase F: EvidenceExtractorService extracts evidence
   → notify("evidence_extraction", "Extracting evidence...")
     → SSE: event=evidence, data={"spans": [...], "cards": [...]}

   → Phase H: GroundedWriterService generates report
   → notify("writing", "Generating grounded report...")
     → SSE: event=token_stream, data={"token": "##"} (repeated)

   → Phase I: CitationAuditService audits claims
   → notify("citation_audit", "Auditing citations...")
     → SSE: event=complete, data={"pass_rate": 0.93}

4. Frontend (useResearchChat)
   → Receives 50+ SSE events over 3-4 minutes
   → Updates pipelineStatus, plan, papers, claims, report state
   → Displays final report in MarkdownRenderer
```

## Performance Profiling

**Backend Profiling**:
```bash
# Install profiler
pip install py-spy

# Profile running pipeline
py-spy record -o profile.svg -- python scripts/test_phase_1_2.py

# View flamegraph
open profile.svg
```

**Frontend Profiling**:
```bash
# Use React DevTools Profiler
# 1. Open browser DevTools
# 2. Go to "Profiler" tab
# 3. Click "Record"
# 4. Perform action (e.g., load research session)
# 5. Stop recording
# 6. Analyze component render times
```

## Common Pitfalls

1. **Forgetting to start MongoDB/Redis**: Backend will crash on startup
2. **Wrong Python version**: Requires 3.11+, syntax errors on 3.9
3. **Missing spacy model**: `python -m spacy download en_core_web_sm`
4. **CORS issues**: Ensure `FRONTEND_URL` in backend `.env` matches frontend URL
5. **SSE timeout**: Increase Nginx `proxy_read_timeout` for long pipelines
6. **MongoDB connection pool**: Default max 100 connections, increase for load testing
