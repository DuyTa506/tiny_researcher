"""
Evidence Extractor Service

Schema-driven extraction of StudyCards and EvidenceSpans from papers.
Core component of the citation-first workflow: every claim in the final
report must trace back to evidence extracted here.
"""

import json
import hashlib
import logging
import re
from datetime import datetime
from typing import List, Tuple, Optional, Any

from src.core.models import (
    Paper,
    PaperStatus,
    EvidenceSpan,
    StudyCard,
    Locator,
)
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.research.analysis.pdf_loader import PDFLoaderService
from src.storage.repositories import EvidenceSpanRepository, StudyCardRepository

logger = logging.getLogger(__name__)


class EvidenceExtractorService:
    """
    Extracts structured study cards with traceable evidence spans from papers.

    For each paper (full text or abstract-only fallback), produces:
    - A StudyCard with structured fields (problem, method, datasets, etc.)
    - A list of EvidenceSpans with verbatim snippets and locators

    Every populated field in the StudyCard must be backed by at least one
    EvidenceSpan for auditability.
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        pdf_loader: PDFLoaderService = None,
        evidence_repo: EvidenceSpanRepository = None,
        study_card_repo: StudyCardRepository = None,
    ):
        self.llm = llm_client
        self.pdf_loader = pdf_loader
        self.evidence_repo = evidence_repo or EvidenceSpanRepository()
        self.study_card_repo = study_card_repo or StudyCardRepository()

    async def extract_study_card(
        self, paper: Paper, language: str = "en"
    ) -> Tuple[Optional[StudyCard], List[EvidenceSpan]]:
        """
        Extract a structured study card + evidence spans from a single paper.

        Uses full_text if available, otherwise falls back to abstract.
        """
        # Determine content source
        if paper.full_text:
            content = paper.full_text[:8000]  # Limit for token budget
            source_type = "full_text"
        elif paper.abstract:
            content = paper.abstract
            source_type = "abstract"
        else:
            logger.warning(f"No content for paper {paper.title[:50]}")
            return None, []

        prompt = PromptManager.get_prompt(
            "EVIDENCE_EXTRACTION",
            title=paper.title,
            content=content,
            language=language,
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            raw = self._parse_json_response(response_text)

            if not isinstance(raw, dict):
                logger.warning(f"Unexpected extraction format for {paper.title[:50]}")
                return None, []

            paper_id = paper.id or paper.arxiv_id or paper.title
            source_url = paper.url or paper.pdf_url or ""

            spans: List[EvidenceSpan] = []
            span_ids: List[str] = []

            # Extract each field
            card_problem = self._extract_field_value(raw, "problem")
            card_method = self._extract_field_value(raw, "method")
            card_datasets = []
            card_metrics = []
            card_results = []
            card_limitations = []

            # Problem span
            problem_span = self._build_span(
                raw.get("problem"), "problem", paper, paper_id, source_url
            )
            if problem_span:
                spans.append(problem_span)
                span_ids.append(problem_span.span_id)

            # Method span
            method_span = self._build_span(
                raw.get("method"), "method", paper, paper_id, source_url
            )
            if method_span:
                spans.append(method_span)
                span_ids.append(method_span.span_id)

            # Datasets
            for item in self._ensure_list(raw.get("datasets", [])):
                name = item.get("name", "") if isinstance(item, dict) else str(item)
                if name:
                    card_datasets.append(name)
                span = self._build_span(item, "dataset", paper, paper_id, source_url)
                if span:
                    spans.append(span)
                    span_ids.append(span.span_id)

            # Metrics
            for item in self._ensure_list(raw.get("metrics", [])):
                name = item.get("name", "") if isinstance(item, dict) else str(item)
                if name:
                    card_metrics.append(name)
                span = self._build_span(item, "metric", paper, paper_id, source_url)
                if span:
                    spans.append(span)
                    span_ids.append(span.span_id)

            # Results
            for item in self._ensure_list(raw.get("results", [])):
                text = item.get("text", "") if isinstance(item, dict) else str(item)
                if text:
                    card_results.append(text)
                span = self._build_span(item, "result", paper, paper_id, source_url)
                if span:
                    spans.append(span)
                    span_ids.append(span.span_id)

            # Limitations
            for item in self._ensure_list(raw.get("limitations", [])):
                text = item.get("text", "") if isinstance(item, dict) else str(item)
                if text:
                    card_limitations.append(text)
                span = self._build_span(item, "limitation", paper, paper_id, source_url)
                if span:
                    spans.append(span)
                    span_ids.append(span.span_id)

            card = StudyCard(
                paper_id=paper_id,
                problem=card_problem,
                method=card_method,
                datasets=card_datasets,
                metrics=card_metrics,
                results=card_results,
                limitations=card_limitations,
                evidence_span_ids=span_ids,
                extraction_metadata={
                    "source_type": source_type,
                    "timestamp": datetime.now().isoformat(),
                    "content_length": len(content),
                },
            )

            paper.status = PaperStatus.EXTRACTED
            return card, spans

        except Exception as e:
            logger.error(f"Evidence extraction failed for {paper.title[:50]}: {e}")
            return None, []

    async def extract_batch(
        self, papers: List[Paper], language: str = "en"
    ) -> Tuple[List[StudyCard], List[EvidenceSpan]]:
        """Extract study cards for multiple papers and persist."""
        all_cards: List[StudyCard] = []
        all_spans: List[EvidenceSpan] = []

        for i, paper in enumerate(papers):
            card, spans = await self.extract_study_card(paper, language=language)
            if card:
                all_cards.append(card)
                all_spans.extend(spans)

            if (i + 1) % 5 == 0:
                logger.info(f"Extracted {i + 1}/{len(papers)} study cards")

        # Persist
        if all_spans:
            await self.evidence_repo.create_many(all_spans)
        if all_cards:
            await self.study_card_repo.create_many(all_cards)

        logger.info(
            f"Extraction complete: {len(all_cards)} study cards, "
            f"{len(all_spans)} evidence spans"
        )
        return all_cards, all_spans

    def _build_span(
        self,
        field_data: Any,
        field_type: str,
        paper: Paper,
        paper_id: str,
        source_url: str,
    ) -> Optional[EvidenceSpan]:
        """Build an EvidenceSpan from extracted field data.

        Uses deterministic span_id: {paper_id}#{sha1(snippet)[:8]}
        This makes span_ids reproducible and prevents hallucination.
        """
        if not isinstance(field_data, dict):
            return None

        snippet = field_data.get("snippet", "")
        if not snippet:
            return None

        # Truncate snippet to 300 chars
        snippet = snippet[:300]

        confidence = self._safe_float(field_data.get("confidence", 0.7))

        # Deterministic span_id from paper_id + snippet hash
        snippet_hash = hashlib.sha1(snippet.encode("utf-8")).hexdigest()[:8]
        span_id = f"{paper_id}#{snippet_hash}"

        # Resolve locator using page map
        locator = Locator()
        if self.pdf_loader and paper.full_text:
            locator = self.pdf_loader.resolve_locator(paper, snippet)

        return EvidenceSpan(
            span_id=span_id,
            paper_id=paper_id,
            field=field_type,
            snippet=snippet,
            locator=locator,
            confidence=confidence,
            source_url=source_url,
        )

    def _extract_field_value(self, raw: dict, field: str) -> Optional[str]:
        """Extract the text value from a field dict."""
        field_data = raw.get(field)
        if isinstance(field_data, dict):
            return field_data.get("text")
        if isinstance(field_data, str):
            return field_data
        return None

    @staticmethod
    def _ensure_list(val) -> list:
        if isinstance(val, list):
            return val
        if val:
            return [val]
        return []

    @staticmethod
    def _safe_float(val) -> float:
        try:
            return min(1.0, max(0.0, float(val)))
        except (ValueError, TypeError):
            return 0.7

    def _parse_json_response(self, response_text: str) -> Any:
        """Parse JSON from LLM response."""
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

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse extraction JSON: {response_text[:200]}")
        return {}
