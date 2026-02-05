
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import logging
from src.adapters.llm import LLMClientInterface
from src.core.prompts import PromptManager
from src.core.schema import ResearchRequest, ResearchPlan, ResearchStep

logger = logging.getLogger(__name__)

class PlannerService:
    """
    Planner Agent: Creates editable research plans from user input.
    
    Flow:
    1. User provides ResearchRequest (topic, keywords, sources, questions)
    2. LLM generates ResearchPlan with actionable steps
    3. User-provided hints are integrated into the plan
    4. User can edit the plan before execution
    """
    
    DEFAULT_SOURCES = ["arxiv", "huggingface"]

    def __init__(self, llm_client: LLMClientInterface = None):
        self.llm = llm_client

    async def generate_research_plan(self, request: ResearchRequest) -> ResearchPlan:
        """
        Generate an editable research plan from user request.
        
        Integrates:
        - request.keywords -> Seed queries for initial steps
        - request.sources -> Dedicated "Collect from URLs" step
        - request.research_questions -> Embedded into plan or separate steps
        - request.time_window -> Stored for ingestion filtering
        """
        topic = request.topic
        
        if not self.llm:
            logger.warning("LLM not provided, returning basic plan")
            return self._create_fallback_plan(request)
        
        # Build context for LLM including user hints
        context = self._build_prompt_context(request)
        prompt = PromptManager.get_prompt("PLANNER_RESEARCH_PLAN", topic=topic)
        
        # Add user hints to prompt if provided
        if context:
            prompt += f"\n\nUser has provided the following hints:\n{context}"
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            data = json.loads(response_text)
            
            # Parse LLM-generated steps
            steps = []
            for step_data in data.get("steps", []):
                step = ResearchStep(
                    id=step_data.get("id", len(steps) + 1),
                    action=step_data.get("action", "research"),
                    title=step_data.get("title", f"Step {len(steps) + 1}"),
                    description=step_data.get("description", ""),
                    queries=step_data.get("queries", []),
                    sources=step_data.get("sources", []),
                    completed=False
                )
                steps.append(step)
            
            # Inject user-provided data into plan
            steps = self._inject_user_data(steps, request)
            
            return ResearchPlan(
                topic=data.get("topic", topic),
                summary=data.get("summary", ""),
                steps=steps,
                language=request.output_config.language
            )
            
        except Exception as e:
            logger.error(f"Error generating research plan: {e}")
            return self._create_fallback_plan(request)
    
    def _build_prompt_context(self, request: ResearchRequest) -> str:
        """Build context string from user-provided hints."""
        parts = []
        
        if request.keywords:
            parts.append(f"- Seed keywords: {', '.join(request.keywords)}")
        
        if request.research_questions:
            parts.append(f"- Specific questions to answer:")
            for q in request.research_questions:
                parts.append(f"  * {q}")
        
        if request.sources:
            parts.append(f"- Specific sources to include: {', '.join(request.sources)}")
        
        if request.time_window:
            parts.append(f"- Time window: {request.time_window.start_date} to {request.time_window.end_date}")
        
        return "\n".join(parts)
    
    def _inject_user_data(self, steps: List[ResearchStep], request: ResearchRequest) -> List[ResearchStep]:
        """
        Inject user-provided keywords, sources, and questions into the plan.
        """
        # 1. Add user keywords to first research step
        if request.keywords and steps:
            first_research_step = next((s for s in steps if s.action == "research"), steps[0])
            existing_queries = set(first_research_step.queries)
            for kw in request.keywords:
                if kw not in existing_queries:
                    first_research_step.queries.insert(0, kw)
        
        # 2. Add dedicated step for user-provided URLs
        if request.sources:
            url_step = ResearchStep(
                id=0,  # Will be renumbered
                action="collect",
                title="Collect from User-Specified Sources",
                description="Fetch papers from URLs provided by user",
                queries=[],
                sources=request.sources,
                completed=False
            )
            steps.insert(0, url_step)
        
        # 3. Add research questions as queries if not already covered
        if request.research_questions:
            # Find or create a "deep dive" step
            deep_step = next((s for s in steps if "deep" in s.title.lower() or "specific" in s.title.lower()), None)
            if deep_step:
                for q in request.research_questions:
                    if q not in deep_step.queries:
                        deep_step.queries.append(q)
            else:
                # Create a dedicated questions step
                q_step = ResearchStep(
                    id=0,
                    action="research",
                    title="Answer User's Research Questions",
                    description="Find information to answer specific questions provided by user",
                    queries=request.research_questions,
                    sources=[],
                    completed=False
                )
                # Insert after initial research
                insert_idx = min(2, len(steps))
                steps.insert(insert_idx, q_step)
        
        # Renumber steps
        for i, step in enumerate(steps, 1):
            step.id = i
        
        return steps
    
    def _create_fallback_plan(self, request: ResearchRequest) -> ResearchPlan:
        """Create a basic plan when LLM is unavailable."""
        topic = request.topic
        steps = []
        
        # Step 0: User sources (if provided)
        if request.sources:
            steps.append(ResearchStep(
                id=len(steps) + 1,
                action="collect",
                title="Collect from User Sources",
                description="Fetch papers from user-provided URLs",
                queries=[],
                sources=request.sources,
                completed=False
            ))
        
        # Step 1: Initial research with keywords
        initial_queries = request.keywords.copy() if request.keywords else []
        initial_queries.extend([topic, f"{topic} survey", f"{topic} methods"])
        steps.append(ResearchStep(
            id=len(steps) + 1,
            action="research",
            title="Initial Research",
            description=f"Search for papers and resources about {topic}",
            queries=list(set(initial_queries)),
            completed=False
        ))
        
        # Step 2: Answer questions (if provided)
        if request.research_questions:
            steps.append(ResearchStep(
                id=len(steps) + 1,
                action="research",
                title="Answer Research Questions",
                description="Find specific answers to user's questions",
                queries=request.research_questions,
                completed=False
            ))
        
        # Step 3: Analyze
        steps.append(ResearchStep(
            id=len(steps) + 1,
            action="analyze",
            title="Analyze Findings",
            description="Review and analyze collected papers",
            queries=[],
            completed=False
        ))
        
        # Step 4: Synthesize
        steps.append(ResearchStep(
            id=len(steps) + 1,
            action="synthesize",
            title="Create Report",
            description="Synthesize findings into comprehensive report",
            queries=[],
            completed=False
        ))
        
        return ResearchPlan(
            topic=topic,
            summary=f"Research plan for: {topic}",
            steps=steps,
            language=request.output_config.language
        )
    
    def get_all_queries(self, plan: ResearchPlan) -> List[str]:
        """Extract all search queries from the plan."""
        queries = []
        for step in plan.steps:
            queries.extend(step.queries)
        return list(set(queries))
    
    def get_all_sources(self, plan: ResearchPlan) -> List[str]:
        """Extract all URLs from the plan."""
        sources = []
        for step in plan.steps:
            sources.extend(step.sources)
        return list(set(sources))
    
    def get_steps_by_action(self, plan: ResearchPlan, action: str) -> List[ResearchStep]:
        """Get all steps of a specific action type."""
        return [s for s in plan.steps if s.action == action]
