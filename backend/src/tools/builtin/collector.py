"""
Collector Tools

Tools for collecting papers from direct URLs.
"""

from typing import List
from src.tools.registry import register_tool


@register_tool(
    name="collect_url",
    description="Collect paper metadata from a direct URL. Supports ArXiv URLs, RSS feeds, and PDF links.",
    tags=["collect", "ingestion", "url"],
)
async def collect_url(url: str) -> List[dict]:
    """
    Collect paper(s) from a URL.

    Args:
        url: URL to collect from (ArXiv, RSS, PDF)

    Returns:
        List of paper dicts extracted from URL
    """
    from src.research.ingestion.collector import IngestionFactory

    collector = IngestionFactory.get_collector(url)
    results = await collector.collect(url)
    return results


@register_tool(
    name="collect_urls",
    description="Collect papers from multiple URLs. Automatically routes each URL to appropriate collector.",
    tags=["collect", "ingestion", "url"],
)
async def collect_urls(urls: List[str]) -> List[dict]:
    """
    Collect papers from multiple URLs.

    Args:
        urls: List of URLs to collect from

    Returns:
        Combined list of paper dicts from all URLs
    """
    from src.research.ingestion.collector import IngestionFactory

    all_results = []
    for url in urls:
        try:
            collector = IngestionFactory.get_collector(url)
            results = await collector.collect(url)
            all_results.extend(results)
        except Exception as e:
            # Log but continue with other URLs
            import logging

            logging.warning(f"Failed to collect from {url}: {e}")

    return all_results
