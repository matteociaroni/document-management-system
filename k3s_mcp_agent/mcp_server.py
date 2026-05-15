import logging
import requests
from openai import OpenAI
from pydantic import BaseModel, Field
import instructor
from mcp.server.fastmcp import FastMCP

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("k3s_mcp_server")

mcp = FastMCP("k3s-mcp-server", host=settings.mcp_host, port=settings.mcp_port)

from enum import Enum

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class LogAnalysisResult(BaseModel):
    severity: Severity = Field(..., description="The severity level of the issue.")
    cause: str = Field(..., description="The root cause of the error found in the log.")
    solution: str = Field(..., description="A proposed solution or actionable step to fix the error.")

def _get_llm_client():
    client = OpenAI(
        api_key=settings.custom_api_key or "no-key",
        base_url=settings.base_url or None,
    )
    return instructor.from_openai(client)

@mcp.tool()
def analyze_k3s_log(log_text: str) -> dict:
    """
    Analyze a K3s or Kubernetes log entry to determine the root cause and propose a solution.
    Returns a dictionary with 'cause' and 'solution'.
    """
    logger.info("Analyzing K3s log: %s", log_text[:100] + "...")
    client = _get_llm_client()
    
    try:
        result = client.chat.completions.create(
            model=settings.model_name,
            response_model=LogAnalysisResult,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Kubernetes and DevOps engineer. "
                               "Analyze the provided log line, identify the technical root cause, "
                               "and suggest a concrete solution to resolve the issue."
                },
                {
                    "role": "user",
                    "content": log_text
                }
            ],
        )
        return {
            "severity": result.severity.value,
            "cause": result.cause,
            "solution": result.solution
        }
    except Exception as e:
        logger.error(f"Error analyzing log: {e}")
        return {
            "severity": "CRITICAL",
            "cause": "Failed to analyze log due to LLM error.",
            "solution": str(e)
        }

@mcp.tool()
def send_telegram_alert(log_text: str, cause: str, solution: str, severity: str = "HIGH") -> str:
    """
    Send an alert to the configured Telegram bot containing the log, cause, and solution.
    Returns a success or error message.
    """
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials not configured.")
        return "Error: Telegram credentials not configured."
        
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    
    emoji_map = {
        "LOW": "🔵",
        "MEDIUM": "🟡",
        "HIGH": "🟠",
        "CRITICAL": "🔴"
    }
    emoji = emoji_map.get(severity.upper(), "🚨")
    
    message = (
        f"{emoji} <b>K3s Alert - Severity: {severity.upper()}</b> {emoji}\n\n"
        f"<b>Log:</b>\n<pre>{log_text[:500]}</pre>\n\n"
        f"<b>Cause:</b>\n{cause}\n\n"
        f"<b>Solution:</b>\n{solution}"
    )
    
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram alert sent successfully.")
        return "Success: Alert sent to Telegram."
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return f"Error: Failed to send Telegram alert: {e}"

if __name__ == "__main__":
    logger.info("Starting K3s MCP Server on %s:%d", settings.mcp_host, settings.mcp_port)
    mcp.run(transport="sse")
