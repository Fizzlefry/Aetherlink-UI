#!/usr/bin/env python3
"""
🔄 Background Ingestion Verification Suite
Tests async job queue for text/URL/file ingestion.
"""
import requests
import time

BASE = "http://localhost:8000"
API_KEY = "test-key"
ADMIN_KEY = "admin-secret-123"

def wait_for_job(job_id: str, timeout: int = 30) -> dict:
    """Poll job status until finished or failed."""
    headers = {"x-admin-key": ADMIN_KEY}
    start = time.time()
    
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/ops/jobs/{job_id}", headers=headers, timeout=5)
        if r.status_code != 200:
            return {"error": f"job_status_failed: {r.status_code}"}
        
        job = r.json()
        status = job.get("status")
        
        if status == "finished":
            return job
        elif status == "failed":
            return job
        
        time.sleep(0.5)
    
    return {"error": "timeout"}

def test_async_text_ingest():
    """Test async text ingestion."""
    print("\n1️⃣  Async Text Ingestion...")
    headers = {"x-api-key": API_KEY, "x-role": "editor", "Content-Type": "application/json"}
    
    payload = {
        "text": "Background job test: customer reported urgent issue with account #999",
        "source": "async_test"
    }
    
    r = requests.post(f"{BASE}/knowledge/ingest-text-async", json=payload, headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"    ❌ Failed to enqueue: {r.status_code} - {r.text}")
        return False
    
    data = r.json()
    job_id = data.get("job_id")
    print(f"    ✅ Job enqueued: {job_id}")
    
    # Poll for completion
    job = wait_for_job(job_id)
    if "error" in job:
        print(f"    ❌ Job failed: {job['error']}")
        return False
    
    if job["status"] == "finished":
        result = job.get("result", {})
        if result.get("ok"):
            chunks = result.get("ingested_chunks", 0)
            print(f"    ✅ Job completed: {chunks} chunks ingested")
            return True
        else:
            print(f"    ❌ Job finished with error: {result.get('error')}")
            return False
    else:
        print(f"    ❌ Job failed: {job.get('error', 'unknown')}")
        return False

def test_async_url_ingest():
    """Test async URL ingestion."""
    print("\n2️⃣  Async URL Ingestion...")
    headers = {"x-api-key": API_KEY, "x-role": "editor", "Content-Type": "application/json"}
    
    payload = {
        "url": "https://example.com",
        "source": "web_test"
    }
    
    r = requests.post(f"{BASE}/knowledge/ingest-url-async", json=payload, headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"    ❌ Failed to enqueue: {r.status_code} - {r.text}")
        return False
    
    data = r.json()
    job_id = data.get("job_id")
    print(f"    ✅ Job enqueued: {job_id}")
    
    # Poll for completion
    job = wait_for_job(job_id, timeout=60)  # URLs take longer
    if "error" in job:
        print(f"    ❌ Job failed: {job['error']}")
        return False
    
    if job["status"] == "finished":
        result = job.get("result", {})
        if result.get("ok"):
            chunks = result.get("ingested_chunks", 0)
            print(f"    ✅ Job completed: {chunks} chunks from URL")
            return True
        else:
            print(f"    ❌ Job finished with error: {result.get('error')}")
            return False
    else:
        print(f"    ❌ Job failed: {job.get('error', 'unknown')}")
        return False

def test_async_file_ingest():
    """Test async file ingestion."""
    print("\n3️⃣  Async File Ingestion...")
    headers = {"x-api-key": API_KEY, "x-role": "editor"}
    
    # Create test file
    files = {"file": ("test.txt", b"Async file test content: lead #888 needs follow-up", "text/plain")}
    data = {"source": "file_test"}
    
    r = requests.post(f"{BASE}/knowledge/ingest-file-async", files=files, data=data, headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"    ❌ Failed to enqueue: {r.status_code} - {r.text}")
        return False
    
    resp_data = r.json()
    job_id = resp_data.get("job_id")
    print(f"    ✅ Job enqueued: {job_id}")
    
    # Poll for completion
    job = wait_for_job(job_id)
    if "error" in job:
        print(f"    ❌ Job failed: {job['error']}")
        return False
    
    if job["status"] == "finished":
        result = job.get("result", {})
        if result.get("ok"):
            chunks = result.get("ingested_chunks", 0)
            print(f"    ✅ Job completed: {chunks} chunks from file")
            return True
        else:
            print(f"    ❌ Job finished with error: {result.get('error')}")
            return False
    else:
        print(f"    ❌ Job failed: {job.get('error', 'unknown')}")
        return False

def test_job_not_found():
    """Test job status for non-existent job."""
    print("\n4️⃣  Job Not Found...")
    headers = {"x-admin-key": ADMIN_KEY}
    
    r = requests.get(f"{BASE}/ops/jobs/fake-job-id-999", headers=headers, timeout=5)
    if r.status_code == 404:
        print("    ✅ Correctly returns 404 for missing job")
        return True
    else:
        print(f"    ❌ Should return 404, got: {r.status_code}")
        return False

def test_viewer_blocked():
    """Test that viewer role cannot enqueue jobs."""
    print("\n5️⃣  Viewer Role Blocked from Enqueue...")
    headers = {"x-api-key": API_KEY, "x-role": "viewer", "Content-Type": "application/json"}
    
    payload = {"text": "test", "source": "test"}
    
    r = requests.post(f"{BASE}/knowledge/ingest-text-async", json=payload, headers=headers, timeout=10)
    if r.status_code == 403:
        print("    ✅ Viewer correctly blocked (403)")
        return True
    else:
        print(f"    ❌ Should return 403, got: {r.status_code}")
        return False

if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  🔄 Background Ingestion Tests       ║")
    print("╚════════════════════════════════════════╝")
    
    # Wait for service + worker
    print("\n⏳ Waiting for service...")
    for i in range(30):
        try:
            r = requests.get(f"{BASE}/health", timeout=2)
            if r.status_code == 200:
                print("✅ Service ready")
                break
        except:
            pass
        time.sleep(1)
    else:
        print("❌ Service not ready after 30s")
        exit(1)
    
    print("\n⏳ Giving worker 5s to start...")
    time.sleep(5)
    
    results = []
    results.append(("Async text ingest", test_async_text_ingest()))
    results.append(("Async URL ingest", test_async_url_ingest()))
    results.append(("Async file ingest", test_async_file_ingest()))
    results.append(("Job not found", test_job_not_found()))
    results.append(("Viewer blocked", test_viewer_blocked()))
    
    print("\n╔════════════════════════════════════════╗")
    print("║  📊 Test Results                      ║")
    print("╚════════════════════════════════════════╝\n")
    
    passed = sum(1 for _, result in results if result)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print(f"\n  Score: {passed}/{len(results)} tests passed\n")
    
    if passed == len(results):
        print("  🎉 ALL BACKGROUND INGESTION TESTS PASSED!")
    else:
        print(f"  ⚠️  {len(results) - passed} test(s) failed")
    
    exit(0 if passed == len(results) else 1)
