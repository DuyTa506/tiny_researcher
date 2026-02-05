import httpx
import io
import structlog
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
                    if i > 10: break 
                    text += page.extract_text() + "\n"
                return text
            else:
                logger.warning("pdf_download_failed", url=pdf_url, status=response.status_code)
                return ""
    except Exception as e:
            logger.warning("pdf_parse_failed", url=pdf_url, error=str(e))
            return ""
