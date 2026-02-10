"""
HuggingFace Tools

Tools for discovering trending papers on HuggingFace.
"""

from typing import List
from src.tools.registry import register_tool


@register_tool(
    name="hf_trending",
    description="Get trending ML/AI papers from HuggingFace Papers. Good for discovering recent popular research.",
    tags=["search", "ingestion", "huggingface"],
)
async def hf_trending(query: str = "", max_results: int = 10) -> List[dict]:
    """
    Get trending papers from HuggingFace.

    Args:
        query: Optional search query filter
        max_results: Maximum papers to return

    Returns:
        List of trending paper dicts
    """
    from src.research.ingestion.searcher import HuggingFaceSearcher

    searcher = HuggingFaceSearcher()
    try:
        results = await searcher.search(query=query, max_results=max_results)
        return results
    except Exception as e:
        # HuggingFace scraping can fail, return empty
        import logging

        logging.getLogger(__name__).warning(f"HuggingFace search failed: {e}")
        return []
