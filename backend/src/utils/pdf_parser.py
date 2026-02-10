import hashlib
import httpx
import io
import structlog
from typing import List, Optional, Tuple
from pypdf import PdfReader

logger = structlog.get_logger()


async def fetch_pdf_content(pdf_url: str) -> str:
    """
    Downloads PDF and extracts text using pypdf.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(pdf_url, follow_redirects=True, timeout=30.0)
            if response.status_code == 200:
                pdf_file = io.BytesIO(response.content)
                reader = PdfReader(pdf_file)
                text = ""
                # Extract text from first 10 pages for MVP speed
                for i, page in enumerate(reader.pages):
                    if i > 10:
                        break
                    text += page.extract_text() + "\n"
                return text
            else:
                logger.warning(
                    "pdf_download_failed", url=pdf_url, status=response.status_code
                )
                return ""
    except Exception as e:
        logger.warning("pdf_parse_failed", url=pdf_url, error=str(e))
        return ""


async def fetch_pdf_with_pages(
    pdf_url: str, max_pages: int = 15
) -> Tuple[str, List[dict], str]:
    """
    Downloads PDF and extracts text with page-level metadata.

    Returns:
        Tuple of (full_text, page_infos, pdf_hash) where page_infos is
        a list of {"text": str, "char_start": int, "char_end": int}
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(pdf_url, follow_redirects=True, timeout=30.0)
            if response.status_code != 200:
                logger.warning(
                    "pdf_download_failed", url=pdf_url, status=response.status_code
                )
                return "", [], ""

            content_bytes = response.content
            pdf_hash = hashlib.sha256(content_bytes).hexdigest()

            pdf_file = io.BytesIO(content_bytes)
            reader = PdfReader(pdf_file)

            full_text = ""
            page_infos = []

            for i, page in enumerate(reader.pages):
                if i >= max_pages:
                    break
                page_text = page.extract_text() or ""
                char_start = len(full_text)
                full_text += page_text + "\n"
                char_end = len(full_text)
                page_infos.append(
                    {
                        "text": page_text,
                        "char_start": char_start,
                        "char_end": char_end,
                    }
                )

            return full_text, page_infos, pdf_hash

    except Exception as e:
        logger.warning("pdf_parse_failed", url=pdf_url, error=str(e))
        return "", [], ""


def find_snippet_location(
    full_text: str, snippet: str, page_infos: List[dict]
) -> Optional[dict]:
    """
    Find where a snippet appears in the full text and resolve to page number.

    Returns:
        dict with keys: page, section, char_start, char_end, or None if not found.
    """
    if not snippet or not full_text:
        return None

    # Exact match
    idx = full_text.find(snippet)

    # Fuzzy: try first 80 chars of snippet
    if idx == -1 and len(snippet) > 80:
        idx = full_text.find(snippet[:80])

    # Fuzzy: try normalized whitespace
    if idx == -1:
        normalized_text = " ".join(full_text.split())
        normalized_snippet = " ".join(snippet.split())
        norm_idx = normalized_text.find(normalized_snippet)
        if norm_idx != -1:
            # Approximate char position in original text
            idx = norm_idx

    if idx == -1:
        return None

    char_start = idx
    char_end = idx + len(snippet)

    # Resolve page number
    page = None
    if page_infos:
        for i, pi in enumerate(page_infos):
            if pi["char_start"] <= char_start < pi["char_end"]:
                page = i + 1  # 1-indexed
                break

    return {
        "page": page,
        "section": None,
        "char_start": char_start,
        "char_end": char_end,
    }
