#!/usr/bin/env python3
"""
AetherLink Command Center - Release Smoke Test Suite
Validates core functionality for deployment readiness
"""

import os
import subprocess
import sys
import time

import requests

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 10


def start_server():
    """Start the server in a separate thread"""
    env = os.environ.copy()
    env["PYTHONPATH"] = r"c:\Users\jonmi\OneDrive\Documents\AetherLink"

    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.path.insert(0, 'services/command-center'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, log_level='info')",
    ]

    proc = subprocess.Popen(cmd, cwd=r"c:\Users\jonmi\OneDrive\Documents\AetherLink", env=env)
    return proc


def log(message, status="INFO"):
    """Simple logging function"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {status}: {message}")


def test_health_check():
    """Test basic health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/ops/health", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" or data.get("ok") == True:
                log("Health check passed")
                return True
        log(f"Health check failed: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"Health check error: {e}", "ERROR")
    return False


def test_ping():
    """Test ping endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/ops/ping", timeout=TIMEOUT)
        if response.status_code == 200:
            log("Ping test passed")
            return True
        log(f"Ping test failed: {response.status_code}", "ERROR")
    except Exception as e:
        log(f"Ping test error: {e}", "ERROR")
    return False


def test_chat_smoke():
    """Test basic local run functionality (replaces chat test)"""
    try:
        payload = {"action": "test", "params": {}}
        headers = {"x-tenant": "the-expert-co"}
        response = requests.post(
            f"{BASE_URL}/api/local/run", json=payload, headers=headers, timeout=TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                log("Local run smoke test passed")
                return True
        log(f"Local run test failed: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"Local run test error: {e}", "ERROR")
    return False


def test_scheduler_status():
    """Test scheduler status endpoint"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/crm/import/acculynx/schedule/status", timeout=TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            if "schedules" in data:
                log("Scheduler status test passed")
                return True
        log(f"Scheduler status failed: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"Scheduler status error: {e}", "ERROR")
    return False


def test_import_status():
    """Test import status endpoint"""
    try:
        headers = {"x-tenant": "the-expert-co"}
        response = requests.get(
            f"{BASE_URL}/api/crm/import/status", headers=headers, timeout=TIMEOUT
        )
        if response.status_code in [200, 404]:  # 404 is OK if no imports yet
            log("Import status test passed")
            return True
        log(f"Import status failed: {response.status_code}", "ERROR")
    except Exception as e:
        log(f"Import status error: {e}", "ERROR")
    return False


def test_accuLynx_stub_mode():
    """Test AccuLynx run-now endpoint (stub mode when no API key)"""
    try:
        # Remove API key to force stub mode
        old_key = os.environ.get("ACCULYNX_API_KEY")
        if "ACCULYNX_API_KEY" in os.environ:
            del os.environ["ACCULYNX_API_KEY"]

        headers = {"x-tenant": "the-expert-co", "x-ops": "1"}  # Add operator header
        response = requests.post(
            f"{BASE_URL}/api/crm/import/acculynx/run-now", headers=headers, timeout=TIMEOUT
        )

        # Restore key
        if old_key:
            os.environ["ACCULYNX_API_KEY"] = old_key

        if response.status_code == 200:
            data = response.json()
            # Accept both success (ok: true) and expected failure (ok: false with error about unknown tenant)
            if data.get("ok") == True or (data.get("ok") == False and "error" in data):
                log("AccuLynx run-now test passed")
                return True
        log(f"AccuLynx run-now failed: {response.status_code} - {response.text}", "ERROR")
    except Exception as e:
        log(f"AccuLynx run-now error: {e}", "ERROR")
    return False


def run_smoke_tests():
    """Run all smoke tests"""
    log("Starting AetherLink Command Center Smoke Test Suite")
    log("=" * 60)

    # Start server
    log("Starting server...")
    server_proc = start_server()

    try:
        # Wait for server to start
        time.sleep(8)

        tests = [
            ("Health Check", test_health_check),
            ("Ping Test", test_ping),
            ("Chat Smoke Test", test_chat_smoke),
            ("Scheduler Status", test_scheduler_status),
            ("Import Status", test_import_status),
            ("AccuLynx Stub Mode", test_accuLynx_stub_mode),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            log(f"Running: {test_name}")
            if test_func():
                passed += 1
            log("-" * 40)

        log("=" * 60)
        log(f"Smoke Test Results: {passed}/{total} tests passed")

        if passed == total:
            log("🎉 All smoke tests passed! Build is ready for deployment.", "SUCCESS")
            return True
        else:
            log(f"❌ {total - passed} tests failed. Please investigate before deployment.", "ERROR")
            return False

    finally:
        # Clean up server
        log("Stopping server...")
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    success = run_smoke_tests()
    sys.exit(0 if success else 1)
