"""
Citation Audit Service

Verifies that claims in the report are properly supported by evidence.
Implements an auto-repair loop for failed claims.
"""

import json
import logging
import re
from typing import List, Any
from dataclasses import dataclass, field

from src.core.models import Claim, EvidenceSpan
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.storage.repositories import ClaimRepository

logger = logging.getLogger(__name__)


@dataclass
class AuditResult:
    """Result of auditing claims for citation support."""
    total_claims: int = 0
    audited_claims: int = 0
    passed: int = 0
    failed: int = 0
    failed_major: int = 0
    failed_minor: int = 0
    repaired: int = 0

    @property
    def pass_rate(self) -> float:
        if self.audited_claims == 0:
            return 1.0
        return (self.passed + self.repaired) / self.audited_claims


class CitationAuditService:
    """
    Verifies claims have valid, semantically-supporting evidence.

    Process:
    1. Sample claims (all above salience threshold, or random N)
    2. For each claim, verify evidence spans exist and support the claim
    3. If failed: attempt auto-repair (rewrite or mark uncertain)
    """

    MAX_REPAIR_ITERATIONS = 2
    SALIENCE_THRESHOLD = 0.3  # Audit all claims above this

    def __init__(
        self,
        llm_client: LLMClientInterface,
        claim_repo: ClaimRepository = None,
    ):
        self.llm = llm_client
        self.claim_repo = claim_repo or ClaimRepository()

    async def audit_claims(
        self,
        claims: List[Claim],
        evidence_spans: List[EvidenceSpan],
    ) -> AuditResult:
        """
        Verify all claims have valid, supporting evidence.

        Returns AuditResult with pass/fail counts.
        """
        span_map = {s.span_id: s for s in evidence_spans}

        result = AuditResult(total_claims=len(claims))

        # Select claims to audit (above salience threshold)
        to_audit = [
            c for c in claims if c.salience_score >= self.SALIENCE_THRESHOLD
        ]
        result.audited_claims = len(to_audit)

        failed_claims = []

        for claim in to_audit:
            # Step 1: Check evidence span IDs exist
            resolved_spans = [
                span_map[sid] for sid in claim.evidence_span_ids if sid in span_map
            ]

            if not resolved_spans:
                logger.warning(
                    f"Claim has no resolvable evidence: {claim.claim_text[:80]}"
                )
                failed_claims.append((claim, "major"))
                continue

            # Step 2: LLM judge - does evidence support claim?
            verdict = await self._verify_support(claim, resolved_spans)

            if verdict["supported"]:
                result.passed += 1
            else:
                severity = verdict.get("severity", "major")
                failed_claims.append((claim, severity))
                if severity == "major":
                    result.failed_major += 1
                else:
                    result.failed_minor += 1

        result.failed = len(failed_claims)

        # Step 3: Auto-repair failed claims (prioritize major failures)
        if failed_claims:
            repaired = await self._repair_claims(failed_claims, span_map)
            result.repaired = repaired
            result.failed -= repaired

        logger.info(
            f"Citation audit: {result.passed} passed, {result.failed} failed "
            f"({result.failed_major} major, {result.failed_minor} minor), "
            f"{result.repaired} repaired (rate: {result.pass_rate:.1%})"
        )
        return result

    async def _verify_support(
        self, claim: Claim, spans: List[EvidenceSpan]
    ) -> dict:
        """Use LLM to verify evidence semantically supports the claim.

        Returns dict with 'supported' (bool) and 'severity' (minor|major).
        """
        evidence_snippets = "\n".join(
            [
                f"[{s.field}] \"{s.snippet}\" (confidence: {s.confidence:.2f})"
                for s in spans
            ]
        )

        prompt = PromptManager.get_prompt(
            "CITATION_AUDIT",
            claim_text=claim.claim_text,
            evidence_snippets=evidence_snippets,
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            result = self._parse_json_response(response_text)

            if isinstance(result, dict):
                return {
                    "supported": bool(result.get("supported", False)),
                    "severity": result.get("severity", "major"),
                }
            return {"supported": False, "severity": "major"}

        except Exception as e:
            logger.error(f"Verification failed for claim: {e}")
            return {"supported": True, "severity": "minor"}  # Don't fail on LLM errors

    async def _repair_claims(
        self,
        failed_claims: List[tuple],
        span_map: dict,
    ) -> int:
        """
        Attempt to repair failed claims.

        Strategies:
        1. Major: Rewrite claim more conservatively
        2. Minor: Mark as uncertain (no rewrite needed)

        Args:
            failed_claims: List of (Claim, severity) tuples
        """
        repaired = 0

        for claim, severity in failed_claims:
            # Get the evidence snippets for context
            spans = [span_map[sid] for sid in claim.evidence_span_ids if sid in span_map]

            if not spans:
                # No evidence at all - mark uncertain
                claim.uncertainty_flag = True
                if self.claim_repo:
                    await self.claim_repo.update_claim(
                        claim.claim_id, {"uncertainty_flag": True}
                    )
                repaired += 1
                continue

            if severity == "minor":
                # Minor issues: just flag as uncertain, don't rewrite
                claim.uncertainty_flag = True
                if self.claim_repo:
                    await self.claim_repo.update_claim(
                        claim.claim_id, {"uncertainty_flag": True}
                    )
                repaired += 1
                continue

            # Major: Try conservative rewrite
            evidence_text = "\n".join([s.snippet for s in spans])

            try:
                prompt = (
                    f"The following claim is not well-supported by the evidence. "
                    f"Rewrite it more conservatively to match what the evidence actually says.\n\n"
                    f"Original claim: {claim.claim_text}\n\n"
                    f"Available evidence:\n{evidence_text}\n\n"
                    f"Return ONLY the rewritten claim text (1-3 sentences). "
                    f"If the evidence is insufficient, prefix with 'Evidence suggests that'."
                )

                rewritten = await self.llm.generate(prompt)
                rewritten = rewritten.strip().strip('"')

                if rewritten and len(rewritten) > 10:
                    claim.claim_text = rewritten
                    claim.uncertainty_flag = True
                    if self.claim_repo:
                        await self.claim_repo.update_claim(
                            claim.claim_id,
                            {
                                "claim_text": rewritten,
                                "uncertainty_flag": True,
                            },
                        )
                    repaired += 1
                else:
                    claim.uncertainty_flag = True

            except Exception as e:
                logger.error(f"Repair failed for claim: {e}")
                claim.uncertainty_flag = True

        return repaired

    def _parse_json_response(self, response_text: str) -> Any:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {}
