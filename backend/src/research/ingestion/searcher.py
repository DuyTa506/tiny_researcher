
from typing import List, Optional
from abc import ABC, abstractmethod
import httpx
import re
from datetime import datetime
import structlog

logger = structlog.get_logger()

class SearcherInterface(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = 50) -> List[dict]:
        pass

class ArxivSearcher(SearcherInterface):
    """
    Searches ArXiv using the Export API.
    Docs: https://info.arxiv.org/help/api/basics.html
    
    Query examples:
        - all:keyword (search all fields)
        - ti:keyword (title only)
        - abs:keyword (abstract only)
        - cat:cs.AI (category filter)
    """
    BASE_URL = "https://export.arxiv.org/api/query"
    
    async def search(
        self, 
        query: str, 
        categories: Optional[List[str]] = None,
        max_results: int = 50,
        start: int = 0
    ) -> List[dict]:
        """
        Search ArXiv by keyword.
        
        Args:
            query: Search query (will be wrapped in all:)
            categories: Optional list of categories like ["cs.AI", "cs.LG"]
            max_results: Maximum results to return
            start: Pagination offset
            
        Returns:
            List of paper dicts with title, abstract, arxiv_id, url, pdf_url, published, authors, categories
        """
        # Build query string
        search_query = f"all:{query}"
        if categories:
            cat_query = "+OR+".join([f"cat:{cat}" for cat in categories])
            search_query = f"({search_query})+AND+({cat_query})"
        
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        logger.info("arxiv_search_start", query=query, categories=categories, max_results=max_results)
        
        results = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    logger.error("arxiv_api_failed", status=response.status_code)
                    return []
                
                results = self._parse_atom_response(response.text)
                logger.info("arxiv_search_complete", count=len(results))
                
        except Exception as e:
            logger.error("arxiv_search_error", error=str(e))
            
        return results
    
    def _parse_atom_response(self, xml_text: str) -> List[dict]:
        """Parse ArXiv Atom XML response into paper dicts."""
        import xml.etree.ElementTree as ET
        
        results = []
        
        # Namespaces
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom',
            'opensearch': 'http://a9.com/-/spec/opensearch/1.1/'
        }
        
        try:
            root = ET.fromstring(xml_text)
            
            for entry in root.findall('atom:entry', ns):
                # ID: http://arxiv.org/abs/2208.10099v1 -> 2208.10099
                id_text = entry.find('atom:id', ns).text
                arxiv_id_match = re.search(r'(\d{4}\.\d{4,5})', id_text)
                arxiv_id = arxiv_id_match.group(1) if arxiv_id_match else id_text
                
                # Title
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                
                # Abstract (summary)
                summary_el = entry.find('atom:summary', ns)
                abstract = summary_el.text.strip().replace('\n', ' ') if summary_el is not None else ""
                
                # Published date
                published_el = entry.find('atom:published', ns)
                published = published_el.text if published_el is not None else None
                
                # Authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_el = author.find('atom:name', ns)
                    if name_el is not None:
                        authors.append(name_el.text)
                
                # Categories
                categories = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term')
                    if term:
                        categories.append(term)
                
                # Links
                url = f"https://arxiv.org/abs/{arxiv_id}"
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                
                results.append({
                    "title": title,
                    "abstract": abstract,
                    "arxiv_id": arxiv_id,
                    "url": url,
                    "pdf_url": pdf_url,
                    "published": published,
                    "authors": authors,
                    "categories": categories,
                    "source_type": "arxiv_api"
                })
                
        except ET.ParseError as e:
            logger.error("arxiv_xml_parse_error", error=str(e))
            
        return results

    async def search_by_keywords(
        self, 
        keywords: List[str], 
        categories: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[dict]:
        """
        Search with multiple keywords (OR query).
        """
        # Join keywords with OR, each wrapped in quotes for phrase matching
        query = " OR ".join([f'"{kw}"' for kw in keywords])
        return await self.search(query, categories, max_results)


class HuggingFaceSearcher(SearcherInterface):
    """
    Scrapes Hugging Face Trending Papers using Playwright.
    """
    BASE_URL = "https://huggingface.co/papers/trending"
    
    async def search(self, query: str, max_results: int = 10) -> List[dict]:
        from playwright.async_api import async_playwright
        from src.utils.pdf_parser import fetch_pdf_content
        
        logger.info("hf_search_start", query=query)
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                url = f"{self.BASE_URL}?q={query}"
                await page.goto(url, wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector("article", timeout=10000)
                except Exception:
                    logger.warning("hf_no_articles_found", query=query)
                    return []
                
                articles = await page.locator("article").all()
                
                for article in articles[:max_results]:
                    try:
                        link_el = article.locator("a[href^='/papers/']").first
                        href = await link_el.get_attribute("href")
                        
                        if not href:
                            continue
                            
                        arxiv_id = href.split("/")[-1]
                        
                        title_el = article.locator("h3")
                        title = await title_el.text_content() if await title_el.count() > 0 else f"Paper {arxiv_id}"

                        abstract_el = article.locator("p.text-gray-500, p.text-gray-600").first
                        abstract = await abstract_el.text_content() if await abstract_el.count() > 0 else ""
                        
                        detail_url = f"https://huggingface.co{href}"
                        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
                        
                        full_text = await fetch_pdf_content(pdf_url)
                        
                        results.append({
                            "title": title.strip() if title else f"Paper {arxiv_id}",
                            "abstract": abstract.strip(),
                            "arxiv_id": arxiv_id,
                            "url": detail_url,
                            "pdf_url": pdf_url,
                            "full_text": full_text,
                            "source_type": "huggingface_trending"
                        })
                            
                    except Exception as e:
                        logger.warning("hf_article_parse_failed", error=str(e))
                        continue
                        
            except Exception as e:
                logger.error("hf_search_failed", query=query, error=str(e))
            finally:
                await browser.close()
                
        return results
