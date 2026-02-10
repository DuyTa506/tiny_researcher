"""
Planner API Routes

Endpoints:
- POST /api/v1/plan - Generate a new research plan
- GET /api/v1/plan/{plan_id} - Get plan by ID
- PUT /api/v1/plan/{plan_id} - Update/edit plan
- POST /api/v1/plan/{plan_id}/execute - Start execution (Phase 2)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from src.core.schema import ResearchRequest, ResearchPlan, ResearchStep
from src.planner.service import PlannerService
from src.planner.store import PlanStore, StoredPlan, PlanStatus
from src.adapters.llm import LLMFactory

router = APIRouter()
logger = logging.getLogger(__name__)


# Dependency: Get plan store instance
def get_plan_store() -> PlanStore:
    return PlanStore()


# Dependency: Get planner service with LLM
def get_planner_service() -> PlannerService:
    try:
        llm = LLMFactory.create_client(provider="openai")
        return PlannerService(llm)
    except Exception as e:
        logger.warning(f"LLM not available: {e}")
        return PlannerService(None)


# --- Request/Response Models ---


class CreatePlanRequest(BaseModel):
    topic: str = Field(..., description="Research topic")
    keywords: List[str] = Field(default_factory=list, description="Seed keywords")
    sources: List[str] = Field(default_factory=list, description="URLs to include")
    research_questions: List[str] = Field(
        default_factory=list, description="Specific questions"
    )
    language: str = Field("vi", description="Output language")


class UpdatePlanRequest(BaseModel):
    steps: List[dict] = Field(..., description="Updated steps")


class PlanResponse(BaseModel):
    plan_id: str
    status: str
    plan: dict
    display: str
    progress: Optional[dict] = None
    results: Optional[dict] = None


# --- Endpoints ---


@router.post("", response_model=PlanResponse)
async def create_plan(
    request: CreatePlanRequest,
    planner: PlannerService = Depends(get_planner_service),
    store: PlanStore = Depends(get_plan_store),
):
    """
    Generate a new research plan from topic.
    Returns plan in draft status for user review/edit.
    """
    # Convert to ResearchRequest
    research_request = ResearchRequest(
        topic=request.topic,
        keywords=request.keywords,
        sources=request.sources,
        research_questions=request.research_questions,
    )
    research_request.output_config.language = request.language

    # Generate plan
    plan = await planner.generate_research_plan(research_request)

    # Store plan
    stored = store.create(plan)

    return PlanResponse(
        plan_id=stored.plan_id,
        status=stored.status.value,
        plan=plan.model_dump(),
        display=plan.to_display(),
        progress=stored.progress.model_dump(),
    )


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str, store: PlanStore = Depends(get_plan_store)):
    """Get plan by ID."""
    stored = store.get(plan_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Plan not found")

    return PlanResponse(
        plan_id=stored.plan_id,
        status=stored.status.value,
        plan=stored.plan.model_dump(),
        display=stored.plan.to_display(),
        progress=stored.progress.model_dump(),
        results=stored.results if stored.results else None,
    )


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str, request: UpdatePlanRequest, store: PlanStore = Depends(get_plan_store)
):
    """
    Update/edit plan steps.
    Only allowed when status is 'draft'.
    """
    stored = store.get(plan_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Plan not found")

    if stored.status != PlanStatus.DRAFT:
        raise HTTPException(
            status_code=400, detail=f"Cannot edit plan in '{stored.status}' status"
        )

    # Update steps
    updated_steps = []
    for step_data in request.steps:
        step = ResearchStep(
            id=step_data.get("id", len(updated_steps) + 1),
            action=step_data.get("action", "research"),
            title=step_data.get("title", ""),
            description=step_data.get("description", ""),
            queries=step_data.get("queries", []),
            sources=step_data.get("sources", []),
            completed=step_data.get("completed", False),
        )
        updated_steps.append(step)

    # Create updated plan
    updated_plan = ResearchPlan(
        topic=stored.plan.topic,
        summary=stored.plan.summary,
        steps=updated_steps,
        language=stored.plan.language,
    )

    # Save
    stored = store.update(plan_id, updated_plan)

    return PlanResponse(
        plan_id=stored.plan_id,
        status=stored.status.value,
        plan=stored.plan.model_dump(),
        display=stored.plan.to_display(),
        progress=stored.progress.model_dump(),
    )


@router.post("/{plan_id}/execute")
async def execute_plan(plan_id: str, store: PlanStore = Depends(get_plan_store)):
    """
    Start executing the plan.
    (Phase 2: Will integrate PlanExecutor)
    """
    stored = store.get(plan_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Plan not found")

    if stored.status == PlanStatus.EXECUTING:
        raise HTTPException(status_code=400, detail="Plan already executing")

    if stored.status == PlanStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Plan already completed")

    # Update status to executing
    store.update_status(plan_id, PlanStatus.EXECUTING)

    # TODO: Trigger PlanExecutor in background task
    # For now, just return status

    return {
        "plan_id": plan_id,
        "status": "executing",
        "message": "Execution started. Poll GET /plan/{id} for progress.",
    }


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, store: PlanStore = Depends(get_plan_store)):
    """Delete a plan."""
    if not store.delete(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")

    return {"message": "Plan deleted"}
