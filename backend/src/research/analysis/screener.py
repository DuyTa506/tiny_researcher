"""
Screener Service

Title/abstract screening for systematic-like review.
Implements include/exclude decisions with reason codes and rationale.
Replaces AnalyzerService for the citation-first workflow.
"""

import json
import logging
import re
from typing import List, Tuple

from src.core.models import Paper, PaperStatus, ScreeningRecord
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.storage.repositories import ScreeningRecordRepository

logger = logging.getLogger(__name__)


class ScreenerService:
    """
    Systematic screening of papers by title/abstract.

    Produces ScreeningRecord for each paper with include/exclude decision,
    reason code, and short rationale. Designed for broad recall with
    controlled noise.
    """

    BATCH_SIZE = 15

    def __init__(
        self,
        llm_client: LLMClientInterface,
        screening_repo: ScreeningRecordRepository = None,
    ):
        self.llm = llm_client
        self.screening_repo = screening_repo or ScreeningRecordRepository()

    async def screen_papers(
        self, papers: List[Paper], topic: str
    ) -> Tuple[List[Paper], List[ScreeningRecord]]:
        """
        Screen papers by title/abstract.

        Returns:
            Tuple of (included_papers, all_screening_records)
        """
        logger.info(f"Screening {len(papers)} papers for topic: {topic[:50]}...")

        all_records: List[ScreeningRecord] = []

        for i in range(0, len(papers), self.BATCH_SIZE):
            batch = papers[i : i + self.BATCH_SIZE]
            records = await self._screen_batch(batch, topic)
            all_records.extend(records)
            logger.info(
                f"Screened batch {i // self.BATCH_SIZE + 1}, "
                f"papers {i + 1}-{min(i + self.BATCH_SIZE, len(papers))}"
            )

        # Apply screening decisions to papers
        record_map = {r.paper_id: r for r in all_records}
        included = []
        for paper in papers:
            pid = paper.id or paper.arxiv_id or paper.title
            record = record_map.get(pid)
            if record and record.include:
                paper.status = PaperStatus.SCREENED
                if record.scored_relevance is not None:
                    paper.relevance_score = record.scored_relevance
                included.append(paper)

        # Persist screening records
        if all_records:
            await self.screening_repo.create_many(all_records)

        logger.info(
            f"Screening complete: {len(included)} included, "
            f"{len(papers) - len(included)} excluded"
        )
        return included, all_records

    async def _screen_batch(
        self, papers: List[Paper], topic: str
    ) -> List[ScreeningRecord]:
        """Screen a batch of papers with a single LLM call."""
        papers_list = "\n\n".join(
            [
                f"Paper {i} (paper_id: {p.id or p.arxiv_id or p.title}):\n"
                f"Title: {p.title}\n"
                f"Abstract: {p.abstract[:600] if p.abstract else 'No abstract'}"
                for i, p in enumerate(papers)
            ]
        )

        prompt = PromptManager.get_prompt(
            "SCREENING_BATCH", topic=topic, papers_list=papers_list
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            results = self._parse_json_response(response_text)

            if not isinstance(results, list):
                if isinstance(results, dict):
                    for key in ["results", "papers", "screenings", "data"]:
                        if key in results and isinstance(results[key], list):
                            results = results[key]
                            break
                    else:
                        results = [results] if results else []
                else:
                    results = []

            records = []
            for result in results:
                if not isinstance(result, dict):
                    continue
                idx = result.get("paper_index", 0)
                if 0 <= idx < len(papers):
                    paper = papers[idx]
                    pid = paper.id or paper.arxiv_id or paper.title

                    # Handle 3-tier response (with backward compat for include/exclude)
                    tier = result.get("tier", "")
                    if tier in ("core", "background", "exclude"):
                        include = tier != "exclude"
                    else:
                        # Backward compat: derive tier from include boolean
                        include = bool(result.get("include", False))
                        tier = "core" if include else "exclude"

                    record = ScreeningRecord(
                        paper_id=pid,
                        tier=tier,
                        include=include,
                        reason_code=result.get("reason_code", "unknown"),
                        rationale_short=result.get("rationale_short", "")[:500],
                        scored_relevance=self._safe_float(
                            result.get("scored_relevance")
                        ),
                    )
                    records.append(record)

            # Fill missing papers with conservative include
            screened_indices = {r.get("paper_index", -1) for r in results if isinstance(r, dict)}
            for i, paper in enumerate(papers):
                if i not in screened_indices:
                    pid = paper.id or paper.arxiv_id or paper.title
                    records.append(
                        ScreeningRecord(
                            paper_id=pid,
                            tier="background",
                            include=True,
                            reason_code="unscreened",
                            rationale_short="Not evaluated in batch, included as background by default",
                            scored_relevance=5.0,
                        )
                    )

            return records

        except Exception as e:
            logger.error(f"Batch screening failed: {e}")
            # Fallback: include all papers as background
            return [
                ScreeningRecord(
                    paper_id=p.id or p.arxiv_id or p.title,
                    tier="background",
                    include=True,
                    reason_code="error_fallback",
                    rationale_short=f"Screening failed: {str(e)[:100]}",
                    scored_relevance=5.0,
                )
                for p in papers
            ]

    def _parse_json_response(self, response_text: str):
        """Parse JSON from LLM response."""
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

        logger.warning(f"Could not parse screening JSON: {response_text[:200]}")
        return []

    @staticmethod
    def _safe_float(val) -> float:
        if val is None:
            return 5.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 5.0
