"""
Synchronous MCP client wrapper.

Connects to the mcp_server via SSE and exposes tool calls as regular
Python methods. Uses asyncio.run() internally since the worker is sync.
"""

import asyncio
import json
import logging

from mcp.client.sse import sse_client
from mcp import ClientSession

logger = logging.getLogger(__name__)


async def _call_tool(url: str, tool_name: str, arguments: dict):
    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if not result.content:
                return []

            text = result.content[0].text
            logger.debug("MCP raw response for %s: %r", tool_name, text)
            parsed = json.loads(text)

            # FastMCP sometimes double-encodes: the text is a JSON string
            # whose value is itself a JSON array/object
            if isinstance(parsed, str):
                parsed = json.loads(parsed)

            # FastMCP may put each dict item in a separate content block
            if isinstance(parsed, dict):
                return [json.loads(c.text) for c in result.content]

            return parsed


class MCPClient:
    def __init__(self, url: str):
        self.url = url

    def _call(self, tool_name: str, arguments: dict):
        return asyncio.run(_call_tool(self.url, tool_name, arguments))

    def list_folders(self, user_id: str, parent_id: str | None = None) -> list[dict]:
        args = {"user_id": user_id}
        if parent_id:
            args["parent_id"] = parent_id
        return self._call("list_folders", args)

    def list_documents(self, user_id: str, folder_id: str | None = None) -> list[dict]:
        args = {"user_id": user_id}
        if folder_id:
            args["folder_id"] = folder_id
        return self._call("list_documents", args)

    def build_folder_tree(self, user_id: str, parent_id: str | None = None, indent: int = 0) -> str:
        """Recursively build a text representation of the folder tree with IDs."""
        folders = self.list_folders(user_id, parent_id)
        if not folders:
            return ""
        lines = []
        for folder in folders:
            prefix = "  " * indent
            lines.append(f"{prefix}- {folder['name']}  [id: {folder['id']}]")
            subtree = self.build_folder_tree(user_id, folder["id"], indent + 1)
            if subtree:
                lines.append(subtree)
        return "\n".join(lines)
