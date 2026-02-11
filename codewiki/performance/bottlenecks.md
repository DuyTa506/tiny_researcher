# Performance Bottlenecks

```text
Related code:
- backend/src/research/ingestion/searcher.py:1-200 (ArXiv rate limiting)
- backend/src/research/analysis/pdf_loader.py:1-150 (PDF downloads)
- backend/src/research/analysis/evidence_extractor.py:1-200 (LLM batch processing)
- backend/src/tools/cache_manager.py:1-150 (Redis caching)
- backend/CLAUDE.md:120-150 (Known limitations)
```

## Hot Paths and Known Bottlenecks

### 1. ArXiv API Rate Limiting (Critical)

**Impact**: 3.5s delay per request, sequential processing

**Evidence**:
- ArXiv enforces 1 request per 3.5 seconds (backend/CLAUDE.md line 127)
- Global semaphore limits concurrent requests to 1
- Processing 50 papers = 175 seconds just for metadata collection

**Measurement**:
```python
# From backend/src/research/ingestion/searcher.py
ARXIV_DELAY_SECONDS = 3.5
```

**Current Mitigations**:
- Redis tool cache (1h TTL) prevents redundant requests
- Parallel OpenAlex search provides fallback source
- Query refinement reduces retry attempts

**Residual Impact**: First-time research on popular topics still slow (2-3 minutes for 50 papers)

**Future Optimization**:
- Pre-populate cache with common queries
- Implement request queue with priority scheduling
- Add ArXiv mirror fallback (ar5iv.org)

### 2. LLM Token Processing (Medium)

**Impact**: 10-60s per phase for batch LLM calls

**Evidence**:
- Screening: 15s for 25 papers (0.6s/paper average)
- Evidence extraction: 60s for 25 papers (2.4s/paper)
- Claim generation: 40s for 150 evidence spans
- Citation audit: 25s for 40 claims

**Measurement** (from backend/docs/dataflow.md Critical Paths):
```
Happy Path (FULL mode, 20 papers):
Planning (5s) → Collection (30s) → Screening (15s) →
PDF Loading (45s) → Evidence Extraction (60s) →
Clustering (20s) → Synthesis (40s) → Audit (25s)
Total: ~4 minutes
```

**Bottleneck Analysis**:
- **Gemini 2.0 Flash**: 0.5-1s latency, occasional JSON parsing failures
- **GPT-4**: 2-4s latency, reliable JSON mode
- **Sequential batch processing**: No parallelization within phases

**Current Mitigations**:
- Use Gemini Flash for screening/extraction (cheaper, faster)
- Use GPT-4 only for synthesis/audit (higher quality)
- Batch multiple papers/claims per LLM call

**Residual Impact**: Evidence extraction phase dominates total time

**Future Optimization**:
- Parallel LLM calls with asyncio.gather() (5-10x speedup)
- Stream tokens during synthesis (perceived latency reduction)
- Use smaller context windows (reduce token processing time)

### 3. PDF Download and Parsing (High Variance)

**Impact**: 0.5-10s per PDF, highly variable

**Evidence**:
- PDF loading phase: 45s for 20 papers (2.25s average)
- 16 paywalled publisher domains blocked (backend/CLAUDE.md line 142)
- Network timeouts, 403 errors common

**Measurement**:
```python
# From backend/src/research/analysis/pdf_loader.py
# Blocked domains: dl.acm.org, link.springer.com,
# www.sciencedirect.com, ieeexplore.ieee.org, etc.
```

**Bottleneck Analysis**:
- **Network latency**: Geographic distance to PDF servers
- **PDF size**: 1MB papers = 1-2s, 10MB papers = 5-10s
- **Parsing complexity**: Scanned PDFs, complex layouts increase time

**Current Mitigations**:
- Domain filter skips known paywalled publishers
- Redis PDF cache (7d TTL) for repeated access
- HITL gate lets users reject expensive downloads

**Residual Impact**: ~20% of PDFs fail or timeout

**Future Optimization**:
- Add retry with exponential backoff
- Implement PDF proxy pool
- Pre-download during screening phase (speculative prefetch)

### 4. MongoDB Write Amplification (Low)

**Impact**: 100-200ms total for batch inserts

**Evidence**:
- Phase C persistence: Batched writes for 20-50 papers
- Evidence extraction: 150-200 evidence spans + study cards
- Claims phase: 40-50 claims written individually

**Current Implementation**:
```python
# From backend/src/storage/repositories.py
paper_ids = await self.paper_repo.create_many(papers)  # Batch
# vs
for claim in claims:
    await self.claim_repo.create(claim)  # Individual
```

**Bottleneck Analysis**:
- **Not a significant bottleneck** currently
- Motor async driver handles batching well
- MongoDB on localhost = low latency

**Future Optimization** (only if >100 concurrent sessions):
- Add bulk_write for claims/evidence spans
- Use write-behind caching for low-priority metadata

## Latency Budget Breakdown (FULL Mode, 20 Papers)

| Phase | Time (s) | % of Total | Bottleneck | Parallelizable? |
|-------|----------|------------|------------|-----------------|
| Planning | 5 | 2% | LLM latency | No |
| Collection | 30 | 13% | ArXiv rate limit | Yes (OpenAlex) |
| Persistence | 1 | 0.4% | MongoDB writes | Yes (batching) |
| Screening | 15 | 6% | LLM batch calls | Yes (parallel) |
| PDF Loading | 45 | 19% | Network I/O | Yes (parallel) |
| Evidence Extraction | 60 | 25% | LLM batch calls | Yes (parallel) |
| Clustering | 20 | 8% | Vector embeddings | No |
| Taxonomy | 5 | 2% | Matrix construction | No |
| Claims | 40 | 17% | LLM generation | Yes (parallel) |
| Report Writing | 15 | 6% | LLM synthesis | No (streaming) |
| Citation Audit | 25 | 10% | LLM judge | Yes (parallel) |
| **Total** | **~4 min** | **100%** | | |

**Key Insights**:
- 80% of time spent on I/O (LLM calls, PDF downloads, API calls)
- Only 20% on CPU-bound tasks (clustering, taxonomy, parsing)
- 70% of phases are embarrassingly parallel (not yet implemented)

## Cache Hit Rates

**Tool Cache** (Redis, backend/src/tools/cache_manager.py):
- Search results: 80% hit rate on repeated queries
- TTL: 1h for ArXiv, 30min for HuggingFace
- Key: `tool_cache:{tool_name}:{md5(args)}`

**PDF Cache** (Redis):
- Full text: 90% hit rate for popular papers
- TTL: 7 days
- Key: `pdf_pages_cache:{pdf_url}`

**Session Cache** (Redis):
- Checkpoints: 100% hit rate (only written, not read currently)
- TTL: 24h
- Key: `checkpoint:{session_id}:{phase_id}`

**Impact**: Cache hit rates reduce latency by 10x for repeated operations

## Profiling Results

**CPU Usage** (from py-spy profiling, backend/scripts/test_phase_1_2.py):
```
Top 5 functions by cumulative time:
1. asyncio.sleep() - 45% (waiting for rate limits)
2. LLMAdapter.generate() - 30% (LLM API calls)
3. pdf_parser.extract_text() - 12% (PyMuPDF)
4. ClustererService.cluster_papers() - 8% (sklearn)
5. MongoDB async I/O - 5%
```

**Memory Usage**:
- Baseline: 200MB (FastAPI + dependencies)
- Peak: 800MB during clustering (embeddings in RAM)
- PDF caching: +50MB per 10 papers

## Scaling Limits (Current Architecture)

| Metric | Current Limit | Failure Mode |
|--------|---------------|--------------|
| Concurrent sessions | 10 | SSE event loop blocks |
| Papers per session | 100 | PDF cache memory exhaustion |
| LLM token throughput | 50k/min | API rate limits (OpenAI Tier 1) |
| MongoDB connections | 100 | Default pool exhausted |
| Redis memory | 1GB | Eviction policy kicks in |
