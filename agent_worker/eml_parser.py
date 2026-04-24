"""Parse a raw .eml file and extract its attachments."""

import email
import email.header
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TEXT_PREVIEW_CHARS = 500


@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    size_bytes: int
    content: bytes
    text_preview: str | None


def _decode_filename(raw: str) -> str:
    parts = email.header.decode_header(raw)
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def parse_attachments(raw_bytes: bytes) -> list[ParsedAttachment]:
    """
    Extract all attachments from a raw RFC 822 email.
    Returns one ParsedAttachment per file found.
    """
    msg = email.message_from_bytes(raw_bytes)
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

        text_preview = None
        if mime_type.startswith("text/"):
            charset = part.get_content_charset() or "utf-8"
            try:
                text_preview = payload.decode(charset, errors="replace")[:TEXT_PREVIEW_CHARS]
            except Exception:
                pass

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
