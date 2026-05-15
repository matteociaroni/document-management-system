import json
import logging
from typing import Any, Dict
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from pydantic import BaseModel

from mcp.client.sse import sse_client
from mcp import ClientSession

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_agent")

app = FastAPI(title="K3s Log Webhook Agent")

async def call_mcp_tool(url: str, tool_name: str, arguments: dict) -> Any:
    """Async helper to call an MCP tool."""
    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if not result.content:
                    return None
                text = result.content[0].text
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, str):
                        parsed = json.loads(parsed)
                    return parsed
                except json.JSONDecodeError:
                    return text
    except Exception as e:
        logger.error(f"Error calling MCP tool {tool_name}: {e}")
        return None

async def process_log(log_text: str):
    """Background task to analyze log and send to Telegram via MCP tools."""
    logger.info("Processing log entry...")
    mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/sse"
    
    # 1. Analyze the log
    logger.info("Calling analyze_k3s_log...")
    analysis_result = await call_mcp_tool(
        url=mcp_url,
        tool_name="analyze_k3s_log",
        arguments={"log_text": log_text}
    )
    
    if not analysis_result or not isinstance(analysis_result, dict):
        logger.error(f"Failed to get valid analysis result: {analysis_result}")
        return
        
    cause = analysis_result.get("cause", "Unknown Cause")
    solution = analysis_result.get("solution", "No solution provided")
    
    logger.info("Analysis complete. Calling send_telegram_alert...")
    
    # 2. Send Telegram alert
    alert_result = await call_mcp_tool(
        url=mcp_url,
        tool_name="send_telegram_alert",
        arguments={
            "log_text": log_text,
            "cause": cause,
            "solution": solution
        }
    )
    logger.info(f"Telegram alert result: {alert_result}")


@app.post("/logs")
async def receive_logs(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint to receive logs.
    Fluent Bit typically sends arrays of JSON objects or just raw JSON.
    """
    try:
        data = await request.json()
        
        # Fluent Bit sends lists of dicts
        if isinstance(data, list):
            for item in data:
                log_text = item.get("log") or item.get("message") or str(item)
                # Quick check if it's actually an error (in case filter didn't catch it)
                if isinstance(log_text, str) and ("error" in log_text.lower() or "warn" in log_text.lower()):
                    background_tasks.add_task(process_log, log_text)
        elif isinstance(data, dict):
            log_text = data.get("log") or data.get("message") or str(data)
            background_tasks.add_task(process_log, log_text)
        else:
            background_tasks.add_task(process_log, str(data))
            
        return {"status": "ok", "message": "Logs queued for processing"}
    except Exception as e:
        logger.error(f"Failed to process incoming webhook: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    uvicorn.run("webhook_agent:app", host="0.0.0.0", port=8000, reload=False)
