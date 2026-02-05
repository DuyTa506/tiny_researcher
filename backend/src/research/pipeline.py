"""
Research Pipeline Orchestrator

Coordinates the full research pipeline:
1. PlanExecutor - collect papers via tools
2. Paper persistence to MongoDB
3. AnalyzerService - score relevance
4. Future: SummarizerService, ClustererService, WriterService
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
from src.adapters.llm import LLMClientInterface

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running the research pipeline."""
    plan_id: str
    topic: str
    
    # Execution stats
    steps_completed: int
    steps_failed: int
    
    # Paper stats
    total_collected: int
    unique_papers: int
    relevant_papers: int
    
    # Dedup stats
    duplicates_removed: int
    
    # Papers
    papers: List[Paper] = field(default_factory=list)
    
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
        skip_analysis: bool = False
    ):
        self.llm = llm_client
        self.skip_analysis = skip_analysis
        
        # Services
        self.planner = PlannerService(llm_client)
        self.paper_repo = PaperRepository()
        self.analyzer = AnalyzerService(llm_client, self.paper_repo)
    
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
            steps_completed=0,
            steps_failed=0,
            total_collected=0,
            unique_papers=0,
            relevant_papers=0,
            duplicates_removed=0,
            started_at=datetime.now()
        )
        
        try:
            # Connect to MongoDB
            await connect_mongodb()
            
            # --- Phase 1: Planning ---
            if not plan:
                logger.info("Phase 1: Generating research plan...")
                plan = await self.planner.generate_research_plan(request)
            
            logger.info(f"Plan: {plan.topic} with {len(plan.steps)} steps")
            
            # --- Phase 2: Execution ---
            logger.info("Phase 2: Executing plan (collecting papers)...")
            executor = PlanExecutor(plan_id=plan_id)
            await executor.execute(plan)
            
            # Get quality metrics
            quality = executor.get_quality_summary()
            result.total_collected = quality.get("total_collected", 0)
            result.unique_papers = quality.get("unique_papers", 0)
            result.duplicates_removed = quality.get("duplicates_removed", 0)
            result.steps_completed = len(executor.progress.completed_steps)
            result.steps_failed = len(executor.progress.failed_steps)
            
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
            
            # --- Phase 4: Analysis ---
            if not self.skip_analysis and papers:
                logger.info("Phase 4: Analyzing relevance...")
                relevant, irrelevant = await self.analyzer.score_and_persist(
                    papers, 
                    request.topic
                )
                
                result.relevant_papers = len(relevant)
                result.papers = relevant
                
                # Update scores in MongoDB
                for paper in papers:
                    if paper.id and paper.relevance_score:
                        await self.paper_repo.update_score(
                            paper.id, 
                            paper.relevance_score
                        )
                
                logger.info(f"Analysis complete: {len(relevant)} relevant papers")
            else:
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
