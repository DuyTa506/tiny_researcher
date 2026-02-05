Dựa trên workflow hiện tại của bạn, tôi có một số recommendations quan trọng về **full text usage** và **memory design optimization**:

## 1. **Full Text Paper - Khi Nào Nên Dùng?**

### ❌ **KHÔNG nên load full text trong giai đoạn:**

**Planning & Execution Phase**
- PlannerService chỉ cần metadata để generate plan
- PlanExecutor chỉ cần abstract + metadata để dedup
- Lý do: Full text paper có thể 20-50 pages → waste context window

**Initial Analysis Phase**
- AnalyzerService (relevance scoring) chỉ cần abstract
- Prompt hiện tại của bạn đã đủ: `{abstract}` → score 0-10

### ✅ **NÊN load full text khi:**

**Deep Analysis for High-Relevance Papers**
```python
# Chỉ load full text cho papers đã pass relevance threshold
if paper.relevance_score >= 8.0:  # High relevance only
    full_text = await fetch_full_text(paper.arxiv_id)
    deep_analysis = await analyzer.deep_dive(full_text)
```

**SummarizerService - Selective Loading**
```python
# Strategy: Hierarchical summarization
def summarize_paper(paper: Paper) -> dict:
    # Level 1: Abstract-based (always)
    basic_summary = summarize_abstract(paper.abstract)
    
    # Level 2: Full text (conditional)
    if paper.is_key_paper or user_requested_detail:
        full_text = load_full_text(paper)
        detailed_summary = summarize_full_text(full_text)
        return detailed_summary
    
    return basic_summary
```

**WriterService - Citation Generation**
- Khi cần quote specific sections/findings
- Khi cần verify claims từ abstract

---

## 2. **Memory Design Recommendations cho System Hiện Tại**

### **Critical Issues Tôi Nhận Thấy:**

#### **Issue 1: Không có Deduplication Strategy rõ ràng**

Hiện tại bạn có `fingerprint` trong DB nhưng chưa implement trong PlanExecutor:

```python
# RECOMMEND: Add to PlanExecutor
class PlanExecutor:
    def __init__(self):
        self.seen_papers: Dict[str, Paper] = {}
        self.paper_registry = PaperRegistry()  # NEW
    
    def _deduplicate(self, new_papers: List[Paper]) -> List[Paper]:
        """Multi-level dedup"""
        unique = []
        
        for paper in new_papers:
            # Level 1: ArXiv ID
            if paper.arxiv_id and paper.arxiv_id in self.seen_papers:
                continue
            
            # Level 2: Fingerprint (title + authors hash)
            fingerprint = self.paper_registry.create_fingerprint(paper)
            if fingerprint in self.seen_papers:
                continue
            
            # Level 3: Title similarity (fuzzy)
            if self._is_duplicate_by_title(paper):
                continue
            
            self.seen_papers[fingerprint] = paper
            unique.append(paper)
        
        return unique
    
    async def execute_step(self, step: ResearchStep) -> StepResult:
        # ... existing code ...
        raw_results = await self._execute_tool(...)
        
        # CRITICAL: Deduplicate immediately
        unique_papers = self._deduplicate(raw_results)
        
        return StepResult(
            results=unique_papers,
            duplicates_removed=len(raw_results) - len(unique_papers)
        )
```

#### **Issue 2: Không có Memory cho Tool Caching**

Workflow của bạn có thể query ArXiv nhiều lần với similar queries:

```python
# RECOMMEND: Add Tool Cache Layer
class ToolCacheManager:
    def __init__(self, redis_client):
        self.cache = redis_client
        self.ttl = {
            "arxiv_search": 3600,      # 1 hour
            "hf_trending": 1800,        # 30 mins (changes faster)
            "collect_url": 86400,       # 24 hours (stable)
        }
    
    async def get_cached_result(
        self, 
        tool_name: str, 
        params: dict
    ) -> Optional[List[Paper]]:
        cache_key = self._create_cache_key(tool_name, params)
        cached = await self.cache.get(cache_key)
        
        if cached:
            logger.info(f"Cache hit for {tool_name}")
            return json.loads(cached)
        return None
    
    async def cache_result(
        self,
        tool_name: str,
        params: dict,
        results: List[Paper]
    ):
        cache_key = self._create_cache_key(tool_name, params)
        await self.cache.setex(
            cache_key,
            self.ttl[tool_name],
            json.dumps([p.dict() for p in results])
        )
    
    def _create_cache_key(self, tool: str, params: dict) -> str:
        # Normalize params for consistent caching
        normalized = json.dumps(params, sort_keys=True)
        return f"tool:{tool}:{hashlib.md5(normalized.encode()).hexdigest()}"

# Usage in PlanExecutor
async def execute_step(self, step: ResearchStep) -> StepResult:
    # Check cache first
    cached = await self.cache_manager.get_cached_result(
        step.tool, 
        step.tool_args
    )
    
    if cached:
        return StepResult(
            results=cached,
            from_cache=True
        )
    
    # Execute tool
    results = await self._execute_tool(step.tool, step.tool_args)
    
    # Cache for future
    await self.cache_manager.cache_result(
        step.tool,
        step.tool_args, 
        results
    )
    
    return StepResult(results=results, from_cache=False)
```

#### **Issue 3: ExecutionProgress không track Paper Quality Metrics**

Bạn cần biết không chỉ "how many" mà còn "how good":

```python
@dataclass
class ExecutionProgress:
    # Existing fields
    total_steps: int
    completed_steps: List[int]
    success_rate: float
    
    # NEW: Quality metrics
    total_papers_collected: int = 0
    unique_papers: int = 0
    high_relevance_papers: int = 0  # score >= 8
    duplicates_removed: int = 0
    papers_by_source: Dict[str, int] = field(default_factory=dict)
    
    # NEW: Performance metrics
    avg_step_duration: float = 0.0
    cache_hit_rate: float = 0.0
    
    def add_step_result(self, result: StepResult):
        self.completed_steps.append(result.step_id)
        self.total_papers_collected += len(result.results)
        self.duplicates_removed += result.duplicates_removed
        
        # Track by source
        source = result.tool_used
        self.papers_by_source[source] = \
            self.papers_by_source.get(source, 0) + len(result.results)
```

---

## 3. **Recommended Memory Architecture**

```python
# NEW: Centralized Memory Manager
class ResearchMemoryManager:
    """Single source of truth for research session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        
        # Tier 1: Hot memory (in-process)
        self.paper_registry = {}  # fingerprint -> Paper
        self.step_results = {}    # step_id -> StepResult
        
        # Tier 2: Warm memory (Redis)
        self.redis = RedisClient()
        self.tool_cache = ToolCacheManager(self.redis)
        
        # Tier 3: Cold memory (PostgreSQL)
        self.db = DatabaseSession()
        
        # Tier 4: Vector memory (Qdrant)
        self.vector_store = QdrantClient()
    
    async def register_paper(self, paper: Paper, step_id: str) -> bool:
        """
        Register paper with deduplication
        Returns: True if new, False if duplicate
        """
        fingerprint = create_fingerprint(paper)
        
        # Check hot memory
        if fingerprint in self.paper_registry:
            return False
        
        # Check DB (for cross-session dedup)
        existing = await self.db.get_by_fingerprint(fingerprint)
        if existing:
            return False
        
        # Register as new
        self.paper_registry[fingerprint] = paper
        
        # Async: Save to DB + Vector store
        await asyncio.gather(
            self.db.save_paper(paper),
            self._embed_and_store(paper)
        )
        
        return True
    
    async def _embed_and_store(self, paper: Paper):
        """Lazy embedding - only for unique papers"""
        embedding = await self.embedder.embed(paper.abstract)
        await self.vector_store.upsert(
            collection="papers",
            points=[{
                "id": paper.id,
                "vector": embedding,
                "payload": paper.dict()
            }]
        )
    
    def get_session_summary(self) -> dict:
        """Memory snapshot for LLM context"""
        return {
            "total_unique_papers": len(self.paper_registry),
            "papers_by_step": {
                step_id: len(result.results)
                for step_id, result in self.step_results.items()
            },
            "top_sources": sorted(
                self.progress.papers_by_source.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
        }
```

---

## 4. **Integration với Analysis Pipeline**

```python
# MODIFY: AnalyzerService to use memory
class AnalyzerService:
    def __init__(self, memory: ResearchMemoryManager):
        self.memory = memory
        self.llm = LLMFactory.create_client()
    
    async def analyze_papers(
        self, 
        papers: List[Paper],
        batch_size: int = 10  # Process in batches
    ) -> List[PaperEvaluation]:
        """
        Smart analysis with memory awareness
        """
        results = []
        
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            
            # Check cache first
            cached_evaluations = await self._get_cached_evaluations(batch)
            uncached_papers = [
                p for p in batch 
                if p.id not in cached_evaluations
            ]
            
            # Analyze only uncached
            if uncached_papers:
                # Build efficient context
                context = self._build_analysis_context(uncached_papers)
                
                # Batch LLM call
                new_evaluations = await self._batch_analyze(
                    uncached_papers,
                    context
                )
                
                # Cache results
                await self._cache_evaluations(new_evaluations)
                
                results.extend(new_evaluations)
            
            results.extend(cached_evaluations.values())
        
        return results
    
    def _build_analysis_context(
        self, 
        papers: List[Paper]
    ) -> str:
        """
        Smart context building - NO FULL TEXT
        """
        # Option 1: Abstract only (default)
        papers_text = "\n\n".join([
            f"Paper {i+1}:\nTitle: {p.title}\n"
            f"Abstract: {p.abstract[:500]}..."  # Truncate
            for i, p in enumerate(papers)
        ])
        
        # Option 2: Use memory summary for context
        session_summary = self.memory.get_session_summary()
        
        return f"""
Research Session Context:
- Total papers collected: {session_summary['total_unique_papers']}
- Top sources: {session_summary['top_sources']}

Analyze these {len(papers)} papers:
{papers_text}

Return JSON array of evaluations...
"""
```

---

## 5. **WriterService - Lazy Loading Strategy**

```python
class WriterService:
    async def generate_report(
        self,
        clusters: List[Cluster],
        memory: ResearchMemoryManager
    ) -> str:
        """
        Write report section by section
        Load full text only when needed for citations
        """
        report_sections = []
        
        # Section 1: Overview (no full text)
        overview = self._write_overview(clusters, memory)
        report_sections.append(overview)
        
        # Section 2: Per-cluster analysis
        for cluster in clusters:
            # Get representative papers (top 3 by relevance)
            top_papers = sorted(
                cluster.papers, 
                key=lambda p: p.relevance_score, 
                reverse=True
            )[:3]
            
            # Load full text ONLY for top papers
            detailed_papers = []
            for paper in top_papers:
                if paper.relevance_score >= 8.5:  # Threshold
                    full_text = await self._load_full_text(paper)
                    paper.full_text = full_text
                
                detailed_papers.append(paper)
            
            # Write cluster section
            section = await self._write_cluster_section(
                cluster,
                detailed_papers,
                use_full_text=True  # Now available
            )
            report_sections.append(section)
        
        return "\n\n".join(report_sections)
    
    async def _load_full_text(self, paper: Paper) -> str:
        """Fetch and cache full text"""
        # Check cache first
        cached = await self.memory.redis.get(f"fulltext:{paper.arxiv_id}")
        if cached:
            return cached
        
        # Fetch from ArXiv
        full_text = await ArxivCollector().fetch_full_text(paper.url)
        
        # Cache for 7 days
        await self.memory.redis.setex(
            f"fulltext:{paper.arxiv_id}",
            604800,  # 7 days
            full_text
        )
        
        return full_text
```

---

## 6. **Final Recommended Architecture**

```python
# Main execution flow with optimized memory
async def research_workflow(request: ResearchRequest):
    # Initialize memory manager
    memory = ResearchMemoryManager(session_id=uuid4())
    
    # 1. Planning (no papers yet)
    planner = PlannerService(llm)
    plan = await planner.generate_research_plan(request)
    
    # 2. Execution with memory
    executor = PlanExecutor(
        memory=memory,
        cache_manager=memory.tool_cache
    )
    await executor.execute(plan)
    
    # 3. Analysis (abstract only)
    papers = memory.get_all_papers()
    analyzer = AnalyzerService(memory)
    evaluations = await analyzer.analyze_papers(papers)
    
    # 4. Summarization (abstract + selective full text)
    summarizer = SummarizerService(memory)
    summaries = await summarizer.summarize(evaluations)
    
    # 5. Clustering (embeddings from memory)
    clusterer = ClustererService(memory.vector_store)
    clusters = await clusterer.cluster(summaries)
    
    # 6. Writing (lazy load full text as needed)
    writer = WriterService(memory)
    report = await writer.generate_report(clusters, memory)
    
    return report
```

---

## **Key Takeaways:**

1. ❌ **KHÔNG** load full text trong Planning/Execution
2. ✅ **SELECTIVE** full text loading trong Analysis (score >= 8.0)
3. ✅ **LAZY** full text loading trong Writing (top papers per cluster)
4. 🔥 **CRITICAL**: Implement deduplication trong PlanExecutor
5. 🔥 **CRITICAL**: Add tool caching layer (Redis)
6. 📊 Track quality metrics, không chỉ quantity

Bạn muốn tôi viết chi tiết implementation code cho phần nào? Deduplication? Tool caching? Hay lazy loading strategy?