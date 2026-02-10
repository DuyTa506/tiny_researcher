"""
Grounded Writer Service

Generates citation-grounded Markdown reports from Claims and evidence.
Every statement in the report must trace back to a Claim, which traces
back to EvidenceSpans in source papers.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from src.core.models import Claim, EvidenceSpan, Paper, TaxonomyMatrix
from src.core.prompts import PromptManager
from src.adapters.llm import LLMClientInterface
from src.research.synthesis.gap_miner import FutureDirection

logger = logging.getLogger(__name__)


class GroundedWriterService:
    """
    Generates research reports where every claim is backed by evidence.

    Report structure:
    1. Scope & search strategy
    2. Theme map (clusters overview)
    3. Per-theme synthesis (from claims with inline citations)
    4. Comparative table (from taxonomy matrix)
    5. Aggregated limitations
    6. Future research directions (gap-driven)
    """

    def __init__(self, llm_client: LLMClientInterface):
        self.llm = llm_client

    async def generate_report(
        self,
        claims: List[Claim],
        clusters: List[dict],
        evidence_spans: List[EvidenceSpan],
        papers: List[Paper],
        topic: str,
        taxonomy: TaxonomyMatrix = None,
        future_directions: List[FutureDirection] = None,
        language: str = "en",
        search_strategy: str = "",
    ) -> str:
        """Generate a full citation-grounded Markdown report."""
        paper_map = {(p.id or p.arxiv_id or p.title): p for p in papers}
        span_map = {s.span_id: s for s in evidence_spans}
        claims_by_theme = {}
        for claim in claims:
            tid = claim.theme_id or "uncategorized"
            if tid not in claims_by_theme:
                claims_by_theme[tid] = []
            claims_by_theme[tid].append(claim)

        sections = []

        # Header
        sections.append(f"# Research Report: {topic}")
        sections.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        sections.append(f"*Papers analyzed: {len(papers)}*\n")

        # 1. Scope & search strategy
        sections.append("## 1. Scope & Search Strategy")
        if search_strategy:
            sections.append(search_strategy)
        else:
            sections.append(
                f"This report synthesizes findings from {len(papers)} papers "
                f"on the topic of **{topic}**. "
                f"Papers were collected, screened, and analyzed through an "
                f"automated citation-first pipeline."
            )
        sections.append("")

        # 2. Theme map
        sections.append("## 2. Theme Map")
        if clusters:
            for cluster in clusters:
                name = cluster.get("name", "Unnamed")
                desc = cluster.get("description", "")
                n_papers = len(cluster.get("paper_ids", []))
                sections.append(f"- **{name}** ({n_papers} papers): {desc}")
        else:
            sections.append("No thematic clusters were identified.")
        sections.append("")

        # 3. Per-theme synthesis
        sections.append("## 3. Thematic Synthesis")
        for cluster in clusters:
            theme_id = cluster.get("id") or cluster.get("name", "unknown")
            theme_name = cluster.get("name", "Unnamed Theme")
            theme_claims = claims_by_theme.get(theme_id, [])

            sections.append(f"### {theme_name}")

            if theme_claims:
                # Use LLM for coherent synthesis
                synthesis = await self._synthesize_theme(
                    theme_name, theme_claims, span_map, paper_map, language
                )
                sections.append(synthesis)

                # Add evidence footnotes
                sections.append("\n**Key evidence:**")
                for claim in sorted(theme_claims, key=lambda c: c.salience_score, reverse=True)[:5]:
                    uncertainty = " [uncertain]" if claim.uncertainty_flag else ""
                    sections.append(f"- {claim.claim_text}{uncertainty}")
                    for sid in claim.evidence_span_ids[:2]:
                        span = span_map.get(sid)
                        if span:
                            paper = paper_map.get(span.paper_id)
                            paper_ref = paper.title[:60] if paper else span.paper_id
                            sections.append(f'  - *"{span.snippet[:150]}..."* — [{paper_ref}]')
            else:
                sections.append("*No grounded claims available for this theme.*")
            sections.append("")

        # 4. Comparative table
        if taxonomy and taxonomy.cells:
            sections.append("## 4. Comparative Table")
            table = self._render_comparative_table(taxonomy, paper_map)
            sections.append(table)
            sections.append("")

        # 5. Aggregated limitations
        sections.append(f"## {5 if taxonomy and taxonomy.cells else 4}. Limitations")
        limitation_spans = [s for s in evidence_spans if s.field == "limitation"]
        if limitation_spans:
            for span in limitation_spans[:15]:
                paper = paper_map.get(span.paper_id)
                paper_ref = paper.title[:50] if paper else span.paper_id
                sections.append(f'- *"{span.snippet[:200]}"* — [{paper_ref}]')
        else:
            sections.append("*No explicit limitations extracted from the corpus.*")
        sections.append("")

        # 6. Future research directions
        section_num = (6 if taxonomy and taxonomy.cells else 5)
        sections.append(f"## {section_num}. Future Research Directions")
        if future_directions:
            for i, fd in enumerate(future_directions, 1):
                type_label = fd.direction_type.replace("_", " ").title()
                sections.append(f"### {i}. {fd.title} ({type_label})")
                sections.append(fd.description)
                if fd.evidence_span_ids:
                    for sid in fd.evidence_span_ids[:2]:
                        span = span_map.get(sid)
                        if span:
                            sections.append(f'  - Based on: *"{span.snippet[:150]}..."*')
                sections.append(f"  - Source: {fd.gap_source.replace('_', ' ')}")
                sections.append("")
        else:
            sections.append("*No future directions generated.*")

        # References
        sections.append("## References")
        for i, paper in enumerate(papers, 1):
            authors = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
            if len(paper.authors) > 3:
                authors += " et al."
            date_str = paper.published_date.strftime("%Y") if paper.published_date else "n.d."
            url = paper.url or paper.pdf_url or ""
            sections.append(
                f"{i}. {authors} ({date_str}). *{paper.title}*. [{url}]({url})"
            )

        return "\n\n".join(sections)

    async def _synthesize_theme(
        self,
        theme_name: str,
        claims: List[Claim],
        span_map: Dict[str, EvidenceSpan],
        paper_map: Dict[str, Paper],
        language: str,
    ) -> str:
        """Use LLM to write coherent synthesis from claims."""
        claims_json = []
        for c in claims:
            papers_cited = []
            for sid in c.evidence_span_ids:
                span = span_map.get(sid)
                if span:
                    paper = paper_map.get(span.paper_id)
                    if paper:
                        papers_cited.append(paper.title[:50])
            claims_json.append({
                "claim_id": c.claim_id[:8],
                "text": c.claim_text,
                "papers": papers_cited,
                "uncertain": c.uncertainty_flag,
            })

        papers_json = []
        seen = set()
        for c in claims:
            for sid in c.evidence_span_ids:
                span = span_map.get(sid)
                if span and span.paper_id not in seen:
                    seen.add(span.paper_id)
                    paper = paper_map.get(span.paper_id)
                    if paper:
                        authors = paper.authors[0] if paper.authors else "Unknown"
                        year = paper.published_date.strftime("%Y") if paper.published_date else "n.d."
                        papers_json.append({
                            "id": span.paper_id,
                            "short_ref": f"{authors} ({year})",
                            "title": paper.title[:60],
                        })

        import json
        prompt = PromptManager.get_prompt(
            "GROUNDED_SYNTHESIS",
            theme_name=theme_name,
            claims_json=json.dumps(claims_json, indent=1),
            papers_json=json.dumps(papers_json, indent=1),
            language=language,
        )

        try:
            synthesis = await self.llm.generate(prompt)
            return synthesis.strip()
        except Exception as e:
            logger.error(f"Synthesis generation failed for '{theme_name}': {e}")
            # Fallback: concatenate claims
            lines = []
            for c in claims:
                lines.append(f"- {c.claim_text}")
            return "\n".join(lines)

    def _render_comparative_table(
        self,
        taxonomy: TaxonomyMatrix,
        paper_map: Dict[str, Paper],
    ) -> str:
        """Render taxonomy matrix as Markdown table."""
        if not taxonomy.datasets or not taxonomy.metrics:
            return "*No comparative data available.*"

        # Limit dimensions for readability
        datasets = taxonomy.datasets[:8]
        metrics = taxonomy.metrics[:5]

        lines = []
        header = "| Dataset | " + " | ".join(metrics) + " |"
        separator = "|" + "---|" * (len(metrics) + 1)
        lines.append(header)
        lines.append(separator)

        for dataset in datasets:
            row = f"| {dataset} |"
            for metric in metrics:
                # Find papers covering this cell across all themes
                paper_count = 0
                for theme in taxonomy.themes:
                    key = f"({theme}, {dataset}, {metric})"
                    paper_count += len(taxonomy.cells.get(key, []))
                row += f" {paper_count if paper_count else '-'} |"
            lines.append(row)

        return "\n".join(lines)
