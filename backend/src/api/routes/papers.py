"""
Papers API routes.

CRUD endpoints for paper management with pagination and filters.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId
import logging

from src.core.database import connect_mongodb, get_database, PAPERS_COLLECTION
from src.core.models import Paper, PaperStatus
from src.storage.repositories import PaperRepository
from src.auth.dependencies import get_current_user, get_optional_user
from src.core.models import User

logger = logging.getLogger(__name__)
router = APIRouter()
paper_repo = PaperRepository()


# ── Schemas ──

class PaperCreateRequest(BaseModel):
    title: str
    abstract: str = ""
    authors: List[str] = Field(default_factory=list)
    source: str = "manual"
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    published_date: Optional[datetime] = None


class PaperUpdateRequest(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    relevance_score: Optional[float] = None
    notes: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Endpoints ──

@router.get("")
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    plan_id: Optional[str] = None,
    min_score: Optional[float] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|relevance_score|title)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: Optional[User] = Depends(get_optional_user),
):
    """List papers with filters and pagination."""
    db = get_database()
    collection = db[PAPERS_COLLECTION]

    query: dict = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source
    if plan_id:
        query["plan_id"] = plan_id
    if min_score is not None:
        query["relevance_score"] = {"$gte": min_score}
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"abstract": {"$regex": keyword, "$options": "i"}},
        ]

    total = await collection.count_documents(query)
    sort_dir = 1 if sort_order == "asc" else -1
    skip = (page - 1) * page_size

    cursor = collection.find(query).sort(sort_by, sort_dir).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/{paper_id}")
async def get_paper(paper_id: str):
    """Get a single paper by ID."""
    paper = await paper_repo.get_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper.model_dump(by_alias=True)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_paper(
    req: PaperCreateRequest,
    user: User = Depends(get_current_user),
):
    """Manually create a paper."""
    paper = Paper(
        title=req.title,
        abstract=req.abstract,
        authors=req.authors,
        source=req.source,
        url=req.url,
        pdf_url=req.pdf_url,
        arxiv_id=req.arxiv_id,
        doi=req.doi,
        published_date=req.published_date,
    )

    paper_id = await paper_repo.create(paper)
    paper.id = paper_id

    return {"id": paper_id, "message": "Paper created"}


@router.put("/{paper_id}")
async def update_paper(
    paper_id: str,
    req: PaperUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update a paper's metadata."""
    existing = await paper_repo.get_by_id(paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"message": "No changes"}

    await paper_repo.update(paper_id, updates)
    return {"message": "Paper updated"}


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a paper."""
    db = get_database()
    result = await db[PAPERS_COLLECTION].delete_one({"_id": ObjectId(paper_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Paper not found")
    return {"message": "Paper deleted"}


# ── Related data endpoints ──

@router.get("/{paper_id}/study-card")
async def get_study_card(paper_id: str):
    """Get study card for a paper."""
    from src.storage.repositories import StudyCardRepository
    repo = StudyCardRepository()
    card = await repo.get_by_paper(paper_id)
    if not card:
        raise HTTPException(status_code=404, detail="Study card not found")
    return card.model_dump()


@router.get("/{paper_id}/screening")
async def get_screening_record(paper_id: str):
    """Get screening record for a paper."""
    from src.storage.repositories import ScreeningRecordRepository
    repo = ScreeningRecordRepository()
    record = await repo.get_by_paper(paper_id)
    if not record:
        raise HTTPException(status_code=404, detail="Screening record not found")
    return record.model_dump()


@router.get("/{paper_id}/evidence-spans")
async def get_evidence_spans(paper_id: str):
    """Get evidence spans for a paper."""
    from src.storage.repositories import EvidenceSpanRepository
    repo = EvidenceSpanRepository()
    spans = await repo.get_by_paper(paper_id)
    return [s.model_dump() for s in spans]
