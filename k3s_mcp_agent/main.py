import subprocess
import sys
import time
import threading

def main():
    print("Starting MCP Server...")
    mcp_process = subprocess.Popen([sys.executable, "mcp_server.py"])

    time.sleep(2)

    print("Starting Webhook Agent...")
    webhook_process = subprocess.Popen([sys.executable, "webhook_agent.py"])

    def _watch(primary, other):
        primary.wait()
        print(f"Process {primary.args} exited (code {primary.returncode}). Terminating companion...")
        other.terminate()

    t1 = threading.Thread(target=_watch, args=(mcp_process, webhook_process), daemon=True)
    t2 = threading.Thread(target=_watch, args=(webhook_process, mcp_process), daemon=True)
    t1.start()
    t2.start()

    try:
        mcp_process.wait()
        webhook_process.wait()
    except KeyboardInterrupt:
        print("Stopping services...")
        mcp_process.terminate()
        webhook_process.terminate()

if __name__ == "__main__":
    main()
