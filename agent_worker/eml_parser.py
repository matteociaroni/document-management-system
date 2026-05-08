"""Parse a raw .eml file and extract its body text and attachments."""

import email
import email.header
import html
import logging
import re
from dataclasses import dataclass

from text_extractor import extract_text_with_tika, TEXT_PREVIEW_CHARS

logger = logging.getLogger(__name__)

BODY_MAX_CHARS = 2000

@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    size_bytes: int
    content: bytes
    text_preview: str | None


@dataclass
class ParsedEmail:
    """Parsed email containing the body text and all attachments."""
    body_text: str | None
    attachments: list[ParsedAttachment]


def _decode_filename(raw: str) -> str:
    parts = email.header.decode_header(raw)
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def _strip_html(html_text: str) -> str:
    """Crude HTML-to-text: strip tags, decode entities, collapse whitespace."""
    text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_body(msg: email.message.Message) -> str | None:
    """
    Extract the plain-text body from an email message.
    Falls back to stripped HTML if no text/plain part is found.
    Truncates to BODY_MAX_CHARS.
    """
    plain_parts: list[str] = []
    html_parts: list[str] = []

    for part in msg.walk():
        # Skip attachments
        if part.get_content_disposition() in ("attachment", "inline") and part.get_filename():
            continue

        ct = part.get_content_type()
        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="replace")
        except Exception:
            continue

        if ct == "text/plain":
            plain_parts.append(decoded)
        elif ct == "text/html":
            html_parts.append(decoded)

    if plain_parts:
        body = "\n".join(plain_parts)
    elif html_parts:
        body = _strip_html("\n".join(html_parts))
    else:
        return None

    body = body.strip()
    if not body:
        return None
    return body[:BODY_MAX_CHARS]


def parse_attachments(raw_bytes: bytes) -> list[ParsedAttachment]:
    """
    Extract all attachments from a raw RFC 822 email.
    Returns one ParsedAttachment per file found.
    """
    msg = email.message_from_bytes(raw_bytes)
    return _extract_attachments(msg)


def extract_text_preview(content: bytes, mime_type: str | None, filename: str) -> str | None:
    """
    Extract a text preview from a standalone file, mirroring the email-attachment
    pipeline. Uses Apache Tika to uniformly extract text across all file formats.
    """
    if not content:
        return None
        
    mt = mime_type or ""
    
    # Fast path for plain text files to save network call
    if mt.startswith("text/"):
        try:
            return content.decode("utf-8", errors="replace")[:TEXT_PREVIEW_CHARS]
        except Exception:
            pass

    # Use Tika for everything else (PDFs, DOCX, XLSX, images, etc.)
    return extract_text_with_tika(content)


def parse_email(raw_bytes: bytes) -> ParsedEmail:
    """
    Parse a raw RFC 822 email and return both the body text and attachments.
    """
    msg = email.message_from_bytes(raw_bytes)
    body = _extract_body(msg)
    attachments = _extract_attachments(msg)
    logger.info("Parsed email: body=%d chars, %d attachment(s)",
                len(body) if body else 0, len(attachments))
    return ParsedEmail(body_text=body, attachments=attachments)


def _extract_attachments(msg: email.message.Message) -> list[ParsedAttachment]:
    """Extract all attachments from an already-parsed email.message.Message."""
    results: list[ParsedAttachment] = []

    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        if content_disposition not in ("attachment", "inline"):
            continue

        raw_filename = part.get_filename()
        if not raw_filename:
            continue

        filename = _decode_filename(raw_filename)
        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        mime_type = part.get_content_type()
        
        # We reuse the unified `extract_text_preview`
        text_preview = extract_text_preview(payload, mime_type, filename)

        results.append(
            ParsedAttachment(
                filename=filename,
                mime_type=mime_type,
                size_bytes=len(payload),
                content=payload,
                text_preview=text_preview,
            )
        )
        logger.debug("Extracted attachment: %s (%s, %d bytes)", filename, mime_type, len(payload))

    logger.info("Parsed %d attachment(s) from .eml", len(results))
    return results
