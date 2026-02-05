"""
MongoDB Repositories

CRUD operations for MongoDB collections.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from src.core.database import get_database, PAPERS_COLLECTION, CLUSTERS_COLLECTION, REPORTS_COLLECTION
from src.core.models import Paper, PaperStatus, Cluster, Report

logger = logging.getLogger(__name__)


class PaperRepository:
    """Repository for Paper documents."""
    
    @property
    def collection(self):
        return get_database()[PAPERS_COLLECTION]
    
    async def create(self, paper: Paper) -> str:
        """Insert a new paper and return its ID."""
        doc = paper.model_dump(exclude={"id"}, by_alias=True)
        doc["updated_at"] = datetime.now()
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def create_many(self, papers: List[Paper]) -> List[str]:
        """Insert multiple papers and return their IDs."""
        if not papers:
            return []
        
        docs = []
        for paper in papers:
            doc = paper.model_dump(exclude={"id"}, by_alias=True)
            doc["updated_at"] = datetime.now()
            docs.append(doc)
        
        result = await self.collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]
    
    async def get_by_id(self, paper_id: str) -> Optional[Paper]:
        """Get paper by ID."""
        doc = await self.collection.find_one({"_id": ObjectId(paper_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Paper(**doc)
        return None
    
    async def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """Get paper by ArXiv ID."""
        doc = await self.collection.find_one({"arxiv_id": arxiv_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Paper(**doc)
        return None
    
    async def get_by_plan(self, plan_id: str, status: Optional[PaperStatus] = None) -> List[Paper]:
        """Get all papers for a research plan."""
        query = {"plan_id": plan_id}
        if status:
            query["status"] = status.value
        
        cursor = self.collection.find(query)
        papers = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            papers.append(Paper(**doc))
        return papers
    
    async def update(self, paper_id: str, updates: Dict[str, Any]) -> bool:
        """Update a paper."""
        updates["updated_at"] = datetime.now()
        result = await self.collection.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    async def update_score(self, paper_id: str, score: float) -> bool:
        """Update relevance score and status."""
        return await self.update(paper_id, {
            "relevance_score": score,
            "status": PaperStatus.SCORED.value
        })
    
    async def update_summary(self, paper_id: str, summary: dict) -> bool:
        """Update paper summary."""
        return await self.update(paper_id, {
            "summary": summary,
            "status": PaperStatus.SUMMARIZED.value
        })
    
    async def get_relevant(self, plan_id: str, min_score: float = 7.0) -> List[Paper]:
        """Get papers with relevance score >= threshold."""
        query = {
            "plan_id": plan_id,
            "relevance_score": {"$gte": min_score}
        }
        cursor = self.collection.find(query).sort("relevance_score", -1)
        papers = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            papers.append(Paper(**doc))
        return papers
    
    async def count_by_plan(self, plan_id: str) -> int:
        """Count papers for a plan."""
        return await self.collection.count_documents({"plan_id": plan_id})
    
    async def exists_arxiv_id(self, arxiv_id: str) -> bool:
        """Check if paper with arxiv_id exists."""
        return await self.collection.count_documents({"arxiv_id": arxiv_id}) > 0


class ClusterRepository:
    """Repository for Cluster documents."""
    
    @property
    def collection(self):
        return get_database()[CLUSTERS_COLLECTION]
    
    async def create(self, cluster: Cluster) -> str:
        """Insert a new cluster."""
        doc = cluster.model_dump(exclude={"id"}, by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_by_plan(self, plan_id: str) -> List[Cluster]:
        """Get all clusters for a plan."""
        cursor = self.collection.find({"plan_id": plan_id})
        clusters = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            clusters.append(Cluster(**doc))
        return clusters


class ReportRepository:
    """Repository for Report documents."""
    
    @property
    def collection(self):
        return get_database()[REPORTS_COLLECTION]
    
    async def create(self, report: Report) -> str:
        """Insert a new report."""
        doc = report.model_dump(exclude={"id"}, by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_by_plan(self, plan_id: str) -> Optional[Report]:
        """Get report for a plan."""
        doc = await self.collection.find_one({"plan_id": plan_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Report(**doc)
        return None
