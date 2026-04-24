"""
MCP server that exposes the DMS folder/document structure as tools.

Connects directly to PostgreSQL (internal service — no JWT required).
Intended to be used by the agent_worker via CrewAI MCPServerAdapter.

Available tools:
  - list_folders(user_id, parent_id?)  → root or sub-folders for a user
  - list_documents(user_id, folder_id?) → documents in a folder (or root)
  - get_folder(user_id, folder_id)      → details of a single folder
"""

import logging
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from config import settings
from database import SessionLocal
from models import Document, Folder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mcp_server")

mcp = FastMCP("dms-mcp-server", host=settings.host, port=settings.port)


@mcp.tool()
def list_folders(user_id: str, parent_id: str | None = None) -> list[dict]:
    """
    List folders owned by user_id.
    If parent_id is provided, returns subfolders of that folder.
    If parent_id is None, returns root-level folders.
    """
    db = SessionLocal()
    try:
        query = db.query(Folder).filter(Folder.owner_id == UUID(user_id))
        if parent_id:
            query = query.filter(Folder.parent_id == UUID(parent_id))
        else:
            query = query.filter(Folder.parent_id.is_(None))

        folders = query.order_by(Folder.name).all()
        logger.info("list_folders user=%s parent=%s → %d results", user_id, parent_id, len(folders))
        return [
            {
                "id": str(f.id),
                "name": f.name,
                "parent_id": str(f.parent_id) if f.parent_id else None,
            }
            for f in folders
        ]
    finally:
        db.close()


@mcp.tool()
def list_documents(user_id: str, folder_id: str | None = None) -> list[dict]:
    """
    List documents owned by user_id inside folder_id.
    If folder_id is None, returns documents at root level (not in any folder).
    """
    db = SessionLocal()
    try:
        query = db.query(Document).filter(Document.owner_id == UUID(user_id))
        if folder_id:
            query = query.filter(Document.folder_id == UUID(folder_id))
        else:
            query = query.filter(Document.folder_id.is_(None))

        docs = query.order_by(Document.name).all()
        logger.info("list_documents user=%s folder=%s → %d results", user_id, folder_id, len(docs))
        return [
            {
                "id": str(d.id),
                "name": d.name,
                "mime_type": d.mime_type,
                "size_bytes": d.size_bytes,
                "folder_id": str(d.folder_id) if d.folder_id else None,
            }
            for d in docs
        ]
    finally:
        db.close()


@mcp.tool()
def get_folder(user_id: str, folder_id: str) -> dict:
    """
    Get details of a specific folder. Returns an error dict if not found or not owned by user.
    """
    db = SessionLocal()
    try:
        folder = (
            db.query(Folder)
            .filter(Folder.id == UUID(folder_id), Folder.owner_id == UUID(user_id))
            .first()
        )
        if not folder:
            return {"error": "Folder not found or access denied"}

        return {
            "id": str(folder.id),
            "name": folder.name,
            "parent_id": str(folder.parent_id) if folder.parent_id else None,
        }
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting MCP server on %s:%d", settings.host, settings.port)
    mcp.run(transport="sse")
