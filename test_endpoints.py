import os
import subprocess
import sys
import time

import requests

# Start server in background
print("Starting server...")
server = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "services.command-center.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--log-level",
        "info",
    ],
    cwd="c:/Users/jonmi/OneDrive/Documents/AetherLink",
    env={**os.environ, "PYTHONPATH": "."},
)

# Wait for server to start
time.sleep(3)

# Test endpoints
endpoints = [
    "/ops/ping",
    "/ops/health",
    "/api/crm/import/acculynx/schedule/status",
    "/api/local/runs",
]

for endpoint in endpoints:
    try:
        url = f"http://127.0.0.1:8000{endpoint}"
        print(f"Testing {url}...")
        response = requests.get(url, timeout=5)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}...")
    except Exception as e:
        print(f"  Error: {e}")

# Check if server is still running
if server.poll() is None:
    print("Server is still running")
    server.terminate()
else:
    print("Server exited with code:", server.returncode)
