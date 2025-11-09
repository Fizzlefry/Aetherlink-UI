#!/usr/bin/env python3
"""
Sample AccuLynx data importer for AetherLink CRM.

This script demonstrates how to import data from AccuLynx into AetherLink CRM.
Run this to populate your CRM with sample data for testing.
"""

import json
import requests
import time
import subprocess
import sys
import os

# Sample AccuLynx data - replace with your actual export
SAMPLE_ACCULYNX_DATA = {
    "vertical": "peakpro",
    "jobs": [
        {
            "JobId": "AX-1001",
            "JobName": "123 Main St Roof",
            "Status": "Active",
            "SalesRep": "Beth L",
            "NextAction": "Call homeowner",
        }
    ],
    "contacts": [
        {
            "ContactId": "AC-555",
            "Name": "Homeowner Jones",
            "Email": "homeowner@example.com",
            "Phone": "555-0101",
        }
    ],
    "files": [
        {
            "FileId": "F-777",
            "Name": "Estimate.pdf",
            "Url": "https://example.com/estimate.pdf",
            "JobId": "AX-1001",
        }
    ],
}

def check_server_running():
    """Check if the Command Center server is running."""
    try:
        response = requests.get("http://localhost:8000/test", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the Command Center server."""
    print("🚀 Starting Command Center server...")
    server_dir = os.path.join(os.path.dirname(__file__), "..", "services", "command-center")
    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]
    
    # Start server in background
    process = subprocess.Popen(cmd, cwd=server_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    for i in range(10):
        time.sleep(1)
        if check_server_running():
            print("✅ Server started successfully")
            return process
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"❌ Server failed to start: {stderr.decode()}")
            return None
    
    print("❌ Server didn't respond within 10 seconds")
    return None

def import_acculynx_data():
    """Import sample AccuLynx data into AetherLink CRM."""

    # Check if server is running, start if not
    if not check_server_running():
        server_process = start_server()
        if not server_process:
            print("❌ Failed to start server. Exiting.")
            return
    else:
        server_process = None
        print("✅ Server already running")

    # Command Center URL - adjust if running on different port
    url = "http://localhost:8000/api/crm/import/acculynx"

    headers = {
        "Content-Type": "application/json",
        "x-tenant": "the-expert-co"
    }

    print("🚀 Importing AccuLynx data into AetherLink CRM...")
    print(f"📊 Data to import:")
    print(f"   • {len(SAMPLE_ACCULYNX_DATA['jobs'])} jobs")
    print(f"   • {len(SAMPLE_ACCULYNX_DATA['contacts'])} contacts")
    print(f"   • {len(SAMPLE_ACCULYNX_DATA['files'])} files")
    print()

    try:
        response = requests.post(url, headers=headers, json=SAMPLE_ACCULYNX_DATA, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print("✅ Import successful!")
            stats = result['stats']
            print(f"� Stats: {stats['records_created']} records created, {stats['records_updated']} updated")
            print(f"   {stats['customers_created']} customers created, {stats['customers_updated']} updated")
            print(f"   {stats['files_created']} files created, {stats['files_updated']} updated")
            print()
            print("🎯 Next steps:")
            print("   1. Open http://localhost/ in your browser")
            print("   2. Navigate to PeakPro CRM")
            print("   3. You should see the imported jobs with 'From AccuLynx' badges")
            print("   4. Click on a job to see attached files")
        else:
            print(f"❌ Import failed with status {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is Command Center running on http://localhost:8000?")
        print("   Try: cd services/command-center && $env:PYTHONPATH = 'services/command-center'; python -m uvicorn services.command-center.main:app --host 127.0.0.1 --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    import_acculynx_data()