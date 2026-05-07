"""
Standalone test for the Atomic Agents filing agent.

Bypasses the worker loop and DB entirely — just calls run_filing_agent directly
with hardcoded data so you can verify the agent + MCP tools work correctly.

Requirements:
  - mcp_server container must be running (docker compose up mcp_server)
  - PostgreSQL must be running with at least one user and some folders
  - Set USER_ID to a valid user UUID from your DB

Run:
  cd agent_worker
  python test_agent.py
"""

import os

# Override settings before importing anything that reads them
os.environ.setdefault("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/dms")
os.environ.setdefault("MODEL_NAME", "openai/geminipro")
os.environ.setdefault("BASE_URL", "https://litellm.darklabs.it")
os.environ.setdefault("CUSTOM_API_KEY", "sk-BI1ty8WHJ-PBrVP5_ElhZA")
os.environ.setdefault("MCP_SERVER_URL", "http://mcp_server:8001/sse")

from agent import run_filing_agent

# --- Configure these before running ---
USER_ID = "8e1a9646-aeff-4575-a49c-736083da09c0"  # replace with a real user UUID from your DB

FAKE_ATTACHMENTS = [
    {
        "filename": "fattura_marzo_2026.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 45231,
        "text_preview": None,
    },
    {
        "filename": "contratto_fornitura.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 128400,
        "text_preview": None,
    },
]

if __name__ == "__main__":
    print("Running filing agent test...")
    print(f"  MCP server: {os.environ['MCP_SERVER_URL']}")
    print(f"  Model:      {os.environ['MODEL_NAME']}")
    print(f"  User ID:    {USER_ID}")
    print()

    result = run_filing_agent(
        user_id=USER_ID,
        email_subject="Documenti amministrativi Marzo 2026",
        email_sender="amministrazione@fornitore.com",
        email_body="Buongiorno, in allegato troverà la fattura relativa al mese di marzo "
                   "e il contratto di fornitura aggiornato. Cordiali saluti.",
        attachments=FAKE_ATTACHMENTS,
    )

    print("\n=== RESULTS ===")
    for decision in result.decisions:
        print(f"\nFile:       {decision.filename}")
        print(f"Folder ID:  {decision.folder_id or '(no match)'}")
        print(f"Confidence: {decision.confidence:.0%}")
        print(f"Reasoning:  {decision.reasoning}")
