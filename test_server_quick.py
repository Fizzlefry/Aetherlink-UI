#!/usr/bin/env python3
"""
Quick server test
"""

import os
import subprocess
import sys
import time

import requests


def test_server():
    # Set environment
    env = os.environ.copy()
    env["PYTHONPATH"] = r"c:\Users\jonmi\OneDrive\Documents\AetherLink"

    # Start server
    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.path.insert(0, 'services/command-center'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, log_level='info')",
    ]

    print("Starting server...")
    proc = subprocess.Popen(cmd, cwd=r"c:\Users\jonmi\OneDrive\Documents\AetherLink", env=env)

    try:
        # Wait for startup
        time.sleep(5)

        # Test health
        print("Testing health endpoint...")
        r = requests.get("http://localhost:8000/ops/health", timeout=5)
        print(f"Status: {r.status_code}")
        print(r.json())
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)
