#!/usr/bin/env python3
"""
Simple script to start the command center server for testing.
"""

import os
import sys

# Add the services/command-center to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "command-center"))

import uvicorn
from main import app

if __name__ == "__main__":
    print("Starting AetherLink Command Center...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
