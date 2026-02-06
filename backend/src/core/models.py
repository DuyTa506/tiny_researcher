"""
MongoDB Models (Pydantic)

Document schemas for MongoDB collections.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PaperStatus(str, Enum):
    """Status of paper processing."""
    RAW = "raw"           # Just collected
    SCORED = "scored"     # Relevance scored
    SUMMARIZED = "summarized"  # Summary extracted
    INDEXED = "indexed"   # In vector store


class PaperSummary(BaseModel):
    """Extracted summary from a paper."""
    problem: str = ""
    approach: str = ""
    results: str = ""
    limitations: str = ""
    key_findings: List[str] = Field(default_factory=list)


class Paper(BaseModel):
    """Paper document for MongoDB."""
    # Identifiers
    id: Optional[str] = Field(None, alias="_id")
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    
    # Core metadata
    title: str
    abstract: str = ""
    authors: List[str] = Field(default_factory=list)
    published_date: Optional[datetime] = None
    source: str = "arxiv"  # arxiv, huggingface, url
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None  # Full PDF text content
    
    # Processing results
    status: PaperStatus = PaperStatus.RAW
    relevance_score: Optional[float] = None
    summary: Optional[PaperSummary] = None
    cluster_id: Optional[str] = None
    
    # Research context
    plan_id: Optional[str] = None  # Which research plan collected this
    step_id: Optional[int] = None  # Which step
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        populate_by_name = True
        
    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper from raw dict (from tools)."""
        return cls(
            arxiv_id=data.get("arxiv_id"),
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=data.get("authors", []),
            published_date=data.get("published"),
            source=data.get("source", "arxiv"),
            url=data.get("url"),
            pdf_url=data.get("pdf_url")
        )


class Cluster(BaseModel):
    """Cluster of related papers."""
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: str = ""
    paper_ids: List[str] = Field(default_factory=list)
    plan_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        populate_by_name = True


class Report(BaseModel):
    """Generated research report."""
    id: Optional[str] = Field(None, alias="_id")
    plan_id: str
    title: str
    content: str  # Markdown content
    clusters: List[str] = Field(default_factory=list)  # Cluster IDs
    paper_count: int = 0
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        populate_by_name = True
