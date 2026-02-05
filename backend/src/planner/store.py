"""
Plan Store: In-memory storage for research plans.

This is a temporary solution for development/testing.
In production, use Redis or database for persistence.
"""

from typing import Dict, Optional
from datetime import datetime
import uuid
from enum import Enum
from pydantic import BaseModel, Field
from src.core.schema import ResearchPlan, ResearchStep


class PlanStatus(str, Enum):
    DRAFT = "draft"           # Plan created, not yet executed
    EXECUTING = "executing"   # Execution in progress
    COMPLETED = "completed"   # All steps done
    FAILED = "failed"         # Execution failed


class PlanProgress(BaseModel):
    current_step: int = 0
    total_steps: int = 0
    completed_steps: list[int] = Field(default_factory=list)


class StoredPlan(BaseModel):
    """A plan stored in the store with metadata."""
    plan_id: str
    plan: ResearchPlan
    status: PlanStatus = PlanStatus.DRAFT
    progress: PlanProgress = Field(default_factory=PlanProgress)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    results: dict = Field(default_factory=dict)


class PlanStore:
    """
    In-memory store for research plans.
    Thread-safe for single process. Use Redis for distributed.
    """
    
    _instance = None
    _plans: Dict[str, StoredPlan] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._plans = {}
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset store (for testing)."""
        cls._plans = {}
    
    def create(self, plan: ResearchPlan) -> StoredPlan:
        """Store a new plan and return with ID."""
        plan_id = str(uuid.uuid4())
        stored = StoredPlan(
            plan_id=plan_id,
            plan=plan,
            status=PlanStatus.DRAFT,
            progress=PlanProgress(
                current_step=0,
                total_steps=len(plan.steps),
                completed_steps=[]
            )
        )
        self._plans[plan_id] = stored
        return stored
    
    def get(self, plan_id: str) -> Optional[StoredPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)
    
    def update(self, plan_id: str, plan: ResearchPlan) -> Optional[StoredPlan]:
        """Update an existing plan."""
        if plan_id not in self._plans:
            return None
        
        stored = self._plans[plan_id]
        stored.plan = plan
        stored.updated_at = datetime.utcnow()
        stored.progress.total_steps = len(plan.steps)
        return stored
    
    def update_status(self, plan_id: str, status: PlanStatus) -> Optional[StoredPlan]:
        """Update plan status."""
        if plan_id not in self._plans:
            return None
        
        self._plans[plan_id].status = status
        self._plans[plan_id].updated_at = datetime.utcnow()
        return self._plans[plan_id]
    
    def mark_step_complete(self, plan_id: str, step_id: int) -> Optional[StoredPlan]:
        """Mark a step as completed."""
        if plan_id not in self._plans:
            return None
        
        stored = self._plans[plan_id]
        if step_id not in stored.progress.completed_steps:
            stored.progress.completed_steps.append(step_id)
        
        # Update current step
        stored.progress.current_step = step_id + 1
        
        # Mark step as completed in plan
        for step in stored.plan.steps:
            if step.id == step_id:
                step.completed = True
                break
        
        stored.updated_at = datetime.utcnow()
        return stored
    
    def set_results(self, plan_id: str, results: dict) -> Optional[StoredPlan]:
        """Store execution results."""
        if plan_id not in self._plans:
            return None
        
        self._plans[plan_id].results = results
        self._plans[plan_id].updated_at = datetime.utcnow()
        return self._plans[plan_id]
    
    def delete(self, plan_id: str) -> bool:
        """Delete a plan."""
        if plan_id in self._plans:
            del self._plans[plan_id]
            return True
        return False
    
    def list_all(self) -> list[StoredPlan]:
        """List all plans."""
        return list(self._plans.values())
