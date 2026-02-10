"""
Research Pipeline Orchestrator (Citation-First)

Coordinates the full research pipeline with two modes:
- Legacy (8-phase): Planning → Execution → Persistence → Analysis →
  PDF Loading → Summarization → Clustering → Writing
- Citation-first (10-phase): Planning → Execution → Persistence →
  Screening → PDF Loading → Evidence Extraction → Clustering →
  Grounded Synthesis (Claims + Report + Gaps) → Citation Audit → Publish

Phase 3 Addition: AdaptivePlannerService - query parsing and phase selection
Citation-First Addition: Screening, Evidence Extraction, Claims, Audit, Gaps
"""

import logging
import uuid
from typing import List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from src.core.schema import ResearchRequest, ResearchPlan
from src.core.models import (
    Paper,
    PaperStatus,
    StudyCard,
    EvidenceSpan,
    Claim,
    TaxonomyMatrix,
)
from src.core.database import connect_mongodb
from src.planner.service import PlannerService
from src.planner.executor import PlanExecutor, StepStatus
from src.planner.adaptive_planner import (
    AdaptivePlannerService,
    AdaptivePlan,
    PhaseConfig,
    LEGACY_PHASE_TEMPLATE,
)
from src.storage.repositories import (
    PaperRepository,
    ClusterRepository,
    ReportRepository,
    ScreeningRecordRepository,
    EvidenceSpanRepository,
    StudyCardRepository,
    ClaimRepository,
)
from src.research.analysis.analyzer import AnalyzerService
from src.research.analysis.pdf_loader import PDFLoaderService
from src.research.analysis.summarizer import SummarizerService
from src.research.analysis.clusterer import ClustererService, Cluster
from src.research.analysis.screener import ScreenerService
from src.research.analysis.evidence_extractor import EvidenceExtractorService
from src.research.analysis.taxonomy import TaxonomyBuilder
from src.research.synthesis.writer import WriterService
from src.research.synthesis.claim_generator import ClaimGeneratorService
from src.research.synthesis.grounded_writer import GroundedWriterService
from src.research.synthesis.citation_audit import CitationAuditService
from src.research.synthesis.gap_miner import GapMinerService, FutureDirection
from src.research.gates import ApprovalGateManager
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

    # Adaptive planning info
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

    # Processing stats (legacy)
    papers_with_full_text: int = 0
    papers_with_summaries: int = 0
    clusters_created: int = 0

    # Screening stats (citation-first)
    papers_screened: int = 0
    papers_included: int = 0
    papers_excluded: int = 0

    # Evidence stats (citation-first)
    study_cards_created: int = 0
    evidence_spans_created: int = 0

    # Claim stats (citation-first)
    claims_generated: int = 0
    citation_audit_pass_rate: float = 0.0

    # Cache stats
    cache_hit_rate: float = 0.0

    # Papers & Clusters
    papers: List[Paper] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)

    # Citation-first artifacts
    study_cards: List[StudyCard] = field(default_factory=list)
    evidence_spans: List[EvidenceSpan] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    taxonomy: Optional[TaxonomyMatrix] = None
    future_directions: list = field(default_factory=list)

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

    Supports two modes:
    - Legacy mode (use_citation_workflow=False): 8-phase pipeline
    - Citation-first mode (use_citation_workflow=True): 10-phase pipeline

    Usage:
        # Citation-first (default)
        pipeline = ResearchPipeline(llm, use_adaptive_planner=True)
        result = await pipeline.run(request)

        # Legacy mode
        pipeline = ResearchPipeline(llm, use_citation_workflow=False)
        result = await pipeline.run(request)
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        skip_analysis: bool = False,
        skip_synthesis: bool = False,
        use_adaptive_planner: bool = False,
        use_citation_workflow: bool = True,
    ):
        self.llm = llm_client
        self.skip_analysis = skip_analysis
        self.skip_synthesis = skip_synthesis
        self.use_adaptive_planner = use_adaptive_planner
        self.use_citation_workflow = use_citation_workflow

        # Core services
        self.planner = PlannerService(llm_client)
        self.adaptive_planner = (
            AdaptivePlannerService(llm_client, self.planner)
            if use_adaptive_planner
            else None
        )
        self.paper_repo = PaperRepository()

        # Legacy analysis
        self.analyzer = AnalyzerService(llm_client, self.paper_repo)

        # HITL gates
        self.gate_manager = ApprovalGateManager()

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
        progress_callback: ProgressCallback = None,
    ) -> PipelineResult:
        """
        Run the complete research pipeline.

        Automatically selects citation-first or legacy mode based on
        self.use_citation_workflow flag.
        """
        plan_id = str(uuid.uuid4())

        result = PipelineResult(
            plan_id=plan_id,
            topic=request.topic,
            started_at=datetime.now(),
        )

        async def notify(phase: str, message: str, **kwargs):
            if progress_callback:
                await progress_callback(phase, message, kwargs)

        phase_config = PhaseConfig()

        try:
            # --- Initialize Services ---
            await connect_mongodb()
            self.cache_manager = await get_cache_manager()
            self.memory_manager = ResearchMemoryManager()
            await self.memory_manager.connect()
            session_id = await self.memory_manager.create_session(
                request.topic, plan_id=plan_id
            )
            result.session_id = session_id

            self.pdf_loader = PDFLoaderService(
                self.cache_manager, relevance_threshold=8.0
            )
            self.summarizer = SummarizerService(self.llm)
            self.vector_service = VectorService()
            self.clusterer = ClustererService(self.llm, self.vector_service)
            self.writer = WriterService()

            # === Phase B: Planning ===
            await self.memory_manager.transition_phase(session_id, "planning")
            await notify("planning", "Generating research plan...")

            if adaptive_plan:
                plan = adaptive_plan.plan
                phase_config = adaptive_plan.phase_config
                result.query_type = adaptive_plan.query_info.query_type.value
            elif self.use_adaptive_planner and self.adaptive_planner and not plan:
                adaptive_plan = await self.adaptive_planner.create_adaptive_plan(
                    request
                )
                plan = adaptive_plan.plan
                phase_config = adaptive_plan.phase_config
                result.query_type = adaptive_plan.query_info.query_type.value
            elif not plan:
                plan = await self.planner.generate_research_plan(request)

            # Apply legacy skip flags
            if self.skip_synthesis:
                phase_config.pdf_loading = False
                phase_config.summarization = False
                phase_config.clustering = False
                phase_config.writing = False
            if self.skip_analysis:
                phase_config.analysis = False

            # Force legacy mode if not using citation workflow
            if not self.use_citation_workflow:
                phase_config = LEGACY_PHASE_TEMPLATE

            result.phases_executed = phase_config.active_phases
            logger.info(f"Plan: {plan.topic} with {len(plan.steps)} steps")

            # === Phase C: Execution (Collection) ===
            await self.memory_manager.transition_phase(session_id, "execution")
            await notify(
                "execution",
                "Collecting papers from sources...",
                steps=len(plan.steps),
            )
            logger.info("Phase C: Executing plan (collecting papers)...")
            executor = PlanExecutor(plan_id=plan_id, cache_manager=self.cache_manager)
            await executor.execute(plan)

            quality = executor.get_quality_summary()
            result.total_collected = quality.get("total_collected", 0)
            result.unique_papers = quality.get("unique_papers", 0)
            result.duplicates_removed = quality.get("duplicates_removed", 0)
            result.steps_completed = len(executor.progress.completed_steps)
            result.steps_failed = len(executor.progress.failed_steps)
            result.cache_hit_rate = executor.progress.cache_hit_rate

            papers = executor.get_papers_as_models()
            for paper in papers:
                paper.plan_id = plan_id

            await notify(
                "execution", f"Collected {len(papers)} papers", papers=len(papers)
            )
            logger.info(f"Collected {len(papers)} unique papers")

            # === Phase C (cont): Persistence ===
            await notify("persistence", "Saving papers to database...")
            logger.info("Persisting papers to MongoDB...")
            if papers:
                paper_ids = await self.paper_repo.create_many(papers)
                for paper, pid in zip(papers, paper_ids):
                    paper.id = pid
                for paper in papers:
                    await self.memory_manager.register_paper(session_id, paper)

            await self.memory_manager.checkpoint(session_id, "collection")

            # === Branch: Citation-first vs Legacy ===
            if self.use_citation_workflow and phase_config.screening:
                result = await self._run_citation_pipeline(
                    request,
                    papers,
                    plan_id,
                    session_id,
                    phase_config,
                    result,
                    notify,
                )
            else:
                result = await self._run_legacy_pipeline(
                    request,
                    papers,
                    plan_id,
                    session_id,
                    phase_config,
                    executor,
                    result,
                    notify,
                )

            # Final phase
            await self.memory_manager.transition_phase(session_id, "complete")
            await notify(
                "complete",
                "Research complete!",
                papers=len(result.papers),
                clusters=len(result.clusters),
            )

            result.completed_at = datetime.now()
            logger.info(f"Pipeline complete in {result.duration_seconds:.1f}s")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            result.completed_at = datetime.now()
            raise

        return result

    async def _run_citation_pipeline(
        self,
        request: ResearchRequest,
        papers: List[Paper],
        plan_id: str,
        session_id: str,
        phase_config: PhaseConfig,
        result: PipelineResult,
        notify,
    ) -> PipelineResult:
        """Run the citation-first 10-phase pipeline."""

        language = request.output_config.language if request.output_config else "en"

        # === Phase D: Screening ===
        await self.memory_manager.transition_phase(session_id, "screening")
        await notify("screening", f"Screening {len(papers)} papers...")
        logger.info("Phase D: Screening papers...")

        screener = ScreenerService(self.llm)
        included_papers, screening_records = await screener.screen_papers(
            papers, request.topic
        )

        result.papers_screened = len(papers)
        result.papers_included = len(included_papers)
        result.papers_excluded = len(papers) - len(included_papers)
        result.relevant_papers = len(included_papers)

        await notify(
            "screening",
            f"Screening complete: {len(included_papers)} included, "
            f"{result.papers_excluded} excluded",
        )
        await self.memory_manager.checkpoint(session_id, "screening")

        papers = included_papers

        # === HITL Gate: PDF Download ===
        if papers:
            gate = self.gate_manager.check_pdf_gate(
                len(papers), request.max_pdf_download
            )
            if gate:
                approved = await self.gate_manager.request_approval(gate)
                if not approved:
                    logger.info("PDF download gate rejected, skipping PDF phase")
                    phase_config.pdf_loading = False

        # === Phase E: Full-text Loading ===
        if phase_config.pdf_loading and papers:
            await self.memory_manager.transition_phase(session_id, "pdf_loading")
            await notify("pdf_loading", "Loading full text with page mapping...")
            logger.info("Phase E: Loading full text with page mapping...")

            loaded_count = await self.pdf_loader.load_batch_with_pages(papers)
            result.papers_with_full_text = loaded_count
            result.high_relevance_papers = loaded_count

            await notify("pdf_loading", f"Loaded {loaded_count} full texts")
            logger.info(f"Loaded full text for {loaded_count} papers")

        # === Phase F: Evidence Extraction ===
        study_cards = []
        evidence_spans = []
        if phase_config.evidence_extraction and papers:
            await self.memory_manager.transition_phase(
                session_id, "evidence_extraction"
            )
            await notify(
                "evidence_extraction",
                f"Extracting evidence from {len(papers)} papers...",
            )
            logger.info("Phase F: Extracting evidence...")

            extractor = EvidenceExtractorService(self.llm, pdf_loader=self.pdf_loader)
            study_cards, evidence_spans = await extractor.extract_batch(
                papers, language=language
            )

            result.study_cards_created = len(study_cards)
            result.evidence_spans_created = len(evidence_spans)
            result.study_cards = study_cards
            result.evidence_spans = evidence_spans

            await notify(
                "evidence_extraction",
                f"Extracted {len(study_cards)} study cards, "
                f"{len(evidence_spans)} evidence spans",
            )
            await self.memory_manager.checkpoint(session_id, "evidence_extraction")

        # === Phase G: Thematic Structuring ===
        clusters = []
        cluster_dicts = []
        if phase_config.clustering and papers:
            await self.memory_manager.transition_phase(session_id, "clustering")
            await notify("clustering", "Grouping papers by theme...")
            logger.info("Phase G: Clustering papers by theme...")

            clusters = await self.clusterer.cluster_papers(papers, language=language)
            result.clusters = clusters
            result.clusters_created = len(clusters)

            # Convert Cluster objects to dicts for downstream use
            for cluster in clusters:
                paper_ids = [
                    papers[idx].id or papers[idx].arxiv_id or papers[idx].title
                    for idx in cluster.paper_indices
                    if idx < len(papers)
                ]
                cluster_dicts.append(
                    {
                        "id": cluster.id,
                        "name": cluster.name,
                        "description": cluster.description,
                        "paper_ids": paper_ids,
                    }
                )

            await notify("clustering", f"Created {len(clusters)} clusters")
            await self.memory_manager.checkpoint(session_id, "clustering")

        # === Build Taxonomy ===
        taxonomy = None
        if study_cards and cluster_dicts:
            taxonomy_builder = TaxonomyBuilder()
            taxonomy = taxonomy_builder.build_taxonomy(study_cards, cluster_dicts)
            result.taxonomy = taxonomy

        # === Phase H: Grounded Synthesis ===
        claims = []
        future_directions = []

        if phase_config.claim_generation and study_cards and cluster_dicts:
            await self.memory_manager.transition_phase(session_id, "synthesis")
            await notify("synthesis", "Generating claims...")
            logger.info("Phase H: Generating claims...")

            claim_gen = ClaimGeneratorService(self.llm)
            claims = await claim_gen.generate_claims(
                study_cards, evidence_spans, cluster_dicts, language=language
            )
            result.claims_generated = len(claims)
            result.claims = claims

            await notify("synthesis", f"Generated {len(claims)} claims")

        # === Gap Mining ===
        if phase_config.gap_mining and study_cards and taxonomy:
            await notify("synthesis", "Mining research gaps...")
            logger.info("Phase H (cont): Mining gaps for future directions...")

            gap_miner = GapMinerService(self.llm)
            future_directions = await gap_miner.mine_gaps(
                study_cards,
                evidence_spans,
                taxonomy,
                request.topic,
                language=language,
            )
            result.future_directions = future_directions

            await notify(
                "synthesis", f"Found {len(future_directions)} future directions"
            )

        # === Report Writing ===
        if phase_config.writing and (claims or papers):
            await self.memory_manager.transition_phase(session_id, "writing")
            await notify("writing", "Generating grounded report...")
            logger.info("Phase H (cont): Generating grounded report...")

            grounded_writer = GroundedWriterService(self.llm)
            report_markdown = await grounded_writer.generate_report(
                claims=claims,
                clusters=cluster_dicts,
                evidence_spans=evidence_spans,
                papers=papers,
                topic=request.topic,
                taxonomy=taxonomy,
                future_directions=future_directions,
                language=language,
            )
            result.report_markdown = report_markdown
            await notify(
                "writing",
                f"Generated report ({len(report_markdown)} chars)",
            )

        # === Phase I: Citation Audit ===
        if phase_config.citation_audit and claims and evidence_spans:
            await self.memory_manager.transition_phase(session_id, "citation_audit")
            await notify("citation_audit", "Auditing citations...")
            logger.info("Phase I: Citation audit...")

            auditor = CitationAuditService(self.llm)
            audit_result = await auditor.audit_claims(claims, evidence_spans)
            result.citation_audit_pass_rate = audit_result.pass_rate

            await notify(
                "citation_audit",
                f"Audit complete: {audit_result.pass_rate:.0%} pass rate "
                f"({audit_result.passed} passed, {audit_result.failed} failed, "
                f"{audit_result.repaired} repaired)",
            )
            logger.info(f"Citation audit: {audit_result.pass_rate:.0%} pass rate")

        # === Phase J: Publish ===
        await notify("publish", "Storing artifacts...")
        logger.info("Phase J: Publishing artifacts...")

        # Store report
        if result.report_markdown:
            from src.core.models import Report

            report = Report(
                plan_id=plan_id,
                title=f"Research Report: {request.topic}",
                content=result.report_markdown,
                paper_count=len(papers),
                language=(
                    request.output_config.language if request.output_config else "en"
                ),
            )
            report_repo = ReportRepository()
            await report_repo.create(report)

        # Store clusters
        if cluster_dicts:
            from src.core.models import Cluster as ClusterModel

            cluster_repo = ClusterRepository()
            for cd in cluster_dicts:
                cluster_model = ClusterModel(
                    name=cd["name"],
                    description=cd.get("description", ""),
                    paper_ids=cd.get("paper_ids", []),
                    plan_id=plan_id,
                )
                await cluster_repo.create(cluster_model)

        result.papers = papers
        return result

    async def _run_legacy_pipeline(
        self,
        request: ResearchRequest,
        papers: List[Paper],
        plan_id: str,
        session_id: str,
        phase_config: PhaseConfig,
        executor: PlanExecutor,
        result: PipelineResult,
        notify,
    ) -> PipelineResult:
        """Run the legacy 8-phase pipeline (backward compatible)."""

        language = request.output_config.language if request.output_config else "en"

        # --- Phase 4: Analysis ---
        if phase_config.analysis and papers:
            await self.memory_manager.transition_phase(session_id, "analysis")
            await notify("analysis", f"Scoring relevance for {len(papers)} papers...")
            logger.info("Phase 4: Analyzing relevance...")
            relevant, irrelevant = await self.analyzer.score_and_persist(
                papers, request.topic
            )

            result.relevant_papers = len(relevant)
            result.high_relevance_papers = sum(
                1 for p in relevant if p.relevance_score and p.relevance_score >= 8.0
            )

            for paper in papers:
                if paper.id and paper.relevance_score:
                    await self.paper_repo.update_score(paper.id, paper.relevance_score)

            papers = relevant
            await self.memory_manager.checkpoint(session_id, "analysis")
        else:
            result.relevant_papers = len(papers)

        # --- Phase 5: Full Text Loading ---
        if phase_config.pdf_loading and papers:
            await notify(
                "pdf_loading", "Loading full text for high-relevance papers..."
            )
            logger.info("Phase 5: Loading full text...")
            loaded_count = await self.pdf_loader.load_full_text_batch(papers)
            result.papers_with_full_text = loaded_count

        # --- Phase 6: Summarization ---
        if phase_config.summarization and papers:
            await self.memory_manager.transition_phase(session_id, "summarization")
            await notify(
                "summarization", f"Generating summaries for {len(papers)} papers..."
            )
            logger.info("Phase 6: Generating summaries...")

            summarized_count = 0
            for paper in papers:
                summary = await self.summarizer.summarize_paper(
                    paper, language=language
                )
                if summary:
                    paper.summary = summary
                    summarized_count += 1

            result.papers_with_summaries = summarized_count
            await self.memory_manager.checkpoint(session_id, "summarization")

        # --- Phase 7: Clustering ---
        clusters = []
        if phase_config.clustering and papers:
            await self.memory_manager.transition_phase(session_id, "clustering")
            await notify("clustering", "Grouping papers by theme...")
            logger.info("Phase 7: Clustering papers...")

            clusters = await self.clusterer.cluster_papers(papers, language=language)
            result.clusters = clusters
            result.clusters_created = len(clusters)
            await self.memory_manager.checkpoint(session_id, "clustering")

        # --- Phase 8: Report Writing ---
        if phase_config.writing and (clusters or papers):
            await self.memory_manager.transition_phase(session_id, "writing")
            await notify("writing", "Generating final report...")
            logger.info("Phase 8: Generating report...")

            report_markdown = self.writer.format_report_with_papers(
                clusters if clusters else [], papers, request.topic
            )
            result.report_markdown = report_markdown

        result.papers = papers
        return result

    async def generate_plan(self, request: ResearchRequest) -> ResearchPlan:
        """Step 1 of 2: Generate a research plan for human review."""
        return await self.planner.generate_research_plan(request)

    async def generate_adaptive_plan(self, request: ResearchRequest) -> AdaptivePlan:
        """Step 1 of 2: Generate an adaptive plan for human review."""
        if not self.adaptive_planner:
            self.adaptive_planner = AdaptivePlannerService(self.llm, self.planner)
        return await self.adaptive_planner.create_adaptive_plan(request)

    async def execute_plan(
        self,
        request: ResearchRequest,
        plan: ResearchPlan = None,
        adaptive_plan: AdaptivePlan = None,
        progress_callback: ProgressCallback = None,
    ) -> PipelineResult:
        """Step 2 of 2: Execute a reviewed/approved plan."""
        return await self.run(
            request,
            plan=plan,
            adaptive_plan=adaptive_plan,
            progress_callback=progress_callback,
        )

    async def run_quick(self, topic: str) -> PipelineResult:
        """Quick run with minimal options (no review phase)."""
        request = ResearchRequest(topic=topic)
        return await self.run(request)
