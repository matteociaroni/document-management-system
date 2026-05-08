"""
Atomic Agents implementation for classifying email attachments into DMS folders.

Flow:
  1. MCPClient fetches the full folder tree from the mcp_server (pre-fetch approach).
  2. The folder tree is injected as context into the agent's system prompt.
  3. The agent receives the email info + attachment list and produces a structured
     FilingOutput (one AttachmentDecision per attachment).

Uses instructor + OpenAI-compatible client so it works with any LiteLLM-proxied model.
"""

import logging

import instructor
from atomic_agents.agents.atomic_agent import AgentConfig, AtomicAgent
from atomic_agents.base.base_io_schema import BaseIOSchema
from atomic_agents.context.system_prompt_generator import (
    BaseDynamicContextProvider,
    SystemPromptGenerator,
)
from openai import OpenAI
from pydantic import BaseModel, Field

from config import settings
from mcp_client import MCPClient

logger = logging.getLogger(__name__)


# --- Schemas ---

class AttachmentInfo(BaseIOSchema):
    """Info about a single email attachment."""
    filename: str = Field(..., description="Name of the file")
    mime_type: str = Field(..., description="MIME type of the file")
    size_bytes: int = Field(..., description="File size in bytes")
    text_preview: str | None = Field(
        None,
        description=(
            "Extracted text content of the attachment. "
            "Text files: the first ~500 chars. "
            "PDFs: text from the first and last pages (separated by '[...]'). "
            "DOCX: head and tail of the concatenated paragraph text. "
            "XLSX: tab-separated rows from the first sheets, prefixed by '[Sheet: <name>]'. "
            "Empty/None for unsupported formats or scanned/image-only PDFs."
        ),
    )


class AttachmentDecision(BaseModel):
    filename: str = Field(..., description="Exact filename as provided in input")
    folder_id: str | None = Field(..., description="UUID of target folder from the tree, or null if no match")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Brief explanation of the filing decision")


class FilingInput(BaseIOSchema):
    """Input for the document filing agent.

    The 'context_*' fields describe where the files come from. For email-derived
    flows they carry subject/sender/body; for direct user uploads they may
    contain just the filename and a placeholder source.
    """
    context_title: str = Field(
        ...,
        description="Short title describing the documents (email subject, or filename for manual uploads)",
    )
    context_source: str = Field(
        ...,
        description="Origin of the documents (sender address, or '(manual upload)' for user-driven uploads)",
    )
    context_description: str | None = Field(
        None,
        description="Optional extended description (email body text, truncated to ~2000 chars). May be null when no narrative is available.",
    )
    attachments: list[AttachmentInfo] = Field(..., description="List of files to classify")


class FilingOutput(BaseIOSchema):
    """Structured filing decisions — one per attachment."""
    decisions: list[AttachmentDecision] = Field(..., description="One decision per attachment")


# --- Context provider ---

class FolderTreeContextProvider(BaseDynamicContextProvider):
    """Injects the pre-fetched folder tree into the system prompt."""

    def __init__(self, folder_tree: str):
        super().__init__(title="Available Folders")
        self.folder_tree = folder_tree

    def get_info(self) -> str:
        if not self.folder_tree:
            return "(no folders found — set folder_id to null for all attachments)"
        return self.folder_tree


# --- Agent factory ---

def _build_instructor_client() -> instructor.Instructor:
    openai_client = OpenAI(
        api_key=settings.custom_api_key or "no-key",
        base_url=settings.base_url or None,
    )
    return instructor.from_openai(openai_client)


def run_filing_agent(
    user_id: str,
    context_title: str,
    context_source: str,
    attachments: list[dict],
    context_description: str | None = None,
) -> FilingOutput:
    """
    Classify a batch of files into DMS folders using Atomic Agents.

    The same agent powers two flows: inbound email attachments and direct
    user uploads. The caller adapts whatever metadata is available to the
    generic ``context_*`` fields.

    Args:
        user_id: UUID of the user who owns the target folder tree.
        context_title: Short title for the batch (email subject, or filename
            for manual uploads).
        context_source: Origin of the files (sender address, or
            '(manual upload)' for user-driven uploads).
        attachments: List of dicts with keys: filename, mime_type, size_bytes,
            text_preview.
        context_description: Optional extended description (email body, etc.),
            truncated to ~2000 chars by the caller. May be None.

    Returns:
        FilingOutput with one AttachmentDecision per attachment.
    """
    # 1. Fetch folder structure via MCP
    mcp = MCPClient(settings.mcp_server_url)
    folder_tree = mcp.build_folder_tree(user_id)
    logger.info("Fetched folder tree for user %s:\n%s", user_id, folder_tree or "(empty)")

    # 2. Build system prompt with folder tree injected as context
    system_prompt = SystemPromptGenerator(
        background=[
            "You are an expert document archivist for a Document Management System (DMS).",
            "Your task is to classify a batch of files and assign each one to the most appropriate folder.",
            "Files may arrive from different sources: an inbound email (with subject, sender, and body), "
            "or a direct upload by the user (with only a filename as context).",
            "The available folder structure is provided in the context below.",
        ],
        steps=[
            "Read the context_title, context_source, and context_description to understand the document "
            "category and the situation in which the files were submitted.",
            "When a context_description is present (typically an email body), it usually states what the "
            "files are about (e.g. 'please find the invoice attached'); rely on it heavily.",
            "When the context is minimal (e.g. a manual upload with no description), give more weight to "
            "the filename and to the text_preview extracted from the file.",
            "For each file, analyze its filename, MIME type, size, and any text preview.",
            "Combine the available context with the file metadata to match each file to the most "
            "semantically appropriate folder from the tree.",
            "If no folder is a good match, set folder_id to null.",
            "Set confidence to 1.0 only if you are certain. Use lower values for ambiguous cases — "
            "in particular, lower the confidence when only a filename is available and it is generic.",
        ],
        output_instructions=[
            "Return exactly one decision per file in the 'decisions' list.",
            "Use the exact filename as provided — do not modify it.",
            "folder_id must be a valid UUID string copied from the folder tree, or null.",
            "confidence must be a float between 0.0 and 1.0.",
        ],
        context_providers={"folders": FolderTreeContextProvider(folder_tree)},
    )

    config = AgentConfig(
        client=_build_instructor_client(),
        model=settings.model_name,
        system_prompt_generator=system_prompt,
    )

    agent = AtomicAgent[FilingInput, FilingOutput](config)

    # 3. Run the agent
    result: FilingOutput = agent.run(
        FilingInput(
            context_title=context_title,
            context_source=context_source,
            context_description=context_description,
            attachments=[
                AttachmentInfo(
                    filename=a["filename"],
                    mime_type=a["mime_type"],
                    size_bytes=a["size_bytes"],
                    text_preview=a.get("text_preview"),
                )
                for a in attachments
            ],
        )
    )

    logger.info("Agent produced %d decision(s)", len(result.decisions))
    return result
