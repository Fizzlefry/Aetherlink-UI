"""
Test suite for admin dashboard endpoints.
"""
import os
import sys
import requests
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

BASE_URL = "http://localhost:8000"
ADMIN_KEY = "admin-secret-123"

def test_admin_overview():
    """Test /admin/overview endpoint returns recent ingests."""
    print("\n🧪 Test 1: /admin/overview endpoint")
    
    headers = {'x-admin-key': ADMIN_KEY}
    response = requests.get(f"{BASE_URL}/admin/overview", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    assert data["ok"] is True
    assert "count" in data
    assert "documents" in data
    assert isinstance(data["documents"], list)
    
    if data["count"] > 0:
        # Check first document structure
        doc = data["documents"][0]
        assert "doc_key" in doc
        assert "chunks" in doc
        assert "total_chars" in doc
        print(f"   ✅ PASS - Found {data['count']} documents")
        print(f"   📄 Sample: {doc.get('title') or doc['doc_key']} ({doc['chunks']} chunks)")
    else:
        print("   ⚠️  PASS - No documents yet (database empty)")

def test_admin_ui():
    """Test /admin/ui endpoint returns HTML."""
    print("\n🧪 Test 2: /admin/ui endpoint")
    
    headers = {'x-admin-key': ADMIN_KEY}
    response = requests.get(f"{BASE_URL}/admin/ui", headers=headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "text/html" in response.headers["Content-Type"]
    assert "AetherLink Admin Dashboard" in response.text
    assert "Recent Ingestions" in response.text
    assert "Search Knowledge Base" in response.text
    
    print("   ✅ PASS - HTML dashboard loads correctly")

def test_admin_rbac():
    """Test that non-admin cannot access admin endpoints."""
    print("\n🧪 Test 3: RBAC protection")
    
    # Try without admin key
    response = requests.get(f"{BASE_URL}/admin/overview")
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    # Try with viewer role
    headers = {'x-api-key': 'test-key', 'x-role': 'viewer'}
    response = requests.get(f"{BASE_URL}/admin/overview", headers=headers)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    print("   ✅ PASS - Admin endpoints protected by RBAC")

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Admin Dashboard Test Suite")
    print("=" * 70)
    
    # Wait for service
    print("\n⏳ Waiting for service...")
    for _ in range(30):
        try:
            requests.get(f"{BASE_URL}/health", timeout=1)
            print("✅ Service ready\n")
            break
        except:
            time.sleep(1)
    else:
        print("❌ Service not available")
        sys.exit(1)
    
    try:
        test_admin_overview()
        test_admin_ui()
        test_admin_rbac()
        
        print("\n" + "=" * 70)
        print("🎉 ALL ADMIN DASHBOARD TESTS PASSED!")
        print("=" * 70)
        print("\nScore: 3/3 tests passed")
        
    except AssertionError as e:
        print(f"\n❌ FAIL  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR  {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
