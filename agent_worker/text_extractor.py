import httpx
import logging

logger = logging.getLogger(__name__)

# Constants for truncation to avoid context window explosion
TEXT_PREVIEW_CHARS = 2000

def extract_text_with_tika(content: bytes) -> str | None:
    """Send bytes to Tika server and get plain text back.

    Returns the FULL extracted text (no truncation). Callers that need a
    shorter preview for the LLM should truncate to TEXT_PREVIEW_CHARS
    themselves.
    """
    if not content:
        return None
        
    try:
        url = "http://tika:9998/tika"
        
        response = httpx.put(
            url, 
            content=content, 
            headers={"Accept": "text/plain"},
            timeout=30.0
        )
        response.raise_for_status()
        
        text = response.text.strip()
        return text if text else None
        
    except Exception as e:
        logger.warning(f"Failed to extract text with Tika: {e}")
        return None
