"""
Plan Executor

Executes research plans step-by-step using the tool registry.
Features:
- Multi-level deduplication (arxiv_id, fingerprint, title similarity)
- Quality metrics tracking
- Immediate paper registration
"""

import logging
import hashlib
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from difflib import SequenceMatcher

from src.core.schema import ResearchPlan, ResearchStep
from src.core.models import Paper
from src.tools import execute_tool, get_tool
from src.tools.registry import ToolNotFoundError, ToolExecutionError
from src.tools.cache_manager import ToolCacheManager

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Status of a single step execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_id: int
    status: StepStatus
    tool_used: Optional[str] = None
    results: List[dict] = field(default_factory=list)
    unique_count: int = 0
    duplicates_removed: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    from_cache: bool = False

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class ExecutionProgress:
    """Track overall execution progress with quality metrics."""

    total_steps: int
    current_step: int = 0
    completed_steps: List[int] = field(default_factory=list)
    failed_steps: List[int] = field(default_factory=list)

    # Quality metrics
    total_papers_collected: int = 0
    unique_papers: int = 0
    duplicates_removed: int = 0
    papers_by_source: Dict[str, int] = field(default_factory=dict)

    # Enhanced metrics (Phase 1-2)
    high_relevance_papers: int = 0  # Score >= 8
    relevance_bands: Dict[str, int] = field(
        default_factory=dict
    )  # "3-5", "6-7", "8-10"
    cache_hits: int = 0
    cache_misses: int = 0
    total_duration_seconds: float = 0.0

    @property
    def is_complete(self) -> bool:
        return len(self.completed_steps) + len(self.failed_steps) >= self.total_steps

    @property
    def success_rate(self) -> float:
        total = len(self.completed_steps) + len(self.failed_steps)
        if total == 0:
            return 0.0
        return len(self.completed_steps) / total

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def avg_step_duration(self) -> float:
        total = len(self.completed_steps) + len(self.failed_steps)
        if total == 0:
            return 0.0
        return self.total_duration_seconds / total

    def add_step_result(self, result: StepResult):
        """Update metrics from step result."""
        if result.status == StepStatus.COMPLETED:
            self.completed_steps.append(result.step_id)
            self.total_papers_collected += (
                result.unique_count + result.duplicates_removed
            )
            self.unique_papers += result.unique_count
            self.duplicates_removed += result.duplicates_removed

            # Track cache usage
            if result.from_cache:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

            # Track duration
            if result.duration_seconds:
                self.total_duration_seconds += result.duration_seconds

            if result.tool_used:
                self.papers_by_source[result.tool_used] = (
                    self.papers_by_source.get(result.tool_used, 0) + result.unique_count
                )
        elif result.status == StepStatus.FAILED:
            self.failed_steps.append(result.step_id)


class PaperDeduplicator:
    """Multi-level paper deduplication."""

    def __init__(self, title_similarity_threshold: float = 0.85):
        self.seen_arxiv_ids: Set[str] = set()
        self.seen_dois: Set[str] = set()
        self.seen_fingerprints: Set[str] = set()
        self.seen_titles: List[str] = []
        self.title_similarity_threshold = title_similarity_threshold

    def create_fingerprint(self, paper: dict) -> str:
        """Create fingerprint from title + first author."""
        title = paper.get("title", "").lower().strip()
        authors = paper.get("authors", [])
        first_author = authors[0].lower() if authors else ""
        content = f"{title}|{first_author}"
        return hashlib.md5(content.encode()).hexdigest()

    def is_duplicate(self, paper: dict) -> bool:
        """Check if paper is a duplicate using multi-level strategy."""
        # Level 1: ArXiv ID
        arxiv_id = paper.get("arxiv_id")
        if arxiv_id:
            if arxiv_id in self.seen_arxiv_ids:
                return True
            self.seen_arxiv_ids.add(arxiv_id)

        # Level 1b: DOI
        doi = paper.get("doi")
        if doi:
            doi_normalized = doi.lower().strip()
            if doi_normalized in self.seen_dois:
                return True
            self.seen_dois.add(doi_normalized)

        # Level 2: Fingerprint (title + author hash)
        fingerprint = self.create_fingerprint(paper)
        if fingerprint in self.seen_fingerprints:
            return True
        self.seen_fingerprints.add(fingerprint)

        # Level 3: Title similarity (fuzzy)
        title = paper.get("title", "").lower().strip()
        if title and self._is_similar_title(title):
            return True
        self.seen_titles.append(title)

        return False

    def _is_similar_title(self, title: str) -> bool:
        """Check if title is similar to any seen title."""
        for seen in self.seen_titles:
            ratio = SequenceMatcher(None, title, seen).ratio()
            if ratio >= self.title_similarity_threshold:
                return True
        return False

    def deduplicate(self, papers: List[dict]) -> tuple[List[dict], int]:
        """
        Deduplicate papers.

        Returns:
            Tuple of (unique_papers, duplicates_count)
        """
        unique = []
        duplicates = 0

        for paper in papers:
            if self.is_duplicate(paper):
                duplicates += 1
            else:
                unique.append(paper)

        return unique, duplicates

    def reset(self):
        """Reset deduplication state."""
        self.seen_arxiv_ids.clear()
        self.seen_dois.clear()
        self.seen_fingerprints.clear()
        self.seen_titles.clear()


class PlanExecutor:
    """
    Executor for research plans.

    Executes each step sequentially, calling tools from the registry,
    deduplicating results, and tracking quality metrics.
    """

    def __init__(
        self,
        on_step_complete: callable = None,
        plan_id: str = None,
        cache_manager: ToolCacheManager = None,
    ):
        """
        Initialize executor.

        Args:
            on_step_complete: Optional callback after each step
            plan_id: Research plan ID (for MongoDB association)
            cache_manager: Optional tool cache manager
        """
        self.on_step_complete = on_step_complete
        self.plan_id = plan_id
        self.cache_manager = cache_manager
        self._current_progress: Optional[ExecutionProgress] = None
        self._results: Dict[int, StepResult] = {}
        self._deduplicator = PaperDeduplicator()
        self._all_papers: List[dict] = []

    async def execute(self, plan: ResearchPlan) -> Dict[int, StepResult]:
        """Execute all steps in a research plan."""
        logger.info(f"Starting execution of plan: {plan.topic}")

        self._current_progress = ExecutionProgress(total_steps=len(plan.steps))
        self._results = {}
        self._deduplicator.reset()
        self._all_papers = []

        for step in plan.steps:
            self._current_progress.current_step = step.id

            result = await self._execute_step(step)
            self._results[step.id] = result

            # Update progress with quality metrics
            self._current_progress.add_step_result(result)

            # Track papers
            if result.status == StepStatus.COMPLETED:
                step.completed = True
                self._all_papers.extend(result.results)

            # Callback
            if self.on_step_complete:
                self.on_step_complete(step, result)

            logger.info(
                f"Step {step.id} completed",
                extra={
                    "status": result.status.value,
                    "unique": result.unique_count,
                    "duplicates_removed": result.duplicates_removed,
                    "duration": result.duration_seconds,
                },
            )

        logger.info(
            f"Plan execution complete",
            extra={
                "total_steps": self._current_progress.total_steps,
                "completed": len(self._current_progress.completed_steps),
                "unique_papers": self._current_progress.unique_papers,
                "duplicates_removed": self._current_progress.duplicates_removed,
                "success_rate": self._current_progress.success_rate,
            },
        )

        return self._results

    async def _execute_step(self, step: ResearchStep) -> StepResult:
        """Execute a single step with deduplication."""
        result = StepResult(
            step_id=step.id, status=StepStatus.RUNNING, started_at=datetime.now()
        )

        try:
            if step.tool:
                result.tool_used = step.tool

                # Verify tool exists
                tool_def = get_tool(step.tool)
                if not tool_def:
                    raise ToolNotFoundError(step.tool)

                # Check cache first
                raw_results = None
                if self.cache_manager:
                    raw_results = await self.cache_manager.get(
                        step.tool, **step.tool_args
                    )
                    if raw_results:
                        result.from_cache = True
                        logger.info(f"Cache HIT for tool: {step.tool}")

                # Execute tool if not cached
                if raw_results is None:
                    logger.info(
                        f"Executing tool: {step.tool}",
                        extra={"tool_args": step.tool_args},
                    )
                    raw_results = await execute_tool(step.tool, **step.tool_args)

                    # Cache the result
                    if self.cache_manager and raw_results is not None:
                        await self.cache_manager.set(
                            step.tool, raw_results, **step.tool_args
                        )

                # Normalize to list
                if not isinstance(raw_results, list):
                    raw_results = [raw_results] if raw_results else []

                # Deduplicate immediately
                unique_papers, duplicates = self._deduplicator.deduplicate(raw_results)

                # Add plan_id and step_id to each paper
                for paper in unique_papers:
                    paper["plan_id"] = self.plan_id
                    paper["step_id"] = step.id

                result.results = unique_papers
                result.unique_count = len(unique_papers)
                result.duplicates_removed = duplicates
                result.status = StepStatus.COMPLETED

            elif step.action in ("analyze", "synthesize"):
                logger.info(
                    f"Step {step.id} ({step.action}) - handled by analysis pipeline"
                )
                result.status = StepStatus.SKIPPED
            else:
                logger.warning(f"Step {step.id} has no tool assigned")
                result.status = StepStatus.SKIPPED

        except ToolNotFoundError as e:
            logger.error(f"Tool not found: {e.tool_name}")
            result.status = StepStatus.FAILED
            result.error = f"Tool not found: {e.tool_name}"

        except ToolExecutionError as e:
            logger.error(f"Tool execution failed: {e}")
            result.status = StepStatus.FAILED
            result.error = str(e.original_error)

        except Exception as e:
            logger.error(f"Unexpected error in step {step.id}: {e}", exc_info=True)
            result.status = StepStatus.FAILED
            result.error = str(e)

        finally:
            result.completed_at = datetime.now()

        return result

    @property
    def progress(self) -> Optional[ExecutionProgress]:
        """Get current execution progress."""
        return self._current_progress

    @property
    def results(self) -> Dict[int, StepResult]:
        """Get execution results."""
        return self._results

    def get_all_papers(self) -> List[dict]:
        """Get all unique papers (already deduplicated)."""
        return self._all_papers

    def get_papers_as_models(self) -> List[Paper]:
        """Convert collected papers to Paper models."""
        return [Paper.from_dict(p) for p in self._all_papers]

    def get_quality_summary(self) -> dict:
        """Get quality metrics summary."""
        if not self._current_progress:
            return {}

        return {
            "total_collected": self._current_progress.total_papers_collected,
            "unique_papers": self._current_progress.unique_papers,
            "duplicates_removed": self._current_progress.duplicates_removed,
            "dedup_rate": (
                self._current_progress.duplicates_removed
                / max(self._current_progress.total_papers_collected, 1)
            ),
            "papers_by_source": self._current_progress.papers_by_source,
        }
