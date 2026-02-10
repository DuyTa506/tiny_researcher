"""
PDF Loader Service

Selectively loads full text for high-relevance papers (score >= 8).
Implements lazy loading with Redis caching to avoid repeated downloads.
Skips known paywalled publisher domains to avoid wasted 403 requests.
"""

import json
import logging
from typing import List, Optional
from urllib.parse import urlparse
from src.core.models import Paper, PaperStatus, Locator
from src.utils.pdf_parser import (
    fetch_pdf_content,
    fetch_pdf_with_pages,
    find_snippet_location,
)
from src.tools.cache_manager import ToolCacheManager

logger = logging.getLogger(__name__)

# Domains known to block automated PDF downloads (403/paywall)
_BLOCKED_PDF_DOMAINS = {
    "dl.acm.org",
    "onlinelibrary.wiley.com",
    "academic.oup.com",
    "link.springer.com",
    "www.sciencedirect.com",
    "ieeexplore.ieee.org",
    "www.nature.com",
    "science.org",
    "www.science.org",
    "journals.sagepub.com",
    "www.tandfonline.com",
    "www.jstor.org",
    "www.emerald.com",
    "www.cambridge.org",
    "www.pnas.org",
    "www.cell.com",
    "www.termedia.pl",
}

# Domains known to provide open-access PDFs
_ALLOWED_PDF_DOMAINS = {
    "arxiv.org",
    "openreview.net",
    "aclanthology.org",
    "proceedings.mlr.press",
    "papers.nips.cc",
    "proceedings.neurips.cc",
    "www.mdpi.com",
    "ojs.aaai.org",
}


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
        relevance_threshold: float = 8.0,
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
        if (
            not paper.relevance_score
            or paper.relevance_score < self.relevance_threshold
        ):
            logger.debug(
                f"Skipping PDF for paper {paper.title[:50]} (score: {paper.relevance_score})"
            )
            return False

        # Skip if no PDF URL
        if not paper.pdf_url:
            logger.warning(f"No PDF URL for paper {paper.title[:50]}")
            return False

        # Skip paywalled publisher domains
        if self._is_blocked_domain(paper.pdf_url):
            logger.info(
                f"Skipping paywalled PDF for {paper.title[:50]} ({paper.pdf_url[:60]})"
            )
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
            logger.info(
                f"Downloading PDF for {paper.title[:50]} (score: {paper.relevance_score})"
            )
            full_text = await fetch_pdf_content(paper.pdf_url)

            if full_text:
                paper.full_text = full_text

                # Cache the result
                if self.cache_manager:
                    await self._cache_pdf(paper.pdf_url, full_text)

                logger.info(f"Successfully loaded {len(full_text)} chars of full text")
                return True
            else:
                logger.warning(
                    f"PDF download returned empty content for {paper.pdf_url}"
                )
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

    @staticmethod
    def _is_blocked_domain(url: str) -> bool:
        """Check if URL is from a known paywalled publisher domain."""
        try:
            domain = urlparse(url).netloc.lower()
            return domain in _BLOCKED_PDF_DOMAINS
        except Exception:
            return False

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

    async def load_full_text_with_pages(self, paper: Paper) -> bool:
        """
        Load full text with page-level mapping for evidence locator support.

        Sets paper.full_text, paper.page_map, paper.pdf_hash, and
        transitions paper.status to FULLTEXT.
        """
        if paper.full_text and paper.page_map:
            return True

        if not paper.pdf_url:
            logger.warning(f"No PDF URL for paper {paper.title[:50]}")
            return False

        # Check cache for page-mapped version
        if self.cache_manager:
            cached = await self._get_cached_pages(paper.pdf_url)
            if cached:
                paper.full_text = cached["full_text"]
                paper.page_map = cached["page_infos"]
                paper.pdf_hash = cached.get("pdf_hash")
                paper.status = PaperStatus.FULLTEXT
                return True

        try:
            logger.info(f"Downloading PDF with page mapping for {paper.title[:50]}")
            full_text, page_infos, pdf_hash = await fetch_pdf_with_pages(paper.pdf_url)

            if full_text:
                paper.full_text = full_text
                paper.page_map = page_infos
                paper.pdf_hash = pdf_hash
                paper.status = PaperStatus.FULLTEXT

                if self.cache_manager:
                    await self._cache_pages(
                        paper.pdf_url, full_text, page_infos, pdf_hash
                    )

                return True
            return False

        except Exception as e:
            logger.error(f"Error loading PDF with pages for {paper.title[:50]}: {e}")
            return False

    async def load_batch_with_pages(self, papers: List[Paper]) -> int:
        """Load full text with page mapping for multiple papers."""
        loaded = 0
        for paper in papers:
            if await self.load_full_text_with_pages(paper):
                loaded += 1
        logger.info(f"Loaded {loaded}/{len(papers)} papers with page mapping")
        return loaded

    def resolve_locator(self, paper: Paper, snippet: str) -> Locator:
        """
        Resolve a snippet to a Locator within a paper.

        Uses page_map if available, otherwise does best-effort char offset.
        """
        if not paper.full_text or not snippet:
            return Locator()

        page_infos = paper.page_map if isinstance(paper.page_map, list) else []
        location = find_snippet_location(paper.full_text, snippet, page_infos)

        if location:
            return Locator(
                page=location.get("page"),
                section=location.get("section"),
                char_start=location.get("char_start"),
                char_end=location.get("char_end"),
            )
        return Locator()

    async def _get_cached_pages(self, pdf_url: str) -> Optional[dict]:
        """Get cached PDF with page info."""
        if not self.cache_manager or not self.cache_manager.redis:
            return None
        try:
            key = f"pdf_pages_cache:{pdf_url}"
            cached = await self.cache_manager.redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error reading PDF pages cache: {e}")
            return None

    async def _cache_pages(
        self, pdf_url: str, full_text: str, page_infos: list, pdf_hash: str
    ):
        """Cache PDF with page info."""
        if not self.cache_manager or not self.cache_manager.redis:
            return
        try:
            key = f"pdf_pages_cache:{pdf_url}"
            data = json.dumps(
                {
                    "full_text": full_text,
                    "page_infos": page_infos,
                    "pdf_hash": pdf_hash,
                }
            )
            await self.cache_manager.redis.setex(key, self.PDF_CACHE_TTL, data)
        except Exception as e:
            logger.error(f"Error caching PDF pages: {e}")
