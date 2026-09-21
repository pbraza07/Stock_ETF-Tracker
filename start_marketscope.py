"""Production entrypoint: resource limits apply before Streamlit/NumPy imports."""
import os
import sys
from production_runtime import configure

def command():
    return [sys.executable,'-m','streamlit','run','app.py',
            '--server.address=0.0.0.0',f'--server.port={os.environ.get("PORT","8501")}',
            '--server.headless=true','--browser.gatherUsageStats=false',
            '--server.runOnSave=false','--server.fileWatcherType=none',
            '--server.disconnectedSessionTTL=1800','--server.websocketPingInterval=30']

if __name__=='__main__':
    threads=configure()
    print(f'MarketScope production startup: numeric_threads={threads}; disconnected_session_ttl=1800s; file_watcher=none',flush=True)
    os.execv(sys.executable,command())
