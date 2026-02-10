"""
Unified Search Tool

Single entry point for academic paper search.
Runs ArXiv + OpenAlex in parallel, deduplicates, and optionally
refines queries via LLM when results are poor.
"""

import asyncio
from typing import List, Optional
import logging

from src.tools.registry import register_tool

logger = logging.getLogger(__name__)

# Quality thresholds for query refinement
_MIN_ACCEPTABLE_RESULTS = 3
_MAX_REFINE_ATTEMPTS = 2


@register_tool(
    name="search",
    description="Search academic papers across multiple sources (ArXiv + OpenAlex) in parallel. Returns paper metadata including title, abstract, authors, DOI, PDF URLs. Automatically refines queries if initial results are poor.",
    tags=["search", "ingestion"],
)
async def search(
    query: str,
    max_results: int = 20,
    categories: List[str] = None,
) -> List[dict]:
    """
    Unified academic paper search.

    Strategy:
    1. Run ArXiv + OpenAlex in parallel
    2. Merge and deduplicate results
    3. If results are poor, refine query via LLM and retry

    Args:
        query: Search query (keywords, topic, title)
        max_results: Maximum papers to return (default 20)
        categories: Optional ArXiv category filter (e.g. ["cs.AI", "cs.CL"])

    Returns:
        List of paper dicts with title, abstract, authors, etc.
    """
    all_results = await _parallel_search(query, max_results, categories)

    # If results are poor (too few OR irrelevant), try query refinement
    if _is_poor_quality(query, all_results):
        refined_results = await _refine_and_retry(
            original_query=query,
            current_results=all_results,
            max_results=max_results,
            categories=categories,
        )
        if refined_results is not None:
            all_results = refined_results

    logger.info(
        "search_complete",
        query=query,
        total=len(all_results),
        sources=_count_sources(all_results),
    )

    return all_results


async def _parallel_search(
    query: str,
    max_results: int,
    categories: List[str] = None,
) -> List[dict]:
    """Run ArXiv and OpenAlex searches in parallel, merge and dedup."""
    arxiv_task = asyncio.create_task(_try_arxiv(query, max_results, categories))
    openalex_task = asyncio.create_task(_try_openalex(query, max_results))

    arxiv_results, openalex_results = await asyncio.gather(
        arxiv_task, openalex_task, return_exceptions=True
    )

    # Handle exceptions from gather
    if isinstance(arxiv_results, Exception):
        logger.warning(f"arxiv_parallel_failed: {arxiv_results}")
        arxiv_results = []
    if isinstance(openalex_results, Exception):
        logger.warning(f"openalex_parallel_failed: {openalex_results}")
        openalex_results = []

    all_results = []
    if arxiv_results:
        all_results.extend(arxiv_results)
    if openalex_results:
        all_results.extend(openalex_results)

    # Deduplicate across sources
    if all_results:
        before = len(all_results)
        all_results = _quick_dedup(all_results)
        dupes = before - len(all_results)
        if dupes > 0:
            logger.info("search_dedup", removed=dupes, remaining=len(all_results))

    sources = _count_sources(all_results)
    logger.info(
        "parallel_search_done", query=query, total=len(all_results), sources=sources
    )

    return all_results


async def _refine_and_retry(
    original_query: str,
    current_results: List[dict],
    max_results: int,
    categories: List[str] = None,
) -> Optional[List[dict]]:
    """
    Use LLM to refine query and retry search when results are poor.

    Returns improved results or None if refinement didn't help.
    """
    from src.research.ingestion.query_refiner import QueryRefiner

    refiner = QueryRefiner()
    tried_queries = {original_query.lower().strip()}
    best_results = list(current_results)
    found_relevant = False

    for attempt in range(_MAX_REFINE_ATTEMPTS):
        logger.info(
            "query_refine_attempt",
            attempt=attempt + 1,
            original_query=original_query,
            current_count=len(best_results),
        )

        # Get refined queries from LLM or heuristic
        refined_queries = await refiner.refine(
            original_query=original_query,
            num_results=len(best_results),
            tried_queries=list(tried_queries),
        )

        if not refined_queries:
            logger.info("query_refine_no_suggestions")
            break

        # Try each refined query
        for rq in refined_queries:
            rq_normalized = rq.lower().strip()
            if rq_normalized in tried_queries:
                continue
            tried_queries.add(rq_normalized)

            logger.info("query_refine_trying", refined_query=rq)
            new_results = await _parallel_search(rq, max_results, categories)

            if not new_results:
                continue

            # Check if new results are actually relevant
            if not _is_poor_quality(rq, new_results):
                # Found relevant results - merge with existing
                best_results.extend(new_results)
                best_results = _quick_dedup(best_results)
                found_relevant = True
                logger.info(
                    "query_refine_improved",
                    refined_query=rq,
                    new_total=len(best_results),
                )
                break
            else:
                logger.info(
                    "query_refine_still_poor", refined_query=rq, count=len(new_results)
                )

        if found_relevant:
            break

    if len(best_results) > len(current_results):
        return best_results
    return None


def _is_poor_quality(query: str, results: List[dict]) -> bool:
    """
    Check if search results are poor quality.

    Poor quality means:
    - Too few results (< threshold)
    - Results are mostly irrelevant (titles don't match query keywords)
    """
    if len(results) < _MIN_ACCEPTABLE_RESULTS:
        return True

    # Check if any results are actually relevant to the query
    # Extract significant keywords from query (>= 3 chars, not stopwords)
    stopwords = {
        "and",
        "or",
        "the",
        "for",
        "with",
        "from",
        "about",
        "into",
        "that",
        "this",
        "are",
        "was",
        "were",
        "been",
        "have",
        "has",
    }
    query_keywords = {
        w.lower() for w in query.split() if len(w) >= 3 and w.lower() not in stopwords
    }

    if not query_keywords:
        return False

    # Count how many results have at least one query keyword in the title
    relevant_count = 0
    for r in results:
        title_lower = r.get("title", "").lower()
        if any(kw in title_lower for kw in query_keywords):
            relevant_count += 1

    relevance_ratio = relevant_count / len(results) if results else 0

    if relevance_ratio < 0.2:  # Less than 20% of results are relevant
        logger.info(
            "search_quality_poor",
            query=query,
            total=len(results),
            relevant=relevant_count,
            ratio=f"{relevance_ratio:.1%}",
        )
        return True

    return False


async def _try_arxiv(
    query: str,
    max_results: int,
    categories: List[str] = None,
) -> List[dict]:
    """Try ArXiv search, return empty list on failure."""
    from src.research.ingestion.searcher import ArxivSearcher

    try:
        searcher = ArxivSearcher()
        results = await searcher.search(
            query=query,
            categories=categories,
            max_results=max_results,
        )
        if results:
            logger.info("arxiv_returned", count=len(results))
        return results or []
    except Exception as e:
        logger.warning(f"arxiv_search_failed: {e}")
        return []


async def _try_openalex(
    query: str,
    max_results: int,
) -> List[dict]:
    """Try OpenAlex search, return empty list on failure.

    OpenAlex title_and_abstract.search requires all terms to match,
    so long queries often return 0 results. We condense the query
    to at most 4 significant words for better recall.
    """
    from src.research.ingestion.searcher import OpenAlexSearcher

    # Condense query for OpenAlex (it needs shorter, focused queries)
    condensed = _condense_for_openalex(query)
    if not condensed:
        return []

    try:
        searcher = OpenAlexSearcher()
        results = await searcher.search(
            query=condensed,
            max_results=max_results,
        )
        if results:
            logger.info("openalex_returned", count=len(results), query=condensed)
        return results or []
    except Exception as e:
        logger.warning(f"openalex_search_failed: {e}")
        return []


def _condense_for_openalex(query: str) -> str:
    """
    Condense a long query for OpenAlex's title_and_abstract.search filter.

    OpenAlex requires ALL terms to match, so long queries like
    'knowledge distillation LLM text to SQL' return 0 results.
    We keep only the most significant 3-4 words.
    """
    stopwords = {
        "and",
        "or",
        "the",
        "a",
        "an",
        "of",
        "for",
        "in",
        "on",
        "to",
        "with",
        "from",
        "about",
        "into",
        "that",
        "this",
        "are",
        "was",
        "is",
        "been",
        "have",
        "has",
        "methods",
        "approaches",
        "techniques",
        "challenges",
        "gaps",
        "summary",
        "review",
        "recent",
        "studies",
    }
    words = [w for w in query.split() if w.lower() not in stopwords and len(w) >= 2]

    if not words:
        return query

    # Keep at most 4 significant words
    condensed = " ".join(words[:4])

    if condensed != query:
        logger.info("openalex_query_condensed", original=query, condensed=condensed)

    return condensed


def _quick_dedup(papers: List[dict]) -> List[dict]:
    """Quick dedup by arxiv_id, DOI, and title fingerprint."""
    seen_ids = set()
    unique = []

    for paper in papers:
        # Check arxiv_id
        aid = paper.get("arxiv_id")
        if aid and aid in seen_ids:
            continue

        # Check DOI
        doi = paper.get("doi")
        if doi:
            doi_key = f"doi:{doi.lower()}"
            if doi_key in seen_ids:
                continue
            seen_ids.add(doi_key)

        # Check title fingerprint
        title = paper.get("title", "").lower().strip()
        authors = paper.get("authors", [])
        first_author = authors[0].lower() if authors else ""
        fp = f"fp:{title[:50]}|{first_author}"
        if fp in seen_ids:
            continue

        # Track IDs
        if aid:
            seen_ids.add(aid)
        seen_ids.add(fp)
        unique.append(paper)

    return unique


def _count_sources(papers: List[dict]) -> dict:
    """Count papers by source type."""
    counts = {}
    for p in papers:
        src = p.get("source_type", "unknown")
        counts[src] = counts.get(src, 0) + 1
    return counts
