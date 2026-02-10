"""
Gap Miner Service

Identifies research gaps from aggregated limitations, contradictory results,
and taxonomy holes. Generates future research directions grounded in evidence.
"""

import json
import logging
import re
from typing import List, Any
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from src.core.models import StudyCard, EvidenceSpan, TaxonomyMatrix
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.research.analysis.taxonomy import TaxonomyBuilder

logger = logging.getLogger(__name__)


class FutureDirection(BaseModel):
    """A research direction grounded in evidence."""

    direction_type: str  # open_problem | research_opportunity | next_experiment
    title: str
    description: str
    evidence_span_ids: List[str] = Field(default_factory=list)
    gap_source: str  # limitation_cluster | contradictory_results | taxonomy_hole


class GapMinerService:
    """
    Mines research gaps from study cards and taxonomy to generate
    evidence-grounded future research directions.

    Gap sources:
    1. Frequently mentioned limitations across papers
    2. Contradictory results (same dataset/metric, different outcomes)
    3. Taxonomy holes (underexplored theme x dataset x metric combos)
    """

    def __init__(self, llm_client: LLMClientInterface):
        self.llm = llm_client
        self.taxonomy_builder = TaxonomyBuilder()

    async def mine_gaps(
        self,
        study_cards: List[StudyCard],
        evidence_spans: List[EvidenceSpan],
        taxonomy: TaxonomyMatrix,
        topic: str,
        language: str = "en",
    ) -> List[FutureDirection]:
        """
        Identify gaps and generate future directions.

        Each direction must cite at least one limitation evidence span.
        """
        # 1. Aggregate limitations with their evidence
        limitations_data = self._aggregate_limitations(study_cards, evidence_spans)

        # 2. Find contradictory results
        contradictions = self._find_contradictions(study_cards)

        # 3. Find taxonomy holes
        holes = self.taxonomy_builder.find_taxonomy_holes(taxonomy)

        # 4. Generate directions via LLM
        directions = await self._generate_directions(
            topic, limitations_data, contradictions, holes, taxonomy, language
        )

        logger.info(f"Mined {len(directions)} future research directions")
        return directions

    def _aggregate_limitations(
        self,
        study_cards: List[StudyCard],
        evidence_spans: List[EvidenceSpan],
    ) -> List[dict]:
        """Aggregate limitations across all study cards with their evidence."""
        span_by_id = {s.span_id: s for s in evidence_spans}
        limitations = []

        for card in study_cards:
            limitation_spans = [
                span_by_id[sid]
                for sid in card.evidence_span_ids
                if sid in span_by_id and span_by_id[sid].field == "limitation"
            ]
            for i, lim_text in enumerate(card.limitations):
                span = limitation_spans[i] if i < len(limitation_spans) else None
                limitations.append(
                    {
                        "paper_id": card.paper_id,
                        "text": lim_text,
                        "span_id": span.span_id if span else None,
                        "snippet": span.snippet if span else "",
                    }
                )

        return limitations

    def _find_contradictions(self, study_cards: List[StudyCard]) -> List[dict]:
        """Find papers with contradictory results on the same dataset/metric."""
        # Group results by (dataset, metric)
        result_groups = {}
        for card in study_cards:
            for dataset in card.datasets:
                for metric in card.metrics:
                    key = (dataset, metric)
                    if key not in result_groups:
                        result_groups[key] = []
                    result_groups[key].append(
                        {
                            "paper_id": card.paper_id,
                            "results": card.results,
                        }
                    )

        contradictions = []
        for (dataset, metric), papers in result_groups.items():
            if len(papers) >= 2:
                contradictions.append(
                    {
                        "dataset": dataset,
                        "metric": metric,
                        "papers": papers,
                    }
                )

        return contradictions

    async def _generate_directions(
        self,
        topic: str,
        limitations: List[dict],
        contradictions: List[dict],
        taxonomy_holes: List[str],
        taxonomy: TaxonomyMatrix,
        language: str = "en",
    ) -> List[FutureDirection]:
        """Use LLM to generate future directions from gaps."""
        # Serialize for prompt
        limitations_json = json.dumps(
            [
                {"text": l["text"], "span_id": l["span_id"], "paper_id": l["paper_id"]}
                for l in limitations
                if l["span_id"]
            ],
            indent=1,
        )

        contradictions_json = (
            json.dumps(
                [
                    {
                        "dataset": c["dataset"],
                        "metric": c["metric"],
                        "paper_count": len(c["papers"]),
                    }
                    for c in contradictions
                ],
                indent=1,
            )
            if contradictions
            else "None found"
        )

        holes_str = ", ".join(taxonomy_holes[:20]) if taxonomy_holes else "None found"

        prompt = PromptManager.get_prompt(
            "GAP_MINING",
            topic=topic,
            limitations_json=limitations_json,
            themes=", ".join(taxonomy.themes),
            datasets=", ".join(taxonomy.datasets[:15]),
            metrics=", ".join(taxonomy.metrics[:15]),
            method_families=", ".join(taxonomy.method_families[:15]),
            taxonomy_holes=holes_str,
            contradictions=contradictions_json,
            language=language,
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            results = self._parse_json_response(response_text)

            if not isinstance(results, list):
                if isinstance(results, dict):
                    for key in ["directions", "results", "future_directions", "data"]:
                        if key in results and isinstance(results[key], list):
                            results = results[key]
                            break
                    else:
                        results = []
                else:
                    results = []

            # Valid limitation span IDs
            valid_span_ids = {l["span_id"] for l in limitations if l["span_id"]}

            directions = []
            for item in results:
                if not isinstance(item, dict):
                    continue

                # Validate span IDs
                raw_ids = item.get("evidence_span_ids", [])
                validated_ids = [sid for sid in raw_ids if sid in valid_span_ids]

                direction = FutureDirection(
                    direction_type=item.get("direction_type", "research_opportunity"),
                    title=item.get("title", "Untitled"),
                    description=item.get("description", ""),
                    evidence_span_ids=validated_ids,
                    gap_source=item.get("gap_source", "limitation_cluster"),
                )
                directions.append(direction)

            return directions

        except Exception as e:
            logger.error(f"Gap mining failed: {e}")
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

        return []
