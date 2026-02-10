
from typing import List, Optional
from abc import ABC, abstractmethod
import httpx
import re
from datetime import datetime
import asyncio
import time
import structlog

logger = structlog.get_logger()

# Global rate limiter for ArXiv API
# ArXiv policy: max 1 request per 3 seconds
_arxiv_semaphore = asyncio.Semaphore(1)  # Only 1 concurrent request
_arxiv_last_request_time = 0.0
_arxiv_min_interval = 3.5  # 3.5 seconds between requests (safety margin)

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
        Search ArXiv by keyword with rate limiting and retry logic.

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

        # Rate limiting and retry logic
        max_retries = 3
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # Global rate limiter - only 1 request at a time
                async with _arxiv_semaphore:
                    global _arxiv_last_request_time

                    # Ensure minimum interval between requests (3.5 seconds)
                    elapsed = time.time() - _arxiv_last_request_time
                    if elapsed < _arxiv_min_interval:
                        sleep_time = _arxiv_min_interval - elapsed
                        logger.info("arxiv_rate_limit_sleep", sleep_seconds=sleep_time)
                        await asyncio.sleep(sleep_time)

                    # Make request
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(self.BASE_URL, params=params)
                        _arxiv_last_request_time = time.time()

                        # Handle 429 (rate limit)
                        if response.status_code == 429:
                            retry_after = response.headers.get("Retry-After")

                            if retry_after:
                                # Use Retry-After header if available
                                wait_time = float(retry_after)
                                logger.warning("arxiv_429_retry_after",
                                             retry_after=wait_time,
                                             retry_count=retry_count)
                            else:
                                # Exponential backoff with jitter
                                base_wait = min(10 * (2 ** retry_count), 60)  # Cap at 60s
                                jitter = base_wait * 0.2 * (0.5 + asyncio.get_event_loop().time() % 0.5)
                                wait_time = base_wait + jitter
                                logger.warning("arxiv_429_exponential_backoff",
                                             wait_seconds=wait_time,
                                             retry_count=retry_count)

                            # Wait and retry
                            await asyncio.sleep(wait_time)
                            retry_count += 1
                            continue

                        # Handle other errors
                        if response.status_code != 200:
                            logger.error("arxiv_api_failed",
                                       status=response.status_code,
                                       retry_count=retry_count)

                            if retry_count < max_retries:
                                # Retry with backoff for server errors (500+)
                                if response.status_code >= 500:
                                    wait_time = 5 * (retry_count + 1)
                                    logger.info("arxiv_server_error_retry", wait_seconds=wait_time)
                                    await asyncio.sleep(wait_time)
                                    retry_count += 1
                                    continue

                            return []

                        # Success!
                        results = self._parse_atom_response(response.text)
                        logger.info("arxiv_search_complete", count=len(results))
                        return results

            except Exception as e:
                logger.error("arxiv_search_error", error=str(e), retry_count=retry_count)

                if retry_count < max_retries:
                    wait_time = 5 * (retry_count + 1)
                    await asyncio.sleep(wait_time)
                    retry_count += 1
                else:
                    break

        # All retries exhausted
        logger.error("arxiv_search_failed_all_retries", max_retries=max_retries)
        return []
    
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


class OpenAlexSearcher(SearcherInterface):
    """
    Searches OpenAlex API for academic papers.
    Docs: https://docs.openalex.org

    No auth required. Adding mailto= gets polite pool (10 req/sec).
    Rate limit: 100k requests/day.
    """
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, mailto: str = None):
        from src.core.config import settings
        self.mailto = mailto or getattr(settings, 'OPENALEX_MAILTO', None)

    async def search(
        self,
        query: str,
        max_results: int = 50,
        publication_year: str = None,
    ) -> List[dict]:
        """
        Search OpenAlex by keyword with rate limiting.

        Args:
            query: Search query (full-text search across title/abstract)
            max_results: Maximum results to return (max 200 per page)
            publication_year: Optional year filter (e.g. "2023", ">2020", "2020-2024")

        Returns:
            List of paper dicts with standardized fields
        """
        params = {
            "page": 1,
            "per_page": min(max_results, 200),
            "sort": "relevance_score:desc",
            "select": "id,title,authorships,publication_year,doi,open_access,primary_location,abstract_inverted_index,cited_by_count,type",
        }

        if self.mailto:
            params["mailto"] = self.mailto

        # Build filters - use title_and_abstract.search for better relevance
        filters = [
            f"title_and_abstract.search:{query}",
            "has_fulltext:true",
        ]
        if publication_year:
            filters.append(f"publication_year:{publication_year}")
        params["filter"] = ",".join(filters)

        logger.info("openalex_search_start", query=query, max_results=max_results)

        max_retries = 3
        retry_count = 0

        while retry_count <= max_retries:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(self.BASE_URL, params=params)

                    if response.status_code == 429 or response.status_code == 403:
                        wait_time = min(5 * (2 ** retry_count), 60)
                        logger.warning("openalex_rate_limited",
                                     status=response.status_code,
                                     wait_seconds=wait_time,
                                     retry_count=retry_count)
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        continue

                    if response.status_code >= 500:
                        wait_time = 5 * (retry_count + 1)
                        logger.warning("openalex_server_error",
                                     status=response.status_code,
                                     wait_seconds=wait_time)
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        continue

                    if response.status_code != 200:
                        logger.error("openalex_api_failed", status=response.status_code)
                        return []

                    data = response.json()
                    results = self._parse_response(data)
                    logger.info("openalex_search_complete", count=len(results))
                    return results

            except Exception as e:
                logger.error("openalex_search_error", error=str(e), retry_count=retry_count)
                if retry_count < max_retries:
                    await asyncio.sleep(5 * (retry_count + 1))
                    retry_count += 1
                else:
                    break

        logger.error("openalex_search_failed_all_retries", max_retries=max_retries)
        return []

    def _parse_response(self, data: dict) -> List[dict]:
        """Parse OpenAlex JSON response into standardized paper dicts."""
        results = []

        for work in data.get("results", []):
            # Title
            title = work.get("title", "")
            if not title:
                continue

            # Abstract - reconstruct from inverted index
            abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))

            # Authors
            authors = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name")
                if name:
                    authors.append(name)

            # DOI
            doi = work.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]

            # URLs
            openalex_id = work.get("id", "")
            url = openalex_id  # OpenAlex URL

            # PDF URL from open access
            pdf_url = None
            oa = work.get("open_access", {})
            if oa and oa.get("oa_url"):
                pdf_url = oa["oa_url"]

            # Also check primary_location for PDF
            primary = work.get("primary_location", {})
            if primary and not pdf_url:
                landing = primary.get("landing_page_url")
                if landing:
                    url = landing
                pdf_loc = primary.get("pdf_url")
                if pdf_loc:
                    pdf_url = pdf_loc

            # Check if this has an arXiv ID (from DOI or URL)
            arxiv_id = None
            if doi and "arxiv" in doi.lower():
                arxiv_match = re.search(r'(\d{4}\.\d{4,5})', doi)
                if arxiv_match:
                    arxiv_id = arxiv_match.group(1)
            if pdf_url and "arxiv.org" in pdf_url:
                arxiv_match = re.search(r'(\d{4}\.\d{4,5})', pdf_url)
                if arxiv_match:
                    arxiv_id = arxiv_match.group(1)

            # Published year
            pub_year = work.get("publication_year")
            published = f"{pub_year}-01-01T00:00:00Z" if pub_year else None

            results.append({
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "url": url,
                "pdf_url": pdf_url,
                "published": published,
                "source_type": "openalex",
                "cited_by_count": work.get("cited_by_count", 0),
                "openalex_id": openalex_id,
                "publication_year": pub_year,
            })

        return results

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""

        # inverted_index: {"word": [position1, position2, ...], ...}
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))

        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions)


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
