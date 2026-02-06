"""
AdaptivePlannerService - Simple adaptive planning.

Simplified to just QUICK vs FULL to reduce complexity.
"""

import logging
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from src.adapters.llm import LLMClientInterface
from src.core.schema import (
    ResearchRequest,
    ResearchPlan,
    ResearchQuery,
    QueryType
)
from src.planner.service import PlannerService
from src.planner.query_parser import QueryParser

logger = logging.getLogger(__name__)


@dataclass
class PhaseConfig:
    """Configuration for which phases to run."""
    active_phases: List[str] = field(default_factory=list)
    skip_synthesis: bool = False

    # Individual phase flags (can be set directly or via active_phases)
    _analysis: Optional[bool] = field(default=None, repr=False)
    _pdf_loading: Optional[bool] = field(default=None, repr=False)
    _summarization: Optional[bool] = field(default=None, repr=False)
    _clustering: Optional[bool] = field(default=None, repr=False)
    _writing: Optional[bool] = field(default=None, repr=False)

    def __post_init__(self):
        if not self.active_phases:
            self.active_phases = [
                "planning", "execution", "persistence", "analysis",
                "pdf_loading", "summarization", "clustering", "writing"
            ]

    @property
    def analysis(self) -> bool:
        if self._analysis is not None:
            return self._analysis
        return "analysis" in self.active_phases

    @analysis.setter
    def analysis(self, value: bool):
        self._analysis = value

    @property
    def pdf_loading(self) -> bool:
        if self._pdf_loading is not None:
            return self._pdf_loading
        return "pdf_loading" in self.active_phases

    @pdf_loading.setter
    def pdf_loading(self, value: bool):
        self._pdf_loading = value

    @property
    def summarization(self) -> bool:
        if self._summarization is not None:
            return self._summarization
        return "summarization" in self.active_phases

    @summarization.setter
    def summarization(self, value: bool):
        self._summarization = value

    @property
    def clustering(self) -> bool:
        if self._clustering is not None:
            return self._clustering
        return "clustering" in self.active_phases

    @clustering.setter
    def clustering(self, value: bool):
        self._clustering = value

    @property
    def writing(self) -> bool:
        if self._writing is not None:
            return self._writing
        return "writing" in self.active_phases

    @writing.setter
    def writing(self, value: bool):
        self._writing = value


@dataclass
class AdaptivePlan:
    """
    Research plan with adaptive configuration.

    Contains the plan and metadata about how to execute it.
    """
    plan: ResearchPlan
    query_info: ResearchQuery
    phase_config: PhaseConfig

    @property
    def topic(self) -> str:
        return self.plan.topic

    @property
    def steps(self) -> list:
        return self.plan.steps

    def to_display(self) -> str:
        """Format adaptive plan for display."""
        lines = [
            f"# Research Plan: {self.plan.topic}",
            "",
            f"**Mode:** {self.query_info.query_type.value.upper()}",
            f"**Phases:** {', '.join(self.phase_config.active_phases)}",
            "",
        ]
        lines.append(self.plan.to_display())
        return "\n".join(lines)


# Phase templates - just 2 options now
PHASE_TEMPLATES = {
    QueryType.QUICK: PhaseConfig(
        active_phases=["planning", "execution", "persistence", "analysis"],
        skip_synthesis=True
    ),
    QueryType.FULL: PhaseConfig(
        active_phases=[
            "planning", "execution", "persistence", "analysis",
            "pdf_loading", "summarization", "clustering", "writing"
        ],
        skip_synthesis=False
    )
}


class AdaptivePlannerService:
    """
    Simple adaptive planner - just QUICK or FULL mode.

    QUICK: 4 phases (fast, no report)
    FULL: 8 phases (complete with report)
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        planner: Optional[PlannerService] = None
    ):
        self.llm = llm_client
        self.planner = planner or PlannerService(llm_client)
        self.query_parser = QueryParser(llm_client)

    async def create_adaptive_plan(
        self,
        request: ResearchRequest,
        use_llm_parsing: bool = False  # Default to rules only
    ) -> AdaptivePlan:
        """
        Create adaptive research plan.

        Args:
            request: Research request from user
            use_llm_parsing: Whether to use LLM for parsing (default False)

        Returns:
            AdaptivePlan with phase configuration
        """
        # 1. Parse query to determine QUICK vs FULL
        query_info = await self.query_parser.parse(
            request.topic,
            use_llm=use_llm_parsing
        )

        logger.info(f"Query type: {query_info.query_type.value}")

        # 2. Handle URLs
        if query_info.has_urls and query_info.urls:
            request.sources = list(set(request.sources + query_info.urls))
            logger.info(f"Added {len(query_info.urls)} URLs")

        # 3. Get phase config
        phase_config = PHASE_TEMPLATES.get(
            query_info.query_type,
            PHASE_TEMPLATES[QueryType.FULL]
        )

        # 4. Generate plan
        plan = await self.planner.generate_research_plan(request)

        return AdaptivePlan(
            plan=plan,
            query_info=query_info,
            phase_config=phase_config
        )

    async def quick_parse(self, topic: str) -> ResearchQuery:
        """Quick parsing without full plan generation."""
        return await self.query_parser.parse(topic, use_llm=False)

    def get_phase_template(self, query_type: QueryType) -> PhaseConfig:
        """Get phase template for a query type."""
        return PHASE_TEMPLATES.get(query_type, PHASE_TEMPLATES[QueryType.FULL])
