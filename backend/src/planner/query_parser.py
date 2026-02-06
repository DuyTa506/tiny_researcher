"""
QueryParser - Simple query analysis for adaptive planning.

Simplified to just 2 types (QUICK/FULL) to reduce LLM hallucination.
Works with any language.
"""

import re
import logging
from typing import Optional, List, Set
from src.adapters.llm import LLMClientInterface
from src.core.schema import ResearchQuery, QueryType

logger = logging.getLogger(__name__)

# URL pattern for detection
URL_PATTERN = re.compile(
    r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}'
    r'\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
)

# Keywords indicating QUICK mode (multilingual)
QUICK_KEYWORDS: Set[str] = {
    # English
    "quick", "fast", "brief", "simple", "basic", "short", "just find",
    # Vietnamese
    "nhanh", "ngắn", "đơn giản", "cơ bản",
    # Chinese
    "快速", "简单", "基本",
}

# Keywords indicating FULL mode (multilingual)
FULL_KEYWORDS: Set[str] = {
    # English
    "comprehensive", "thorough", "complete", "detailed", "in-depth",
    "survey", "overview", "full", "deep", "all",
    # Vietnamese
    "toàn diện", "chi tiết", "đầy đủ", "sâu",
    # Chinese
    "全面", "详细", "完整", "深入",
}


class QueryParser:
    """
    Simple query parser - just determines QUICK vs FULL.

    QUICK (4 phases): Planning → Execution → Persistence → Analysis
    FULL (8 phases): + PDF Loading → Summarization → Clustering → Writing
    """

    def __init__(self, llm_client: Optional[LLMClientInterface] = None):
        self.llm = llm_client

    async def parse(self, query: str, use_llm: bool = False) -> ResearchQuery:
        """
        Parse query into ResearchQuery.

        Args:
            query: Raw user query
            use_llm: Whether to use LLM (default False - use rules)

        Returns:
            ResearchQuery with type and topic
        """
        return self._parse_with_rules(query)

    def _parse_with_rules(self, query: str) -> ResearchQuery:
        """Simple rule-based parsing."""
        query_clean = query.strip()
        query_lower = query_clean.lower()
        words = set(query_lower.split())

        # Extract URLs
        urls = URL_PATTERN.findall(query)
        has_urls = len(urls) > 0

        # Detect query type
        query_type = self._detect_type(query_lower, words)

        # Extract main topic (just use the query as topic)
        main_topic = self._extract_topic(query_clean)

        return ResearchQuery(
            original_query=query,
            query_type=query_type,
            main_topic=main_topic,
            has_urls=has_urls,
            urls=urls,
            skip_synthesis=(query_type == QueryType.QUICK),
            confidence=0.8
        )

    def _detect_type(self, query_lower: str, words: Set[str]) -> QueryType:
        """Detect QUICK or FULL."""
        # Check for QUICK indicators
        if words & QUICK_KEYWORDS:
            return QueryType.QUICK

        # Check for FULL indicators
        if words & FULL_KEYWORDS:
            return QueryType.FULL

        # Default to FULL for research tasks
        return QueryType.FULL

    def _extract_topic(self, query: str) -> str:
        """Extract main topic from query."""
        # Remove common prefixes (multilingual)
        prefixes = [
            # English
            "research", "find papers on", "search for", "look up",
            "survey of", "overview of", "tell me about",
            # Vietnamese
            "nghiên cứu về", "tìm bài báo về", "tìm kiếm",
        ]

        result = query.strip()
        result_lower = result.lower()

        for prefix in prefixes:
            if result_lower.startswith(prefix):
                result = result[len(prefix):].strip()
                result_lower = result.lower()

        return result if result else query

    def get_phase_config(self, query: ResearchQuery) -> dict:
        """
        Get phase configuration based on query type.

        Returns dict with active phases.
        """
        if query.query_type == QueryType.QUICK:
            return {
                "active_phases": ["planning", "execution", "persistence", "analysis"],
                "skip_synthesis": True
            }
        else:  # FULL
            return {
                "active_phases": [
                    "planning", "execution", "persistence", "analysis",
                    "pdf_loading", "summarization", "clustering", "writing"
                ],
                "skip_synthesis": False
            }
