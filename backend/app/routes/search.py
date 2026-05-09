"""Full-text search endpoint powered by OpenSearch (per-tenant index)."""

from __future__ import annotations

import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from opensearchpy import OpenSearch, NotFoundError as OSNotFoundError
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Folder, User

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


# ── Embedding helpers ───────────────────────────────────────────────────────

_embed_model: Optional[SentenceTransformer] = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model '%s'", settings.embedding_model_name)
        _embed_model = SentenceTransformer(settings.embedding_model_name)
    return _embed_model


def _embed_query(text: str) -> Optional[List[float]]:
    if not text:
        return None
    try:
        snippet = text[: settings.embedding_max_chars]
        vector = _get_embed_model().encode(snippet, normalize_embeddings=True)
        return vector.tolist()
    except Exception as e:
        logger.warning("Query embedding failed: %s", e)
        return None


# ── Response schemas ────────────────────────────────────────────────────────

class FolderPathItem(BaseModel):
    id: UUID
    name: str


class SearchResult(BaseModel):
    type: str  # "document" | "folder"
    id: UUID
    name: str
    folder_id: Optional[UUID] = None
    path: List[FolderPathItem] = []
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
    db: Session = Depends(get_db),
):
    """Search the current user's documents (full-text via OpenSearch) and
    folders (name match via Postgres).  Each result includes the folder path
    chain so the UI can display location and offer "open parent folder".
    """
    results: List[SearchResult] = []
    folder_cache: Dict[UUID, Optional[Folder]] = {}

    def _get_folder(folder_id: Optional[UUID]) -> Optional[Folder]:
        if folder_id is None:
            return None
        if folder_id in folder_cache:
            return folder_cache[folder_id]
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        folder_cache[folder_id] = folder
        return folder

    def _build_path(folder_id: Optional[UUID]) -> List[FolderPathItem]:
        """Path chain from the root down to and including ``folder_id``.

        Returns an empty list when ``folder_id`` is None (i.e. the item lives
        at the drive root).
        """
        chain: List[FolderPathItem] = []
        current_id = folder_id
        while current_id is not None:
            folder = _get_folder(current_id)
            if folder is None:
                break
            chain.insert(0, FolderPathItem(id=folder.id, name=folder.name))
            current_id = folder.parent_id
        return chain

    # ── 1) Folder name matches (Postgres, case-insensitive contains) ──
    folder_matches = (
        db.query(Folder)
        .filter(Folder.owner_id == user.id, Folder.name.ilike(f"%{q}%"))
        .order_by(Folder.name)
        .limit(limit)
        .all()
    )

    for folder in folder_matches:
        folder_cache[folder.id] = folder
        # path = ancestors of this folder (excluding the folder itself)
        path = _build_path(folder.parent_id)
        results.append(SearchResult(
            type="folder",
            id=folder.id,
            name=folder.name,
            folder_id=folder.parent_id,
            path=path,
            mime_type=None,
            highlight=None,
            score=1.0,
        ))

    # ── 2) Document full-text matches (OpenSearch) ────────────────────
    client = _get_client()
    index_name = _get_index_name(user.id)

    if client.indices.exists(index=index_name):
        should_clauses = [
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
                        "boost": 2.0,
                    }
                }
            },
        ]

        query_vector = _embed_query(q)
        if query_vector is not None:
            should_clauses.append({
                "knn": {
                    "embedding": {
                        "vector": query_vector,
                        "k": settings.knn_candidates,
                    }
                }
            })

        body = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1,
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
            resp = None
        except Exception as e:
            logger.error("OpenSearch query failed: %s", e)
            resp = None

        if resp is not None:
            hits = resp.get("hits", {})
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

                path = _build_path(folder_id)

                results.append(SearchResult(
                    type="document",
                    id=UUID(source["document_id"]),
                    name=source.get("filename", ""),
                    folder_id=folder_id,
                    path=path,
                    mime_type=source.get("mime_type"),
                    highlight=highlight,
                    score=hit["_score"],
                ))

    return SearchResponse(results=results, total=len(results))


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
