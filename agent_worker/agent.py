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
    text_preview: str | None = Field(None, description="First 500 chars of content (text files only)")


class AttachmentDecision(BaseModel):
    filename: str = Field(..., description="Exact filename as provided in input")
    folder_id: str | None = Field(..., description="UUID of target folder from the tree, or null if no match")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Brief explanation of the filing decision")


class FilingInput(BaseIOSchema):
    """Input for the document filing agent."""
    email_subject: str = Field(..., description="Subject line of the email")
    email_sender: str = Field(..., description="Sender address")
    attachments: list[AttachmentInfo] = Field(..., description="List of attachments to classify")


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
    email_subject: str,
    email_sender: str,
    attachments: list[dict],
) -> FilingOutput:
    """
    Classify email attachments into DMS folders using Atomic Agents.

    Args:
        user_id: UUID of the user who owns the email account.
        email_subject: Subject line of the email.
        email_sender: Sender address.
        attachments: List of dicts with keys: filename, mime_type, size_bytes, text_preview.

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
            "Your task is to classify email attachments and assign each one to the most appropriate folder.",
            "The available folder structure is provided in the context below.",
        ],
        steps=[
            "Read the email subject and sender to understand the document category.",
            "For each attachment, analyze its filename, MIME type, size, and any text preview.",
            "Match each attachment to the most semantically appropriate folder from the tree.",
            "If no folder is a good match, set folder_id to null.",
            "Set confidence to 1.0 only if you are certain. Use lower values for ambiguous cases.",
        ],
        output_instructions=[
            "Return exactly one decision per attachment in the 'decisions' list.",
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
            email_subject=email_subject,
            email_sender=email_sender,
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
