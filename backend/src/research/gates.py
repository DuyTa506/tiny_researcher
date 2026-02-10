"""
HITL Approval Gate Manager

Implements human-in-the-loop approval gates for high-cost/high-risk actions.
Only asks for approval when action has meaningful cost or risk.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


class ApprovalGate(BaseModel):
    """A pending approval request for a high-cost action."""

    gate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gate_type: str  # pdf_download | external_crawl | high_token_budget
    context: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending | approved | rejected
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


class ApprovalGateManager:
    """
    Manages HITL approval gates for the research pipeline.

    Gates are triggered at specific points:
    - Before downloading many PDFs (cost: bandwidth + time)
    - Before crawling external URLs (risk: unknown domains)
    - Before high token budget operations (cost: API usage)

    Default behavior: auto-approve unless thresholds are exceeded.
    """

    PDF_DOWNLOAD_THRESHOLD = 15  # Ask approval if > 15 PDFs
    TOKEN_BUDGET_THRESHOLD = 100000  # Ask approval if > 100k tokens estimated

    def __init__(self):
        self.pending_gates: List[ApprovalGate] = []
        self.resolved_gates: List[ApprovalGate] = []
        self._approval_callback = None

    def set_approval_callback(self, callback):
        """Set callback for requesting user approval (SSE/WebSocket/CLI)."""
        self._approval_callback = callback

    def check_pdf_gate(
        self, included_count: int, max_pdf: int = 20
    ) -> Optional[ApprovalGate]:
        """
        Check if PDF download count warrants approval.

        Returns ApprovalGate if approval needed, None if auto-approved.
        """
        if included_count <= self.PDF_DOWNLOAD_THRESHOLD:
            return None

        gate = ApprovalGate(
            gate_type="pdf_download",
            context={
                "papers_to_download": included_count,
                "max_pdf": max_pdf,
                "estimated_bandwidth_mb": included_count * 2,  # ~2MB per PDF
            },
        )
        self.pending_gates.append(gate)
        logger.info(
            f"PDF download gate created: {included_count} papers "
            f"(threshold: {self.PDF_DOWNLOAD_THRESHOLD})"
        )
        return gate

    def check_url_gate(self, urls: List[str]) -> Optional[ApprovalGate]:
        """
        Check if any URLs are from non-standard domains.

        Standard domains: arxiv.org, huggingface.co
        """
        from urllib.parse import urlparse

        standard_domains = {"arxiv.org", "huggingface.co", "hf.co"}
        external_urls = []

        for url in urls:
            try:
                domain = urlparse(url).netloc.lower()
                # Strip www prefix
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain not in standard_domains:
                    external_urls.append(url)
            except Exception:
                external_urls.append(url)

        if not external_urls:
            return None

        gate = ApprovalGate(
            gate_type="external_crawl",
            context={
                "external_urls": external_urls,
                "count": len(external_urls),
            },
        )
        self.pending_gates.append(gate)
        logger.info(f"External crawl gate created: {len(external_urls)} URLs")
        return gate

    def check_token_gate(
        self, estimated_tokens: int, budget: Optional[int] = None
    ) -> Optional[ApprovalGate]:
        """Check if estimated token usage exceeds budget."""
        threshold = budget or self.TOKEN_BUDGET_THRESHOLD
        if estimated_tokens <= threshold:
            return None

        gate = ApprovalGate(
            gate_type="high_token_budget",
            context={
                "estimated_tokens": estimated_tokens,
                "budget_threshold": threshold,
                "estimated_cost_usd": estimated_tokens * 0.00001,  # rough estimate
            },
        )
        self.pending_gates.append(gate)
        logger.info(
            f"Token budget gate created: {estimated_tokens} tokens "
            f"(threshold: {threshold})"
        )
        return gate

    async def request_approval(self, gate: ApprovalGate) -> bool:
        """
        Request user approval for a gate.

        If no callback is set, auto-approves (development mode).
        """
        if self._approval_callback:
            approved = await self._approval_callback(gate)
        else:
            # Auto-approve in development mode
            logger.info(
                f"Auto-approving gate {gate.gate_type} " f"(no approval callback set)"
            )
            approved = True

        gate.status = "approved" if approved else "rejected"
        gate.resolved_at = datetime.now()
        self.pending_gates.remove(gate)
        self.resolved_gates.append(gate)

        return approved

    def get_gate_summary(self, gate: ApprovalGate) -> str:
        """Get human-readable summary of a gate for display."""
        if gate.gate_type == "pdf_download":
            n = gate.context.get("papers_to_download", 0)
            mb = gate.context.get("estimated_bandwidth_mb", 0)
            return f"Download PDFs for {n} papers (~{mb}MB bandwidth). " f"Proceed?"
        elif gate.gate_type == "external_crawl":
            urls = gate.context.get("external_urls", [])
            return (
                f"Crawl {len(urls)} external URL(s): "
                f"{', '.join(urls[:3])}{'...' if len(urls) > 3 else ''}. "
                f"Proceed?"
            )
        elif gate.gate_type == "high_token_budget":
            tokens = gate.context.get("estimated_tokens", 0)
            cost = gate.context.get("estimated_cost_usd", 0)
            return f"Estimated {tokens:,} tokens (~${cost:.2f}). " f"Proceed?"
        return f"Approval needed for {gate.gate_type}. Proceed?"
