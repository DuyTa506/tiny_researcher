"""
PDF Loader Service

Selectively loads full text for high-relevance papers (score >= 8).
Implements lazy loading with Redis caching to avoid repeated downloads.
"""

import logging
from typing import List, Optional
from src.core.models import Paper
from src.utils.pdf_parser import fetch_pdf_content
from src.tools.cache_manager import ToolCacheManager

logger = logging.getLogger(__name__)


class PDFLoaderService:
    """
    Service for selectively loading full text from PDFs.

    Features:
    - Only loads PDFs for papers with score >= threshold
    - Redis caching with 7-day TTL
    - Graceful fallback if PDF download fails

    Usage:
        loader = PDFLoaderService(cache_manager, threshold=8.0)
        await loader.load_full_text_batch(papers)
    """

    PDF_CACHE_TTL = 604800  # 7 days in seconds

    def __init__(
        self,
        cache_manager: Optional[ToolCacheManager] = None,
        relevance_threshold: float = 8.0
    ):
        """
        Initialize PDF loader.

        Args:
            cache_manager: Optional cache for PDF content
            relevance_threshold: Minimum score to load full text (default: 8.0)
        """
        self.cache_manager = cache_manager
        self.relevance_threshold = relevance_threshold

    async def load_full_text(self, paper: Paper) -> bool:
        """
        Load full text for a single paper if it meets threshold.

        Args:
            paper: Paper object to load full text for

        Returns:
            True if full text was loaded, False otherwise
        """
        # Skip if already has full text
        if paper.full_text:
            return True

        # Skip if below threshold
        if not paper.relevance_score or paper.relevance_score < self.relevance_threshold:
            logger.debug(f"Skipping PDF for paper {paper.title[:50]} (score: {paper.relevance_score})")
            return False

        # Skip if no PDF URL
        if not paper.pdf_url:
            logger.warning(f"No PDF URL for paper {paper.title[:50]}")
            return False

        # Check cache first
        if self.cache_manager:
            cached_text = await self._get_cached_pdf(paper.pdf_url)
            if cached_text:
                paper.full_text = cached_text
                logger.info(f"Loaded full text from cache for {paper.title[:50]}")
                return True

        # Download PDF
        try:
            logger.info(f"Downloading PDF for {paper.title[:50]} (score: {paper.relevance_score})")
            full_text = await fetch_pdf_content(paper.pdf_url)

            if full_text:
                paper.full_text = full_text

                # Cache the result
                if self.cache_manager:
                    await self._cache_pdf(paper.pdf_url, full_text)

                logger.info(f"Successfully loaded {len(full_text)} chars of full text")
                return True
            else:
                logger.warning(f"PDF download returned empty content for {paper.pdf_url}")
                return False

        except Exception as e:
            logger.error(f"Error loading PDF for {paper.title[:50]}: {e}")
            return False

    async def load_full_text_batch(self, papers: List[Paper]) -> int:
        """
        Load full text for multiple papers (only high-relevance ones).

        Args:
            papers: List of papers

        Returns:
            Number of papers with full text loaded
        """
        loaded_count = 0

        for paper in papers:
            if await self.load_full_text(paper):
                loaded_count += 1

        logger.info(
            f"Loaded full text for {loaded_count}/{len(papers)} papers "
            f"(threshold: {self.relevance_threshold})"
        )

        return loaded_count

    async def _get_cached_pdf(self, pdf_url: str) -> Optional[str]:
        """Get cached PDF content."""
        if not self.cache_manager or not self.cache_manager.redis:
            return None

        try:
            key = f"pdf_cache:{pdf_url}"
            cached = await self.cache_manager.redis.get(key)
            return cached if cached else None
        except Exception as e:
            logger.error(f"Error reading PDF cache: {e}")
            return None

    async def _cache_pdf(self, pdf_url: str, content: str):
        """Cache PDF content with TTL."""
        if not self.cache_manager or not self.cache_manager.redis:
            return

        try:
            key = f"pdf_cache:{pdf_url}"
            await self.cache_manager.redis.setex(key, self.PDF_CACHE_TTL, content)
            logger.debug(f"Cached PDF content ({len(content)} chars)")
        except Exception as e:
            logger.error(f"Error caching PDF: {e}")
