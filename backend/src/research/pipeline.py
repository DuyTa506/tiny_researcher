"""
Research Pipeline Orchestrator

Coordinates the full research pipeline:
1. PlanExecutor - collect papers via tools
2. Paper persistence to MongoDB
3. AnalyzerService - score relevance
4. PDFLoaderService - load full text for high-score papers
5. SummarizerService - generate summaries
6. ClustererService - group papers by theme
7. WriterService - generate final report

Phase 3 Addition:
- AdaptivePlannerService - query parsing and phase selection
"""

import logging
from typing import List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from src.core.schema import ResearchRequest, ResearchPlan
from src.core.models import Paper, PaperStatus
from src.core.database import connect_mongodb
from src.planner.service import PlannerService
from src.planner.executor import PlanExecutor, StepStatus
from src.planner.adaptive_planner import AdaptivePlannerService, AdaptivePlan, PhaseConfig
from src.storage.repositories import PaperRepository
from src.research.analysis.analyzer import AnalyzerService
from src.research.analysis.pdf_loader import PDFLoaderService
from src.research.analysis.summarizer import SummarizerService
from src.research.analysis.clusterer import ClustererService, Cluster
from src.research.synthesis.writer import WriterService
from src.storage.vector_store import VectorService
from src.adapters.llm import LLMClientInterface
from src.tools.cache_manager import ToolCacheManager, get_cache_manager
from src.core.memory_manager import ResearchMemoryManager

logger = logging.getLogger(__name__)


# Callback type for progress updates
# Signature: (phase: str, message: str, progress: dict) -> None
ProgressCallback = Callable[[str, str, dict], Awaitable[None]]


@dataclass
class PipelineResult:
    """Result of running the research pipeline."""
    plan_id: str
    topic: str
    session_id: Optional[str] = None

    # Adaptive planning info (Phase 3)
    query_type: Optional[str] = None
    phases_executed: List[str] = field(default_factory=list)

    # Execution stats
    steps_completed: int = 0
    steps_failed: int = 0

    # Paper stats
    total_collected: int = 0
    unique_papers: int = 0
    relevant_papers: int = 0
    high_relevance_papers: int = 0

    # Dedup stats
    duplicates_removed: int = 0

    # Processing stats
    papers_with_full_text: int = 0
    papers_with_summaries: int = 0
    clusters_created: int = 0

    # Cache stats
    cache_hit_rate: float = 0.0

    # Papers & Clusters
    papers: List[Paper] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)

    # Final report
    report_markdown: str = ""

    # Sources used (for memory tracking)
    sources_used: List[str] = field(default_factory=list)

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ResearchPipeline:
    """
    Orchestrates the complete research workflow.

    Usage:
        pipeline = ResearchPipeline(llm)
        result = await pipeline.run(request)

    With adaptive planning (Phase 3):
        pipeline = ResearchPipeline(llm, use_adaptive_planner=True)
        result = await pipeline.run(request)  # Automatically adapts phases
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        skip_analysis: bool = False,
        skip_synthesis: bool = False,
        use_adaptive_planner: bool = False
    ):
        self.llm = llm_client
        self.skip_analysis = skip_analysis
        self.skip_synthesis = skip_synthesis
        self.use_adaptive_planner = use_adaptive_planner

        # Services
        self.planner = PlannerService(llm_client)
        self.adaptive_planner = AdaptivePlannerService(llm_client, self.planner) if use_adaptive_planner else None
        self.paper_repo = PaperRepository()
        self.analyzer = AnalyzerService(llm_client, self.paper_repo)

        # Will be initialized during run
        self.cache_manager: Optional[ToolCacheManager] = None
        self.memory_manager: Optional[ResearchMemoryManager] = None
        self.pdf_loader: Optional[PDFLoaderService] = None
        self.summarizer: Optional[SummarizerService] = None
        self.clusterer: Optional[ClustererService] = None
        self.writer: Optional[WriterService] = None
        self.vector_service: Optional[VectorService] = None
    
    async def run(
        self,
        request: ResearchRequest,
        plan: ResearchPlan = None,
        adaptive_plan: AdaptivePlan = None,
        progress_callback: ProgressCallback = None
    ) -> PipelineResult:
        """
        Run the complete research pipeline.

        Args:
            request: Research request from user
            plan: Optional pre-generated plan (skip planning if provided)
            adaptive_plan: Optional pre-generated adaptive plan (includes phase config)
            progress_callback: Optional async callback for progress updates
        """
        import uuid
        plan_id = str(uuid.uuid4())

        result = PipelineResult(
            plan_id=plan_id,
            topic=request.topic,
            started_at=datetime.now()
        )

        # Helper to notify progress
        async def notify(phase: str, message: str, **kwargs):
            if progress_callback:
                await progress_callback(phase, message, kwargs)

        # Phase configuration (default all on, unless adaptive planning overrides)
        phase_config = PhaseConfig()

        try:
            # --- Initialize Services ---
            await connect_mongodb()

            # Get cache manager
            self.cache_manager = await get_cache_manager()

            # Initialize memory manager
            self.memory_manager = ResearchMemoryManager()
            await self.memory_manager.connect()
            session_id = await self.memory_manager.create_session(
                request.topic,
                plan_id=plan_id
            )
            result.session_id = session_id

            # Initialize synthesis services
            self.pdf_loader = PDFLoaderService(self.cache_manager, relevance_threshold=8.0)
            self.summarizer = SummarizerService(self.llm)
            self.vector_service = VectorService()
            self.clusterer = ClustererService(self.llm, self.vector_service)
            self.writer = WriterService()

            # --- Phase 1: Planning (with optional adaptive planning) ---
            await self.memory_manager.transition_phase(session_id, "planning")
            await notify("planning", "Generating research plan...")

            if adaptive_plan:
                # Use pre-generated adaptive plan
                plan = adaptive_plan.plan
                phase_config = adaptive_plan.phase_config
                result.query_type = adaptive_plan.query_info.query_type.value
                logger.info(f"Using adaptive plan: type={result.query_type}")

            elif self.use_adaptive_planner and self.adaptive_planner and not plan:
                # Generate adaptive plan
                logger.info("Phase 1: Generating adaptive research plan...")
                adaptive_plan = await self.adaptive_planner.create_adaptive_plan(request)
                plan = adaptive_plan.plan
                phase_config = adaptive_plan.phase_config
                result.query_type = adaptive_plan.query_info.query_type.value
                logger.info(
                    f"Adaptive plan created: type={result.query_type}, "
                    f"phases={phase_config.active_phases}"
                )

            elif not plan:
                # Use standard planner
                logger.info("Phase 1: Generating research plan...")
                plan = await self.planner.generate_research_plan(request)

            # Apply legacy skip flags to phase config
            if self.skip_synthesis:
                phase_config.pdf_loading = False
                phase_config.summarization = False
                phase_config.clustering = False
                phase_config.writing = False

            if self.skip_analysis:
                phase_config.analysis = False

            result.phases_executed = phase_config.active_phases
            logger.info(f"Plan: {plan.topic} with {len(plan.steps)} steps")

            # --- Phase 2: Execution (Collection) ---
            await self.memory_manager.transition_phase(session_id, "execution")
            await notify("execution", "Collecting papers from sources...", steps=len(plan.steps))
            logger.info("Phase 2: Executing plan (collecting papers)...")
            executor = PlanExecutor(
                plan_id=plan_id,
                cache_manager=self.cache_manager
            )
            await executor.execute(plan)

            # Get quality metrics
            quality = executor.get_quality_summary()
            result.total_collected = quality.get("total_collected", 0)
            result.unique_papers = quality.get("unique_papers", 0)
            result.duplicates_removed = quality.get("duplicates_removed", 0)
            result.steps_completed = len(executor.progress.completed_steps)
            result.steps_failed = len(executor.progress.failed_steps)
            result.cache_hit_rate = executor.progress.cache_hit_rate

            # Convert to Paper models
            papers = executor.get_papers_as_models()

            # Add metadata
            for paper in papers:
                paper.plan_id = plan_id

            await notify("execution", f"Collected {len(papers)} papers", papers=len(papers))
            logger.info(f"Collected {len(papers)} unique papers")

            # --- Phase 3: Persistence ---
            await notify("persistence", "Saving papers to database...")
            logger.info("Phase 3: Saving papers to MongoDB...")
            if papers:
                paper_ids = await self.paper_repo.create_many(papers)
                logger.info(f"Saved {len(paper_ids)} papers to MongoDB")

                # Update paper IDs
                for paper, pid in zip(papers, paper_ids):
                    paper.id = pid

                # Register papers in memory
                for paper in papers:
                    await self.memory_manager.register_paper(session_id, paper)

            # Checkpoint after collection
            await self.memory_manager.checkpoint(session_id, "collection")

            # --- Phase 4: Analysis ---
            if phase_config.analysis and papers:
                await self.memory_manager.transition_phase(session_id, "analysis")
                await notify("analysis", f"Scoring relevance for {len(papers)} papers...")
                logger.info("Phase 4: Analyzing relevance...")
                relevant, irrelevant = await self.analyzer.score_and_persist(
                    papers,
                    request.topic
                )

                result.relevant_papers = len(relevant)
                result.high_relevance_papers = sum(
                    1 for p in relevant if p.relevance_score and p.relevance_score >= 8.0
                )

                # Update progress with relevance bands
                if executor.progress:
                    for paper in relevant:
                        if paper.relevance_score:
                            if paper.relevance_score >= 8.0:
                                executor.progress.relevance_bands["8-10"] = \
                                    executor.progress.relevance_bands.get("8-10", 0) + 1
                            elif paper.relevance_score >= 6.0:
                                executor.progress.relevance_bands["6-7"] = \
                                    executor.progress.relevance_bands.get("6-7", 0) + 1
                            else:
                                executor.progress.relevance_bands["3-5"] = \
                                    executor.progress.relevance_bands.get("3-5", 0) + 1
                    executor.progress.high_relevance_papers = result.high_relevance_papers

                # Update scores in MongoDB
                for paper in papers:
                    if paper.id and paper.relevance_score:
                        await self.paper_repo.update_score(
                            paper.id,
                            paper.relevance_score
                        )

                logger.info(f"Analysis complete: {len(relevant)} relevant papers")

                # Use relevant papers for synthesis
                papers = relevant

                # Checkpoint after analysis
                await self.memory_manager.checkpoint(session_id, "analysis")
            else:
                result.relevant_papers = len(papers)

            # --- Phase 5: Full Text Loading (Selective) ---
            if phase_config.pdf_loading and papers:
                await notify("pdf_loading", "Loading full text for high-relevance papers...")
                logger.info("Phase 5: Loading full text for high-relevance papers...")
                loaded_count = await self.pdf_loader.load_full_text_batch(papers)
                result.papers_with_full_text = loaded_count
                await notify("pdf_loading", f"Loaded {loaded_count} full texts", loaded=loaded_count)
                logger.info(f"Loaded full text for {loaded_count} papers")

            # --- Phase 6: Summarization ---
            if phase_config.summarization and papers:
                await self.memory_manager.transition_phase(session_id, "summarization")
                await notify("summarization", f"Generating summaries for {len(papers)} papers...")
                logger.info("Phase 6: Generating summaries...")

                summarized_count = 0
                for paper in papers:
                    summary = await self.summarizer.summarize_paper(paper)
                    if summary:
                        paper.summary = summary
                        summarized_count += 1
                        if summarized_count % 5 == 0:
                            await notify("summarization", f"Summarized {summarized_count} papers...", count=summarized_count)

                result.papers_with_summaries = summarized_count
                await notify("summarization", f"Generated {summarized_count} summaries", count=summarized_count)
                logger.info(f"Generated {summarized_count} summaries")

                # Checkpoint after summarization
                await self.memory_manager.checkpoint(session_id, "summarization")

            # --- Phase 7: Clustering ---
            clusters = []
            if phase_config.clustering and papers:
                await self.memory_manager.transition_phase(session_id, "clustering")
                await notify("clustering", "Grouping papers by theme...")
                logger.info("Phase 7: Clustering papers by theme...")

                clusters = await self.clusterer.cluster_papers(papers)
                result.clusters = clusters
                result.clusters_created = len(clusters)

                await notify("clustering", f"Created {len(clusters)} clusters", clusters=len(clusters))
                logger.info(f"Created {len(clusters)} clusters")

                # Checkpoint after clustering
                await self.memory_manager.checkpoint(session_id, "clustering")

            # --- Phase 8: Report Writing ---
            if phase_config.writing and (clusters or papers):
                await self.memory_manager.transition_phase(session_id, "writing")
                await notify("writing", "Generating final report...")
                logger.info("Phase 8: Generating final report...")

                report_markdown = self.writer.format_report_with_papers(
                    clusters if clusters else [],
                    papers,
                    request.topic
                )
                result.report_markdown = report_markdown

                await notify("writing", f"Generated report ({len(report_markdown)} chars)", chars=len(report_markdown))
                logger.info(f"Generated report ({len(report_markdown)} chars)")

            # Final phase
            await self.memory_manager.transition_phase(session_id, "complete")
            await notify("complete", "Research complete!", papers=len(papers), clusters=len(clusters))

            result.papers = papers
            result.completed_at = datetime.now()
            logger.info(f"Pipeline complete in {result.duration_seconds:.1f}s")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            result.completed_at = datetime.now()
            raise

        return result

    async def generate_plan(self, request: ResearchRequest) -> ResearchPlan:
        """
        Step 1 of 2: Generate a research plan for human review.

        Returns the plan WITHOUT executing it. User can review/edit
        the plan, then call execute_plan() to run it.

        Usage:
            # Step 1: Generate plan
            plan = await pipeline.generate_plan(request)
            print(plan.to_display())

            # Step 2: Human reviews and edits
            plan.steps[0].queries.append("BERT attention")

            # Step 3: Execute approved plan
            result = await pipeline.execute_plan(request, plan)
        """
        return await self.planner.generate_research_plan(request)

    async def generate_adaptive_plan(self, request: ResearchRequest) -> AdaptivePlan:
        """
        Step 1 of 2: Generate an adaptive plan for human review.

        Analyzes the query, selects phase template, and generates plan.
        Returns the AdaptivePlan WITHOUT executing. User can review/edit,
        then call execute_plan() to run it.

        Usage:
            # Step 1: Generate adaptive plan
            adaptive_plan = await pipeline.generate_adaptive_plan(request)

            # Review what was detected
            print(f"Query Type: {adaptive_plan.query_info.query_type}")
            print(f"Phases: {adaptive_plan.phase_config.active_phases}")
            print(adaptive_plan.to_display())

            # Step 2: Human can override phase config
            adaptive_plan.phase_config.clustering = True  # Force clustering on

            # Step 3: Execute approved plan
            result = await pipeline.execute_plan(request, adaptive_plan=adaptive_plan)
        """
        if not self.adaptive_planner:
            self.adaptive_planner = AdaptivePlannerService(self.llm, self.planner)

        return await self.adaptive_planner.create_adaptive_plan(request)

    async def execute_plan(
        self,
        request: ResearchRequest,
        plan: ResearchPlan = None,
        adaptive_plan: AdaptivePlan = None,
        progress_callback: ProgressCallback = None
    ) -> PipelineResult:
        """
        Step 2 of 2: Execute a reviewed/approved plan.

        Call this after generate_plan() or generate_adaptive_plan()
        once the human has reviewed and optionally edited the plan.

        Args:
            request: Original research request
            plan: Reviewed ResearchPlan (from generate_plan)
            adaptive_plan: Reviewed AdaptivePlan (from generate_adaptive_plan)
            progress_callback: Optional callback for progress updates

        Returns:
            PipelineResult with collected papers, clusters, report
        """
        return await self.run(request, plan=plan, adaptive_plan=adaptive_plan, progress_callback=progress_callback)

    async def run_quick(self, topic: str) -> PipelineResult:
        """Quick run with minimal options (no review phase)."""
        request = ResearchRequest(topic=topic)
        return await self.run(request)
