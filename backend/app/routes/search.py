"""Full-text search endpoint powered by OpenSearch (per-tenant index)."""

from __future__ import annotations

import logging
from typing import Optional, List
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from opensearchpy import OpenSearch, NotFoundError as OSNotFoundError
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# ── OpenSearch helpers ──────────────────────────────────────────────────────

_os_client: Optional[OpenSearch] = None


def _get_client() -> OpenSearch:
    global _os_client
    if _os_client is None:
        parsed = urlparse(settings.opensearch_url)
        _os_client = OpenSearch(
            hosts=[{"host": parsed.hostname, "port": parsed.port or 9200}],
            use_ssl=False,
            verify_certs=False,
        )
    return _os_client


def _get_index_name(owner_id) -> str:
    """Per-tenant index name: documents_<uuid_without_hyphens>."""
    return f"documents_{str(owner_id).replace('-', '')}"


# ── Response schemas ────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    document_id: UUID
    filename: str
    folder_id: Optional[UUID] = None
    mime_type: Optional[str] = None
    highlight: Optional[str] = None
    score: float


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.get("", response_model=SearchResponse)
def search_documents(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
):
    """Search the current user's documents by full-text content and filename.

    Uses the per-tenant OpenSearch index.  If the tenant index does not exist
    yet (the user never uploaded anything), an empty result set is returned.
    """
    client = _get_client()
    index_name = _get_index_name(user.id)

    # If the tenant index doesn't exist, return empty results.
    if not client.indices.exists(index=index_name):
        return SearchResponse(results=[], total=0)

    body = {
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": q,
                            "fields": ["text", "filename^2"],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                        }
                    },
                    {
                        "wildcard": {
                            "filename.keyword": {
                                "value": f"*{q}*",
                                "case_insensitive": True,
                                "boost": 2.0
                            }
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        },
        "highlight": {
            "fields": {
                "text": {
                    "fragment_size": 200,
                    "number_of_fragments": 1,
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                },
                "filename": {
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                },
            }
        },
        "from": offset,
        "size": limit,
    }

    try:
        resp = client.search(index=index_name, body=body)
    except OSNotFoundError:
        return SearchResponse(results=[], total=0)
    except Exception as e:
        logger.error("OpenSearch query failed: %s", e)
        return SearchResponse(results=[], total=0)

    hits = resp.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    results: list[SearchResult] = []

    for hit in hits.get("hits", []):
        source = hit["_source"]
        highlight_parts = hit.get("highlight", {})

        # Prefer text highlight, fall back to filename highlight
        highlight = None
        if "text" in highlight_parts:
            highlight = highlight_parts["text"][0]
        elif "filename" in highlight_parts:
            highlight = highlight_parts["filename"][0]

        folder_id_raw = source.get("folder_id")
        try:
            folder_id = UUID(folder_id_raw) if folder_id_raw else None
        except (ValueError, TypeError):
            folder_id = None

        results.append(SearchResult(
            document_id=UUID(source["document_id"]),
            filename=source.get("filename", ""),
            folder_id=folder_id,
            mime_type=source.get("mime_type"),
            highlight=highlight,
            score=hit["_score"],
        ))

    return SearchResponse(results=results, total=total)


# ── Utility for de-indexing ─────────────────────────────────────────────────

def delete_from_index(owner_id, document_id) -> None:
    """Remove a document from the tenant's OpenSearch index.

    Called by the documents router when a document is deleted.
    Silently ignores missing documents / indices.
    """
    client = _get_client()
    index_name = _get_index_name(owner_id)
    try:
        client.delete(index=index_name, id=str(document_id))
        logger.info("Removed doc %s from index %s", document_id, index_name)
    except OSNotFoundError:
        pass
    except Exception as e:
        logger.warning("Failed to de-index doc %s: %s", document_id, e)
