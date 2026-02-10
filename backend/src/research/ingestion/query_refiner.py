"""
QueryRefiner - LLM-based query refinement for poor search results.

When a search returns too few or irrelevant results, the refiner:
1. Analyzes why the query might have failed
2. Generates alternative search queries
3. Returns refined queries for retry

Works without LLM as fallback using heuristic rules.
"""

import json
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class QueryRefiner:
    """
    Refines search queries when results are poor.

    Strategy:
    1. Try LLM-based refinement (best quality)
    2. Fall back to heuristic rules (no API needed)
    """

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            try:
                from src.adapters.llm import GeminiAdapter
                from src.core.config import settings
                api_key = getattr(settings, 'GEMINI_API_KEY', None)
                if api_key:
                    self._llm = GeminiAdapter(
                        api_key=api_key,
                        model_name="gemini-2.0-flash"
                    )
            except Exception as e:
                logger.warning(f"query_refiner_llm_init_failed: {e}")
        return self._llm

    async def refine(
        self,
        original_query: str,
        num_results: int = 0,
        tried_queries: List[str] = None,
    ) -> List[str]:
        """
        Generate refined search queries.

        Args:
            original_query: The original query that produced poor results
            num_results: How many results the original query returned
            tried_queries: Queries already attempted (to avoid repeats)

        Returns:
            List of 2-3 refined query strings to try
        """
        tried = set(q.lower().strip() for q in (tried_queries or []))

        # Try LLM refinement first
        llm = self._get_llm()
        if llm:
            refined = await self._refine_with_llm(
                original_query, num_results, tried
            )
            if refined:
                return refined

        # Fallback to heuristic rules
        return self._refine_heuristic(original_query, tried)

    async def _refine_with_llm(
        self,
        query: str,
        num_results: int,
        tried: set,
    ) -> List[str]:
        """Use LLM to generate refined queries."""
        tried_list = ", ".join(f'"{q}"' for q in tried) if tried else "none"

        prompt = f"""You are an academic search query optimizer. A user searched for academic papers but got poor results.

Original query: "{query}"
Results found: {num_results} (too few or irrelevant)
Already tried: {tried_list}

Analyze why this query might fail and suggest 2-3 DIFFERENT search queries that would find relevant academic papers.

Common issues:
- Product/model names that don't match paper titles (e.g. "DeepSeek OCR" → the model might be called "DeepSeek-VL" or just "DeepSeek vision")
- Too specific terms that narrow results too much
- Informal language that doesn't match academic writing style
- Missing key academic terms or synonyms

Rules:
- Each query should be in English (academic papers are mostly in English)
- Use academic/technical terminology
- Each query should take a different angle (broader, narrower, synonyms)
- Do NOT repeat any already-tried queries
- Keep queries concise (2-6 words each)

Return ONLY a JSON array of query strings, nothing else:
["query1", "query2", "query3"]"""

        try:
            response = await self._llm.generate(prompt, json_mode=True)
            queries = json.loads(response.strip())

            if isinstance(queries, list):
                # Filter out already-tried queries
                filtered = [
                    q for q in queries
                    if isinstance(q, str)
                    and q.lower().strip() not in tried
                    and len(q.strip()) > 2
                ]
                if filtered:
                    logger.info("query_refine_llm_success",
                               original=query,
                               refined=filtered)
                    return filtered[:3]

        except Exception as e:
            logger.warning(f"query_refine_llm_failed: {e}")

        return []

    def _refine_heuristic(
        self,
        query: str,
        tried: set,
    ) -> List[str]:
        """
        Heuristic query refinement without LLM.

        Rules:
        1. Remove version numbers (OCR 1 → OCR)
        2. Try core terms (must be >= 2 words)
        3. Try 2-word subsets for multi-concept queries
        4. Try broader variants (add "survey")

        NEVER generates single-word queries - they produce garbage results.
        """
        suggestions = []
        seen = set(tried)

        def _add(q: str):
            q = q.strip()
            # Enforce minimum 2 words to avoid garbage single-word searches
            word_count = len(q.split())
            if q and q.lower() not in seen and word_count >= 2:
                seen.add(q.lower())
                suggestions.append(q)

        # Remove version numbers and clean up stopwords left behind
        cleaned = re.sub(r'\b(v?\d+(\.\d+)*)\b', '', query).strip()
        # Remove dangling conjunctions/prepositions
        cleaned = re.sub(r'\b(and|or|the|a|an|of|for|in|on|to|with)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        _add(cleaned)

        # Try just significant words (>2 chars, no stopwords)
        stopwords = {'and', 'or', 'the', 'a', 'an', 'of', 'for', 'in', 'on', 'to', 'with', 'is', 'are', 'was'}
        words = [w for w in query.split() if len(w) > 2 and w.lower() not in stopwords]
        if len(words) >= 2:
            _add(" ".join(words))

        # Try 2-word pairs from significant words (NOT single words)
        # e.g. "knowledge distillation LLM text SQL" → "knowledge distillation", "distillation LLM"
        if len(words) >= 3:
            for i in range(len(words) - 1):
                _add(f"{words[i]} {words[i+1]}")

        # Try adding "survey" for broader results
        base = cleaned or query
        _add(f"{base} survey")

        return suggestions[:3]
