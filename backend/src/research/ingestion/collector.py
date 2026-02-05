from abc import ABC, abstractmethod
from typing import List
import httpx
import feedparser
import re
from bs4 import BeautifulSoup
from src.core.models import Paper
from src.utils.pdf_parser import fetch_pdf_content
import datetime

import structlog
logger = structlog.get_logger()

class CollectorInterface(ABC):
    @abstractmethod
    async def collect(self, source: str) -> List[dict]:
        pass

class RSSCollector(CollectorInterface):
    async def collect(self, url: str) -> List[dict]:
        try:
            feed = feedparser.parse(url)
            results = []
            for entry in feed.entries:
                results.append({
                    "title": entry.get("title"),
                    "link": entry.get("link"),
                    "abstract": entry.get("summary", ""),
                    "published_date": entry.get("published_parsed")
                })
            return results
        except Exception as e:
            logger.error("rss_collect_failed", url=url, error=str(e))
            return []

class ArxivCollector(CollectorInterface):
    async def collect(self, url: str) -> List[dict]:
        """
        Collects from a direct ArXiv URL (abs or pdf).
        Extracts metadata from abs page and content from PDF.
        """
        # Normalization: Ensure we have the abs URL for metadata and pdf URL for content
        # Input: https://arxiv.org/abs/2602.02475 or https://arxiv.org/pdf/2602.02475.pdf
        
        arxiv_id_match = re.search(r'(\d{4}\.\d{4,5})', url)
        if not arxiv_id_match:
            logger.warning("arxiv_id_not_found", url=url)
            return []
            
        arxiv_id = arxiv_id_match.group(1)
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        results = []
        try:
            # 1. Fetch Metadata from Abstract Page
            async with httpx.AsyncClient() as client:
                response = await client.get(abs_url, follow_redirects=True, timeout=10.0)
                if response.status_code != 200:
                    logger.warning("arxiv_abs_failed", status=response.status_code)
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract Title (strip "Title:")
                title_tag = soup.find('h1', class_='title')
                title = title_tag.text.replace('Title:', '').strip() if title_tag else f"ArXiv {arxiv_id}"
                
                # Extract Abstract (strip "Abstract:")
                abstract_tag = soup.find('blockquote', class_='abstract')
                abstract = abstract_tag.text.replace('Abstract:', '').strip() if abstract_tag else ""
                
                # 2. Fetch PDF Content
                full_text = await fetch_pdf_content(pdf_url)
                
                results.append({
                    "title": title,
                    "abstract": abstract,
                    "arxiv_id": arxiv_id,
                    "url": abs_url,
                    "pdf_url": pdf_url,
                    "full_text": full_text,
                    "source_type": "arxiv_direct"
                })
                
        except Exception as e:
             logger.error("arxiv_collect_failed", url=url, error=str(e))
             
        return results

class WebCollector(CollectorInterface):
    async def collect(self, url: str) -> List[dict]:
        # Placeholder for direct generic web scraping
        return []

class IngestionFactory:
    @staticmethod
    def get_collector(url: str) -> CollectorInterface:
        if "rss" in url or "xml" in url or "feed" in url:
            return RSSCollector()
        if "arxiv.org" in url:
            return ArxivCollector()
        return WebCollector()
