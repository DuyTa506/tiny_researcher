"""
Taxonomy Builder

Builds a multi-dimensional TaxonomyMatrix from study cards and clusters.
Used for gap detection and comparative tables in the final report.
"""

import logging
from typing import List

from src.core.models import StudyCard, TaxonomyMatrix

logger = logging.getLogger(__name__)


class TaxonomyBuilder:
    """
    Builds a taxonomy matrix showing coverage across themes,
    datasets, metrics, and method families.

    The matrix is used for:
    - Comparative tables in the report
    - Gap detection (empty cells = unexplored combinations)
    """

    def build_taxonomy(
        self,
        study_cards: List[StudyCard],
        clusters: List[dict],
    ) -> TaxonomyMatrix:
        """
        Build multi-dimensional taxonomy from study cards.

        Args:
            study_cards: Extracted study cards
            clusters: List of cluster dicts with 'id', 'name', 'paper_ids'
        """
        card_by_paper = {c.paper_id: c for c in study_cards}

        # Collect dimensions
        themes = []
        all_datasets = set()
        all_metrics = set()
        all_methods = set()

        paper_to_theme = {}
        for cluster in clusters:
            theme_name = cluster.get("name", "Unknown")
            themes.append(theme_name)
            for pid in cluster.get("paper_ids", []):
                paper_to_theme[pid] = theme_name

        for card in study_cards:
            for d in card.datasets:
                all_datasets.add(d)
            for m in card.metrics:
                all_metrics.add(m)
            if card.method:
                # Extract method family (first few words)
                method_family = " ".join(card.method.split()[:4])
                all_methods.add(method_family)

        datasets = sorted(all_datasets)
        metrics = sorted(all_metrics)
        method_families = sorted(all_methods)

        # Build cells: (theme, dataset, metric) -> [paper_ids]
        cells = {}
        for card in study_cards:
            theme = paper_to_theme.get(card.paper_id, "Unclustered")
            for dataset in card.datasets:
                for metric in card.metrics:
                    key = f"({theme}, {dataset}, {metric})"
                    if key not in cells:
                        cells[key] = []
                    cells[key].append(card.paper_id)

        taxonomy = TaxonomyMatrix(
            themes=themes,
            datasets=datasets,
            metrics=metrics,
            method_families=method_families,
            cells=cells,
        )

        logger.info(
            f"Built taxonomy: {len(themes)} themes, {len(datasets)} datasets, "
            f"{len(metrics)} metrics, {len(cells)} cells"
        )
        return taxonomy

    def find_taxonomy_holes(self, taxonomy: TaxonomyMatrix) -> List[str]:
        """
        Find empty cells in the taxonomy (unexplored combinations).

        Returns list of "(theme, dataset, metric)" strings that have
        no papers covering them.
        """
        holes = []
        for theme in taxonomy.themes:
            for dataset in taxonomy.datasets:
                for metric in taxonomy.metrics:
                    key = f"({theme}, {dataset}, {metric})"
                    if key not in taxonomy.cells or not taxonomy.cells[key]:
                        holes.append(key)
        return holes
