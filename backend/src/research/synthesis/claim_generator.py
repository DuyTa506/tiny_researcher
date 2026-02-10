"""
Claim Generator Service

Converts StudyCards into atomic, citable Claims grouped by theme.
Each claim is a single factual statement backed by evidence spans.
"""

import json
import logging
import re
from typing import List, Any

from src.core.models import Claim, StudyCard, EvidenceSpan
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.storage.repositories import ClaimRepository

logger = logging.getLogger(__name__)


class ClaimGeneratorService:
    """
    Generates atomic citable claims from study cards and evidence.

    Claims are the building blocks for the grounded synthesis report.
    Every claim must reference at least one evidence span.
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        claim_repo: ClaimRepository = None,
    ):
        self.llm = llm_client
        self.claim_repo = claim_repo or ClaimRepository()

    async def generate_claims(
        self,
        study_cards: List[StudyCard],
        evidence_spans: List[EvidenceSpan],
        clusters: List[dict],
        language: str = "en",
    ) -> List[Claim]:
        """
        Generate claims for all themes/clusters.

        Args:
            study_cards: Extracted study cards from papers
            evidence_spans: All evidence spans across papers
            clusters: List of cluster dicts with 'id', 'name', 'paper_ids'

        Returns:
            List of generated Claims
        """
        # Build lookup maps
        card_by_paper = {c.paper_id: c for c in study_cards}
        span_by_id = {s.span_id: s for s in evidence_spans}

        all_claims: List[Claim] = []

        for cluster in clusters:
            cluster_id = str(cluster.get("id") or cluster.get("name", "unknown"))
            cluster_name = cluster.get("name", "Unnamed Theme")
            paper_ids = cluster.get("paper_ids", [])

            # Gather study cards for this cluster
            cluster_cards = [
                card_by_paper[pid] for pid in paper_ids if pid in card_by_paper
            ]
            if not cluster_cards:
                continue

            # Gather evidence spans for these cards
            cluster_span_ids = set()
            for card in cluster_cards:
                cluster_span_ids.update(card.evidence_span_ids)
            cluster_spans = [
                span_by_id[sid] for sid in cluster_span_ids if sid in span_by_id
            ]

            claims = await self._generate_theme_claims(
                cluster_name, cluster_id, cluster_cards, cluster_spans, language
            )
            all_claims.extend(claims)

        # Persist
        if all_claims:
            await self.claim_repo.create_many(all_claims)

        logger.info(f"Generated {len(all_claims)} claims across {len(clusters)} themes")
        return all_claims

    async def _generate_theme_claims(
        self,
        theme_name: str,
        theme_id: str,
        study_cards: List[StudyCard],
        evidence_spans: List[EvidenceSpan],
        language: str = "en",
    ) -> List[Claim]:
        """Generate claims for a single theme."""
        # Serialize study cards (compact)
        cards_json = json.dumps(
            [
                {
                    "paper_id": c.paper_id,
                    "problem": c.problem,
                    "method": c.method,
                    "datasets": c.datasets,
                    "results": c.results,
                    "limitations": c.limitations,
                    "evidence_span_ids": c.evidence_span_ids,
                }
                for c in study_cards
            ],
            indent=1,
        )

        # Serialize evidence spans (compact)
        spans_json = json.dumps(
            [
                {
                    "span_id": s.span_id,
                    "paper_id": s.paper_id,
                    "field": s.field,
                    "snippet": s.snippet[:200],
                }
                for s in evidence_spans
            ],
            indent=1,
        )

        prompt = PromptManager.get_prompt(
            "CLAIM_GENERATION",
            theme_name=theme_name,
            study_cards_json=cards_json,
            evidence_spans_json=spans_json,
            language=language,
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            results = self._parse_json_response(response_text)

            if not isinstance(results, list):
                if isinstance(results, dict):
                    for key in ["claims", "results", "data"]:
                        if key in results and isinstance(results[key], list):
                            results = results[key]
                            break
                    else:
                        results = []
                else:
                    results = []

            # Valid span IDs for validation
            valid_span_ids = {s.span_id for s in evidence_spans}

            claims = []
            for item in results:
                if not isinstance(item, dict):
                    continue

                claim_text = item.get("claim_text", "")
                if not claim_text:
                    continue

                # Validate evidence span IDs
                raw_ids = item.get("evidence_span_ids", [])
                validated_ids = [sid for sid in raw_ids if sid in valid_span_ids]

                # Skip claims with no valid evidence
                if not validated_ids:
                    logger.warning(
                        f"Claim has no valid evidence spans, skipping: {claim_text[:80]}"
                    )
                    continue

                claim = Claim(
                    claim_text=claim_text,
                    evidence_span_ids=validated_ids,
                    theme_id=theme_id,
                    salience_score=self._safe_float(
                        item.get("salience_score", 0.5)
                    ),
                    uncertainty_flag=bool(item.get("uncertainty_flag", False)),
                )
                claims.append(claim)

            logger.info(f"Generated {len(claims)} claims for theme '{theme_name}'")
            return claims

        except Exception as e:
            logger.error(f"Claim generation failed for theme '{theme_name}': {e}")
            return []

    def _parse_json_response(self, response_text: str) -> Any:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\[[\s\S]*\]", response_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return []

    @staticmethod
    def _safe_float(val) -> float:
        try:
            return min(1.0, max(0.0, float(val)))
        except (ValueError, TypeError):
            return 0.5
