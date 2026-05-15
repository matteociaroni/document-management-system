import json
import logging
import time
import hashlib
from collections import OrderedDict
from typing import Any, Dict
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from pydantic import BaseModel

from mcp.client.sse import sse_client
from mcp import ClientSession

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_agent")

class LogDeduplicator:
    def __init__(self, ttl_seconds: int = 900, max_size: int = 1000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache = OrderedDict()

    def is_duplicate(self, key: str) -> bool:
        now = time.time()
        
        # Prune expired (simple approach)
        expired = [k for k, v in self.cache.items() if now - v > self.ttl]
        for k in expired:
            del self.cache[k]

        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = now
            return True
            
        self.cache[key] = now
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
        return False

deduplicator = LogDeduplicator(ttl_seconds=900)  # 15 minutes cooldown

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
    severity = analysis_result.get("severity", "HIGH")
    
    logger.info(f"Analysis complete (Severity: {severity}). Calling send_telegram_alert...")
    
    # 2. Send Telegram alert
    alert_result = await call_mcp_tool(
        url=mcp_url,
        tool_name="send_telegram_alert",
        arguments={
            "log_text": log_text,
            "cause": cause,
            "solution": solution,
            "severity": severity
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
        
        def handle_log(log_item):
            # Check if this is a Kubernetes Event
            if isinstance(log_item, dict) and "involvedObject" in log_item and "reason" in log_item:
                event_type = log_item.get("type", "Normal")
                reason = log_item.get("reason", "Unknown")
                message = log_item.get("message", "")
                involved = log_item.get("involvedObject", {})
                kind = involved.get("kind", "Unknown")
                name = involved.get("name", "Unknown")
                
                # Filter events: we only want Warnings, or specific Normal events like Killing/Evicted
                if event_type == "Warning" or reason in ["Killing", "Evicted", "OOMKilling", "Failed", "BackOff"]:
                    dedup_key = hashlib.md5(f"event:{reason}:{name}".encode()).hexdigest()
                    if not deduplicator.is_duplicate(dedup_key):
                        logger.info(f"New K8s Event detected (key: {dedup_key}). Sending directly to Telegram.")
                        mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/sse"
                        severity = "MEDIUM" if event_type == "Warning" else "LOW"
                        if reason in ["OOMKilling", "Failed", "BackOff"]:
                            severity = "HIGH"
                            
                        background_tasks.add_task(
                            call_mcp_tool,
                            url=mcp_url,
                            tool_name="send_telegram_alert",
                            arguments={
                                "log_text": f"Event: {reason} on {kind}/{name}\n{message}",
                                "cause": f"Kubernetes Event ({event_type})",
                                "solution": "N/A - System Event",
                                "severity": severity
                            }
                        )
                return

            # Extract log text for standard container logs
            log_text = log_item.get("log") if isinstance(log_item, dict) else str(log_item)
            if not log_text:
                return
            
            def should_process_log(pod: str, text: str) -> bool:
                text_lower = text.lower()
                pod_lower = pod.lower()
                
                # 1. Only process error, panic, fatal (drop WARN)
                if not any(k in text_lower for k in ["error", "panic", "fatal", "exception"]):
                    return False
                    
                # 2. Exclude noisy pods (tika, opensearch) unless it's a fatal/panic
                is_fatal = "panic" in text_lower or "fatal" in text_lower or "oomkilled" in text_lower
                if "tika" in pod_lower or "opensearch" in pod_lower:
                    if not is_fatal:
                        return False
                        
                # 3. Exclude Traefik/Ingress client-side network errors
                if "traefik" in pod_lower or "ingress" in pod_lower:
                    client_errors = [
                        "404 not found", "400 bad request", "eof", 
                        "connection reset by peer", "client closed connection",
                        "broken pipe", "request canceled"
                    ]
                    if any(c_err in text_lower for c_err in client_errors):
                        return False
                        
                return True

            pod_name = log_item.get("kubernetes", {}).get("pod_name", "") if isinstance(log_item, dict) else ""
            
            if should_process_log(pod_name, log_text):
                # Create a unique hash for the log to deduplicate
                # We hash the pod name and the first 200 chars of the log (usually enough to identify the error without timestamps)
                dedup_key = hashlib.md5(f"{pod_name}:{log_text[:200]}".encode()).hexdigest()
                
                if not deduplicator.is_duplicate(dedup_key):
                    logger.info(f"New unique log detected (key: {dedup_key}). Queuing for analysis.")
                    background_tasks.add_task(process_log, log_text)
                else:
                    logger.debug(f"Skipping duplicate log (key: {dedup_key}).")

        # Fluent Bit sends lists of dicts
        if isinstance(data, list):
            for item in data:
                handle_log(item)
        else:
            handle_log(data)
            
        return {"status": "ok", "message": "Logs processed"}
    except Exception as e:
        logger.error(f"Failed to process incoming webhook: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    uvicorn.run("webhook_agent:app", host="0.0.0.0", port=8000, reload=False)
