"""
Ingestion Sub-module

Contains data collection services:
- ArxivSearcher: Search ArXiv via API
- HuggingFaceSearcher: Search trending papers on HuggingFace
- ArxivCollector: Collect from direct ArXiv URLs
- RSSCollector: Collect from RSS feeds
"""

from src.research.ingestion.searcher import ArxivSearcher, HuggingFaceSearcher
from src.research.ingestion.collector import (
    ArxivCollector,
    RSSCollector,
    IngestionFactory,
)

__all__ = [
    "ArxivSearcher",
    "HuggingFaceSearcher",
    "ArxivCollector",
    "RSSCollector",
    "IngestionFactory",
]
