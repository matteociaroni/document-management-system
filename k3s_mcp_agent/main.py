import subprocess
import sys
import time

def main():
    print("Starting MCP Server...")
    mcp_process = subprocess.Popen([sys.executable, "mcp_server.py"])
    
    # Wait a moment for MCP server to start
    time.sleep(2)
    
    print("Starting Webhook Agent...")
    webhook_process = subprocess.Popen([sys.executable, "webhook_agent.py"])
    
    try:
        mcp_process.wait()
        webhook_process.wait()
    except KeyboardInterrupt:
        print("Stopping services...")
        mcp_process.terminate()
        webhook_process.terminate()

if __name__ == "__main__":
    main()
