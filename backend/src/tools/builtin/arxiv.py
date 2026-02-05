"""
ArXiv Tools

Tools for searching and collecting papers from ArXiv.
"""

from typing import List, Optional
from src.tools.registry import register_tool


@register_tool(
    name="arxiv_search",
    description="Search academic papers on ArXiv by keyword or query. Returns paper metadata including title, abstract, authors, and ArXiv ID.",
    tags=["search", "ingestion", "arxiv"]
)
async def arxiv_search(
    query: str,
    max_results: int = 20,
    categories: List[str] = None
) -> List[dict]:
    """
    Search ArXiv papers by keyword.
    
    Args:
        query: Search query (keywords, title, author)
        max_results: Maximum papers to return (default 20)
        categories: Filter by ArXiv categories (e.g., ["cs.AI", "cs.CL"])
        
    Returns:
        List of paper dicts with title, abstract, arxiv_id, etc.
    """
    from src.research.ingestion.searcher import ArxivSearcher
    
    searcher = ArxivSearcher()
    results = await searcher.search(
        query=query,
        categories=categories,
        max_results=max_results
    )
    return results


@register_tool(
    name="arxiv_search_keywords",
    description="Search ArXiv using multiple keywords combined with OR. Good for broad topic exploration. Accepts either 'query' (string) or 'keywords' (list).",
    tags=["search", "ingestion", "arxiv"]
)
async def arxiv_search_keywords(
    keywords: List[str] = None,
    query: str = None,
    max_results: int = 30,
    categories: List[str] = None
) -> List[dict]:
    """
    Search ArXiv with multiple keywords.
    
    Args:
        keywords: List of keywords to search (OR combined)
        query: Alternative - single query string (will be split by OR)
        max_results: Maximum papers to return
        categories: Filter by categories
        
    Returns:
        List of paper dicts
    """
    from src.research.ingestion.searcher import ArxivSearcher
    
    # Handle query parameter (LLM often uses this)
    if query and not keywords:
        if " OR " in query:
            keywords = [k.strip() for k in query.split(" OR ")]
        else:
            keywords = [query]
    
    # Handle case where keywords is a string
    if isinstance(keywords, str):
        if " OR " in keywords:
            keywords = [k.strip() for k in keywords.split(" OR ")]
        else:
            keywords = [keywords]
    
    # Fallback
    if not keywords:
        keywords = ["machine learning"]
    
    searcher = ArxivSearcher()
    results = await searcher.search_by_keywords(
        keywords=keywords,
        categories=categories,
        max_results=max_results
    )
    return results
