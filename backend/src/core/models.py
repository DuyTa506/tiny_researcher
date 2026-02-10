"""
MongoDB Models (Pydantic)

Document schemas for MongoDB collections.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class PaperStatus(str, Enum):
    """Status of paper processing."""

    RAW = "raw"  # Just collected
    SCREENED = "screened"  # Title/abstract screening completed
    FULLTEXT = "fulltext"  # Full text loaded
    EXTRACTED = "extracted"  # Evidence extracted
    SCORED = "scored"  # Relevance scored (legacy)
    SUMMARIZED = "summarized"  # Summary extracted (legacy)
    INDEXED = "indexed"  # In vector store
    REPORTED = "reported"  # Included in final report


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

    # Citation-first additions
    metadata_hash: Optional[str] = None  # Hash of title+authors for dedup
    pdf_hash: Optional[str] = None  # Hash of PDF content
    page_map: Optional[Dict[str, Any]] = None  # Page-level text mapping

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper from raw dict (from tools)."""
        # Determine source from source_type or source field
        source = data.get("source_type", data.get("source", "arxiv"))
        # Normalize source_type values to source values
        if source == "arxiv_api":
            source = "arxiv"
        elif source == "huggingface_trending":
            source = "huggingface"

        return cls(
            arxiv_id=data.get("arxiv_id"),
            doi=data.get("doi"),
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=data.get("authors", []),
            published_date=data.get("published"),
            source=source,
            url=data.get("url"),
            pdf_url=data.get("pdf_url"),
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


# ============================================================
# Citation-First Workflow Models (Phase 1)
# ============================================================


class Locator(BaseModel):
    """Evidence location within a paper.

    Tracks where evidence was found in the source document.
    Best-effort: page number if available, otherwise section/char offsets.
    """

    page: Optional[int] = None  # PDF page number
    section: Optional[str] = None  # Section heading if parseable
    char_start: Optional[int] = None  # Character offset in full text
    char_end: Optional[int] = None  # End of evidence span


class EvidenceSpan(BaseModel):
    """Traceable evidence snippet from a paper.

    Core primitive for citation-first workflow. Every claim in the
    final report must reference at least one EvidenceSpan.
    """

    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_id: str  # Reference to Paper.id

    # What kind of evidence is this?
    field: Literal[
        "problem", "method", "dataset", "metric", "result", "limitation", "other"
    ]

    # The evidence itself
    snippet: str = Field(..., max_length=300)  # Short quote from paper
    locator: Locator  # Where in the paper
    confidence: float = Field(ge=0.0, le=1.0)  # Extraction confidence
    source_url: str  # PDF or paper URL for attribution

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True


class StudyCard(BaseModel):
    """Structured extraction from a paper.

    Replaces the loose PaperSummary with schema-driven extraction.
    All fields MUST be backed by EvidenceSpans for auditability.
    """

    card_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_id: str

    # Structured fields (evidence-backed)
    problem: Optional[str] = None  # What problem does this address?
    method: Optional[str] = None  # What approach/technique?
    datasets: List[str] = Field(default_factory=list)  # Evaluation datasets
    metrics: List[str] = Field(default_factory=list)  # Evaluation metrics
    results: List[str] = Field(default_factory=list)  # Key findings
    limitations: List[str] = Field(default_factory=list)  # Stated limitations

    # CRITICAL: All populated fields must have evidence
    evidence_span_ids: List[str] = Field(default_factory=list)

    # Extraction metadata for reproducibility
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)
    # Expected keys: model, prompt_version, timestamp, source_type

    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True


class ScreeningRecord(BaseModel):
    """Title/abstract screening decision.

    Implements systematic review screening step with 3-tier system:
    - core: directly relevant, new contribution → full-text analysis
    - background: survey, context, indirect → include for background
    - exclude: out of scope → skip

    The `include` field is derived from tier for backward compatibility.
    """

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_id: str

    # Decision (3-tier)
    tier: Literal["core", "background", "exclude"] = "core"
    include: bool = True  # Derived: True if tier != "exclude"

    # Reasoning
    reason_code: str  # Structured code: relevant, out_of_scope, survey_context, missing_eval, etc.
    rationale_short: str = Field(..., max_length=500)  # Brief explanation

    # Optional relevance score (0-10)
    scored_relevance: Optional[float] = Field(None, ge=0.0, le=10.0)

    # Audit trail
    screened_at: datetime = Field(default_factory=datetime.now)
    screened_by: str = "llm"  # "llm" or human user ID for HITL

    class Config:
        populate_by_name = True


class Claim(BaseModel):
    """Atomic citable claim in the report.

    Core unit of the grounded synthesis. Each claim is a single factual
    statement backed by ≥1 evidence spans. The final report is composed
    entirely of cited claims.
    """

    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim_text: str  # The assertion (1-3 sentences)

    # MANDATORY: Every claim must cite evidence
    evidence_span_ids: List[str] = Field(..., min_length=1)

    # Organization
    theme_id: Optional[str] = None  # Cluster/theme this belongs to

    # Importance
    salience_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Quality flags
    uncertainty_flag: bool = False  # Mark if evidence is weak/contradictory

    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True


class TaxonomyMatrix(BaseModel):
    """Structured view of the research landscape.

    Multi-dimensional matrix showing coverage across themes, datasets,
    metrics, and method families. Used to identify gaps for future work.
    """

    id: Optional[str] = Field(None, alias="_id")
    plan_id: Optional[str] = None

    # Dimensions
    themes: List[str] = Field(default_factory=list)
    datasets: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    method_families: List[str] = Field(default_factory=list)

    # Cells: "(theme, dataset, metric)" -> [paper_ids]
    cells: Dict[str, List[str]] = Field(default_factory=dict)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True


class PageInfo(BaseModel):
    """Page-level metadata for PDF locator tracking."""

    text: str
    char_start: int
    char_end: int


# ============================================================
# User / Auth Models
# ============================================================


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    RESEARCHER = "researcher"


class UserPreferences(BaseModel):
    language: str = "en"
    theme: str = "light"
    default_max_papers: int = 20
    notifications_enabled: bool = True


class UserUsageStats(BaseModel):
    papers_collected: int = 0
    reports_generated: int = 0
    research_sessions: int = 0


class User(BaseModel):
    """User account document for MongoDB."""

    id: Optional[str] = Field(None, alias="_id")
    email: str
    username: str
    password_hash: str
    role: UserRole = UserRole.USER

    # Profile
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # Status
    is_active: bool = True
    email_verified: bool = False

    # Tokens for email flows
    verification_token: Optional[str] = None
    reset_token: Optional[str] = None
    reset_token_expires: Optional[datetime] = None

    # OAuth
    oauth_provider: Optional[str] = None  # "google"
    oauth_id: Optional[str] = None

    # Preferences
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    usage_stats: UserUsageStats = Field(default_factory=UserUsageStats)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    class Config:
        populate_by_name = True
