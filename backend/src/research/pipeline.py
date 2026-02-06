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
"""

import logging
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.core.schema import ResearchRequest, ResearchPlan
from src.core.models import Paper, PaperStatus
from src.core.database import connect_mongodb
from src.planner.service import PlannerService
from src.planner.executor import PlanExecutor, StepStatus
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


@dataclass
class PipelineResult:
    """Result of running the research pipeline."""
    plan_id: str
    topic: str
    session_id: Optional[str] = None

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
    """
    
    def __init__(
        self,
        llm_client: LLMClientInterface,
        skip_analysis: bool = False,
        skip_synthesis: bool = False
    ):
        self.llm = llm_client
        self.skip_analysis = skip_analysis
        self.skip_synthesis = skip_synthesis

        # Services
        self.planner = PlannerService(llm_client)
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
        plan: ResearchPlan = None
    ) -> PipelineResult:
        """
        Run the complete research pipeline.

        Args:
            request: Research request from user
            plan: Optional pre-generated plan (skip planning if provided)
        """
        import uuid
        plan_id = str(uuid.uuid4())

        result = PipelineResult(
            plan_id=plan_id,
            topic=request.topic,
            started_at=datetime.now()
        )

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

            # --- Phase 1: Planning ---
            await self.memory_manager.transition_phase(session_id, "planning")
            if not plan:
                logger.info("Phase 1: Generating research plan...")
                plan = await self.planner.generate_research_plan(request)

            logger.info(f"Plan: {plan.topic} with {len(plan.steps)} steps")

            # --- Phase 2: Execution (Collection) ---
            await self.memory_manager.transition_phase(session_id, "execution")
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

            logger.info(f"Collected {len(papers)} unique papers")

            # --- Phase 3: Persistence ---
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
            if not self.skip_analysis and papers:
                await self.memory_manager.transition_phase(session_id, "analysis")
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
            if not self.skip_synthesis and papers:
                logger.info("Phase 5: Loading full text for high-relevance papers...")
                loaded_count = await self.pdf_loader.load_full_text_batch(papers)
                result.papers_with_full_text = loaded_count
                logger.info(f"Loaded full text for {loaded_count} papers")

            # --- Phase 6: Summarization ---
            if not self.skip_synthesis and papers:
                await self.memory_manager.transition_phase(session_id, "summarization")
                logger.info("Phase 6: Generating summaries...")

                summarized_count = 0
                for paper in papers:
                    summary = await self.summarizer.summarize_paper(paper)
                    if summary:
                        paper.summary = summary
                        summarized_count += 1

                result.papers_with_summaries = summarized_count
                logger.info(f"Generated {summarized_count} summaries")

                # Checkpoint after summarization
                await self.memory_manager.checkpoint(session_id, "summarization")

            # --- Phase 7: Clustering ---
            if not self.skip_synthesis and papers:
                await self.memory_manager.transition_phase(session_id, "clustering")
                logger.info("Phase 7: Clustering papers by theme...")

                clusters = await self.clusterer.cluster_papers(papers)
                result.clusters = clusters
                result.clusters_created = len(clusters)

                logger.info(f"Created {len(clusters)} clusters")

                # Checkpoint after clustering
                await self.memory_manager.checkpoint(session_id, "clustering")

            # --- Phase 8: Report Writing ---
            if not self.skip_synthesis and clusters:
                await self.memory_manager.transition_phase(session_id, "writing")
                logger.info("Phase 8: Generating final report...")

                report_markdown = self.writer.format_report_with_papers(
                    clusters,
                    papers,
                    request.topic
                )
                result.report_markdown = report_markdown

                logger.info(f"Generated report ({len(report_markdown)} chars)")

            # Final phase
            await self.memory_manager.transition_phase(session_id, "complete")

            result.papers = papers
            result.completed_at = datetime.now()
            logger.info(f"Pipeline complete in {result.duration_seconds:.1f}s")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            result.completed_at = datetime.now()
            raise

        return result
    
    async def run_quick(self, topic: str) -> PipelineResult:
        """Quick run with minimal options."""
        request = ResearchRequest(topic=topic)
        return await self.run(request)
