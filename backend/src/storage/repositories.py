"""
MongoDB Repositories

CRUD operations for MongoDB collections.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from src.core.database import (
    get_database,
    PAPERS_COLLECTION,
    CLUSTERS_COLLECTION,
    REPORTS_COLLECTION,
    SCREENING_RECORDS_COLLECTION,
    EVIDENCE_SPANS_COLLECTION,
    STUDY_CARDS_COLLECTION,
    CLAIMS_COLLECTION,
    TAXONOMY_MATRIX_COLLECTION,
)
from src.core.models import (
    Paper,
    PaperStatus,
    Cluster,
    Report,
    EvidenceSpan,
    StudyCard,
    ScreeningRecord,
    Claim,
    TaxonomyMatrix,
)

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

    async def get_by_plan(
        self, plan_id: str, status: Optional[PaperStatus] = None
    ) -> List[Paper]:
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
            {"_id": ObjectId(paper_id)}, {"$set": updates}
        )
        return result.modified_count > 0

    async def update_score(self, paper_id: str, score: float) -> bool:
        """Update relevance score and status."""
        return await self.update(
            paper_id, {"relevance_score": score, "status": PaperStatus.SCORED.value}
        )

    async def update_summary(self, paper_id: str, summary: dict) -> bool:
        """Update paper summary."""
        return await self.update(
            paper_id, {"summary": summary, "status": PaperStatus.SUMMARIZED.value}
        )

    async def get_relevant(self, plan_id: str, min_score: float = 7.0) -> List[Paper]:
        """Get papers with relevance score >= threshold."""
        query = {"plan_id": plan_id, "relevance_score": {"$gte": min_score}}
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


class ScreeningRecordRepository:
    """Repository for ScreeningRecord documents."""

    @property
    def collection(self):
        return get_database()[SCREENING_RECORDS_COLLECTION]

    async def create(self, record: ScreeningRecord) -> str:
        doc = record.model_dump(by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_many(self, records: List[ScreeningRecord]) -> List[str]:
        if not records:
            return []
        docs = [r.model_dump(by_alias=True) for r in records]
        result = await self.collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]

    async def get_by_paper(self, paper_id: str) -> Optional[ScreeningRecord]:
        doc = await self.collection.find_one({"paper_id": paper_id})
        if doc:
            doc.pop("_id", None)
            return ScreeningRecord(**doc)
        return None

    async def get_included_paper_ids(self, plan_id: str) -> List[str]:
        """Get paper_ids that passed screening for a plan."""
        pipeline = [
            {"$match": {"include": True}},
            {
                "$lookup": {
                    "from": PAPERS_COLLECTION,
                    "localField": "paper_id",
                    "foreignField": "_id",
                    "as": "paper",
                }
            },
            {"$unwind": "$paper"},
            {"$match": {"paper.plan_id": plan_id}},
            {"$project": {"paper_id": 1}},
        ]
        # Simpler approach: query papers by plan_id first, then filter screening
        cursor = self.collection.find({"include": True})
        ids = []
        async for doc in cursor:
            ids.append(doc["paper_id"])
        return ids

    async def get_by_plan_papers(self, paper_ids: List[str]) -> List[ScreeningRecord]:
        """Get screening records for a list of paper IDs."""
        cursor = self.collection.find({"paper_id": {"$in": paper_ids}})
        records = []
        async for doc in cursor:
            doc.pop("_id", None)
            records.append(ScreeningRecord(**doc))
        return records

    async def count_included(self, paper_ids: List[str]) -> int:
        return await self.collection.count_documents(
            {
                "paper_id": {"$in": paper_ids},
                "include": True,
            }
        )

    async def count_excluded(self, paper_ids: List[str]) -> int:
        return await self.collection.count_documents(
            {
                "paper_id": {"$in": paper_ids},
                "include": False,
            }
        )


class EvidenceSpanRepository:
    """Repository for EvidenceSpan documents."""

    @property
    def collection(self):
        return get_database()[EVIDENCE_SPANS_COLLECTION]

    async def create(self, span: EvidenceSpan) -> str:
        doc = span.model_dump(by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_many(self, spans: List[EvidenceSpan]) -> List[str]:
        if not spans:
            return []
        docs = [s.model_dump(by_alias=True) for s in spans]
        result = await self.collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]

    async def get_by_paper(self, paper_id: str) -> List[EvidenceSpan]:
        cursor = self.collection.find({"paper_id": paper_id})
        spans = []
        async for doc in cursor:
            doc.pop("_id", None)
            spans.append(EvidenceSpan(**doc))
        return spans

    async def get_by_ids(self, span_ids: List[str]) -> List[EvidenceSpan]:
        cursor = self.collection.find({"span_id": {"$in": span_ids}})
        spans = []
        async for doc in cursor:
            doc.pop("_id", None)
            spans.append(EvidenceSpan(**doc))
        return spans

    async def get_by_field(self, paper_id: str, field: str) -> List[EvidenceSpan]:
        cursor = self.collection.find({"paper_id": paper_id, "field": field})
        spans = []
        async for doc in cursor:
            doc.pop("_id", None)
            spans.append(EvidenceSpan(**doc))
        return spans

    async def get_by_paper_ids(self, paper_ids: List[str]) -> List[EvidenceSpan]:
        cursor = self.collection.find({"paper_id": {"$in": paper_ids}})
        spans = []
        async for doc in cursor:
            doc.pop("_id", None)
            spans.append(EvidenceSpan(**doc))
        return spans


class StudyCardRepository:
    """Repository for StudyCard documents."""

    @property
    def collection(self):
        return get_database()[STUDY_CARDS_COLLECTION]

    async def create(self, card: StudyCard) -> str:
        doc = card.model_dump(by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_many(self, cards: List[StudyCard]) -> List[str]:
        if not cards:
            return []
        docs = [c.model_dump(by_alias=True) for c in cards]
        result = await self.collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]

    async def get_by_paper(self, paper_id: str) -> Optional[StudyCard]:
        doc = await self.collection.find_one({"paper_id": paper_id})
        if doc:
            doc.pop("_id", None)
            return StudyCard(**doc)
        return None

    async def get_by_paper_ids(self, paper_ids: List[str]) -> List[StudyCard]:
        cursor = self.collection.find({"paper_id": {"$in": paper_ids}})
        cards = []
        async for doc in cursor:
            doc.pop("_id", None)
            cards.append(StudyCard(**doc))
        return cards


class ClaimRepository:
    """Repository for Claim documents."""

    @property
    def collection(self):
        return get_database()[CLAIMS_COLLECTION]

    async def create(self, claim: Claim) -> str:
        doc = claim.model_dump(by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def create_many(self, claims: List[Claim]) -> List[str]:
        if not claims:
            return []
        docs = [c.model_dump(by_alias=True) for c in claims]
        result = await self.collection.insert_many(docs)
        return [str(id) for id in result.inserted_ids]

    async def get_by_theme(self, theme_id: str) -> List[Claim]:
        cursor = self.collection.find({"theme_id": theme_id})
        claims = []
        async for doc in cursor:
            doc.pop("_id", None)
            claims.append(Claim(**doc))
        return claims

    async def get_by_plan_themes(self, theme_ids: List[str]) -> List[Claim]:
        cursor = self.collection.find({"theme_id": {"$in": theme_ids}})
        claims = []
        async for doc in cursor:
            doc.pop("_id", None)
            claims.append(Claim(**doc))
        return claims

    async def get_uncited(self) -> List[Claim]:
        cursor = self.collection.find({"evidence_span_ids": {"$size": 0}})
        claims = []
        async for doc in cursor:
            doc.pop("_id", None)
            claims.append(Claim(**doc))
        return claims

    async def update_evidence(self, claim_id: str, span_ids: List[str]) -> bool:
        result = await self.collection.update_one(
            {"claim_id": claim_id},
            {"$set": {"evidence_span_ids": span_ids}},
        )
        return result.modified_count > 0

    async def update_claim(self, claim_id: str, updates: Dict[str, Any]) -> bool:
        result = await self.collection.update_one(
            {"claim_id": claim_id},
            {"$set": updates},
        )
        return result.modified_count > 0


class TaxonomyMatrixRepository:
    """Repository for TaxonomyMatrix documents."""

    @property
    def collection(self):
        return get_database()[TAXONOMY_MATRIX_COLLECTION]

    async def create(self, taxonomy: TaxonomyMatrix) -> str:
        doc = taxonomy.model_dump(exclude={"id"}, by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_plan(self, plan_id: str) -> Optional[TaxonomyMatrix]:
        doc = await self.collection.find_one({"plan_id": plan_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return TaxonomyMatrix(**doc)
        return None
