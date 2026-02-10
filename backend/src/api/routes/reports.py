"""
Reports API routes.

CRUD endpoints for report management with export functionality.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import logging

from src.core.database import get_database, REPORTS_COLLECTION, CLAIMS_COLLECTION
from src.core.models import User
from src.storage.repositories import ReportRepository, ClaimRepository
from src.auth.dependencies import get_current_user, get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter()
report_repo = ReportRepository()
claim_repo = ClaimRepository()


# ── Schemas ──


class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# ── Endpoints ──


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    user: Optional[User] = Depends(get_optional_user),
):
    """List all reports with pagination."""
    db = get_database()
    collection = db[REPORTS_COLLECTION]

    query: dict = {}
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"content": {"$regex": keyword, "$options": "i"}},
        ]

    total = await collection.count_documents(query)
    skip = (page - 1) * page_size

    cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        # Don't include full content in list view
        doc.pop("content", None)
        items.append(doc)

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get a single report by ID."""
    db = get_database()
    doc = await db[REPORTS_COLLECTION].find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.put("/{report_id}")
async def update_report(
    report_id: str,
    req: ReportUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update a report's title or content."""
    db = get_database()
    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"message": "No changes"}

    updates["updated_at"] = datetime.now()
    result = await db[REPORTS_COLLECTION].update_one(
        {"_id": ObjectId(report_id)},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report updated"}


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a report."""
    db = get_database()
    result = await db[REPORTS_COLLECTION].delete_one({"_id": ObjectId(report_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted"}


@router.get("/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = Query("markdown", pattern="^(markdown|html)$"),
):
    """Export a report as Markdown or HTML."""
    db = get_database()
    doc = await db[REPORTS_COLLECTION].find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    content = doc.get("content", "")
    title = doc.get("title", "report")

    if format == "html":
        # Simple Markdown-to-HTML conversion
        try:
            import markdown

            html_content = markdown.markdown(
                content, extensions=["tables", "fenced_code"]
            )
        except ImportError:
            html_content = f"<pre>{content}</pre>"

        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{title}.html"'},
        )

    # Default: Markdown
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{title}.md"'},
    )


@router.get("/{report_id}/claims")
async def get_report_claims(report_id: str):
    """Get claims associated with a report's plan."""
    db = get_database()
    doc = await db[REPORTS_COLLECTION].find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    plan_id = doc.get("plan_id")
    if not plan_id:
        return []

    # Get clusters for the plan to find theme IDs
    from src.storage.repositories import ClusterRepository

    cluster_repo = ClusterRepository()
    clusters = await cluster_repo.get_by_plan(plan_id)
    theme_ids = [str(c.id) for c in clusters if c.id]

    if not theme_ids:
        return []

    claims = await claim_repo.get_by_plan_themes(theme_ids)
    return [c.model_dump() for c in claims]


@router.get("/{report_id}/taxonomy")
async def get_report_taxonomy(report_id: str):
    """Get taxonomy matrix for a report."""
    db = get_database()
    doc = await db[REPORTS_COLLECTION].find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    plan_id = doc.get("plan_id")
    if not plan_id:
        return None

    from src.storage.repositories import TaxonomyMatrixRepository

    taxonomy_repo = TaxonomyMatrixRepository()
    taxonomy = await taxonomy_repo.get_by_plan(plan_id)
    if not taxonomy:
        return None
    return taxonomy.model_dump()


@router.get("/{report_id}/citation-audit")
async def get_citation_audit(report_id: str):
    """Get citation audit status derived from claims."""
    db = get_database()
    doc = await db[REPORTS_COLLECTION].find_one({"_id": ObjectId(report_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    plan_id = doc.get("plan_id")
    if not plan_id:
        return {"total": 0, "verified": 0, "uncertain": 0}

    from src.storage.repositories import ClusterRepository

    cluster_repo = ClusterRepository()
    clusters = await cluster_repo.get_by_plan(plan_id)
    theme_ids = [str(c.id) for c in clusters if c.id]

    if not theme_ids:
        return {"total": 0, "verified": 0, "uncertain": 0}

    claims = await claim_repo.get_by_plan_themes(theme_ids)
    total = len(claims)
    uncertain = sum(1 for c in claims if c.uncertainty_flag)
    verified = total - uncertain

    return {"total": total, "verified": verified, "uncertain": uncertain}
