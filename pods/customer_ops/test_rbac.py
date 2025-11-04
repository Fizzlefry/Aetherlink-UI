#!/usr/bin/env python3
"""
🔒 RBAC Verification Suite
Tests role-based access control for admin/editor/viewer roles.
"""
import requests
import time

BASE = "http://localhost:8000"
API_KEY = "test-key"
ADMIN_KEY = "admin-secret-123"

def test_viewer_read_only():
    """Viewer can read, but not write."""
    print("\n1️⃣  Viewer Role (read-only)...")
    headers = {"x-api-key": API_KEY, "x-role": "viewer"}
    
    # Should succeed: list knowledge
    r = requests.get(f"{BASE}/knowledge/list", headers=headers)
    if r.status_code == 200:
        print("    ✅ Viewer CAN list knowledge")
    else:
        print(f"    ❌ Viewer blocked from list: {r.status_code}")
        return False
    
    # Should fail: ingest knowledge
    try:
        r = requests.post(
            f"{BASE}/knowledge/ingest",
            headers={**headers, "Content-Type": "application/json"},
            json={"text": "test", "source": "rbac"}
        )
        if r.status_code == 403:
            print("    ✅ Viewer blocked from ingest (403)")
        else:
            print(f"    ❌ Viewer should be blocked from ingest, got: {r.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Error testing viewer ingest: {e}")
        return False
    
    # Should fail: delete knowledge
    try:
        r = requests.delete(f"{BASE}/knowledge/delete?ids=1", headers=headers)
        if r.status_code == 403:
            print("    ✅ Viewer blocked from delete (403)")
        else:
            print(f"    ❌ Viewer should be blocked from delete, got: {r.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Error testing viewer delete: {e}")
        return False
    
    # Should fail: dashboard access
    try:
        r = requests.get(f"{BASE}/", headers=headers)
        if r.status_code == 403:
            print("    ✅ Viewer blocked from dashboard (403)")
        else:
            print(f"    ❌ Viewer should be blocked from dashboard, got: {r.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Error testing viewer dashboard: {e}")
        return False
    
    return True

def test_editor_can_write():
    """Editor can read and write knowledge."""
    print("\n2️⃣  Editor Role (read + write)...")
    headers = {"x-api-key": API_KEY, "x-role": "editor", "Content-Type": "application/json"}
    
    # Should succeed: ingest knowledge
    r = requests.post(
        f"{BASE}/knowledge/ingest",
        headers=headers,
        json={"text": "RBAC test from editor", "source": "rbac_test"}
    )
    if r.status_code == 200:
        data = r.json()
        print(f"    ✅ Editor CAN ingest: {data.get('ingested_chunks', 0)} chunks")
    else:
        print(f"    ❌ Editor failed to ingest: {r.status_code} - {r.text}")
        return False
    
    # Should succeed: list knowledge
    r = requests.get(f"{BASE}/knowledge/list", headers=headers)
    if r.status_code == 200:
        print("    ✅ Editor CAN list knowledge")
    else:
        print(f"    ❌ Editor blocked from list: {r.status_code}")
        return False
    
    # Should fail: dashboard access (editor ≠ admin)
    try:
        r = requests.get(f"{BASE}/", headers=headers)
        if r.status_code == 403:
            print("    ✅ Editor blocked from dashboard (403)")
        else:
            print(f"    ❌ Editor should be blocked from dashboard, got: {r.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Error testing editor dashboard: {e}")
        return False
    
    return True

def test_admin_full_access():
    """Admin can access everything."""
    print("\n3️⃣  Admin Role (full access)...")
    headers = {"x-admin-key": ADMIN_KEY, "x-role": "admin"}
    
    # Should succeed: dashboard
    r = requests.get(f"{BASE}/", headers=headers)
    if r.status_code == 200:
        print("    ✅ Admin CAN access dashboard")
    else:
        print(f"    ❌ Admin blocked from dashboard: {r.status_code}")
        return False
    
    # Should succeed: ingest (with admin key, implicit admin role)
    admin_headers = {"x-admin-key": ADMIN_KEY, "x-api-key": API_KEY, "Content-Type": "application/json"}
    r = requests.post(
        f"{BASE}/knowledge/ingest",
        headers=admin_headers,
        json={"text": "Admin test", "source": "admin_rbac"}
    )
    if r.status_code == 200:
        print("    ✅ Admin CAN ingest knowledge")
    else:
        print(f"    ❌ Admin failed to ingest: {r.status_code}")
        return False
    
    return True

def test_admin_key_grants_admin_role():
    """Admin key should grant admin role implicitly (no x-role needed)."""
    print("\n4️⃣  Admin Key Auto-Grants Admin Role...")
    headers = {"x-admin-key": ADMIN_KEY}  # No x-role header
    
    r = requests.get(f"{BASE}/", headers=headers)
    if r.status_code == 200:
        print("    ✅ Admin key grants dashboard access without x-role")
    else:
        print(f"    ❌ Admin key should grant access, got: {r.status_code}")
        return False
    
    return True

def test_invalid_role():
    """Invalid role should be rejected."""
    print("\n5️⃣  Invalid Role Rejection...")
    headers = {"x-api-key": API_KEY, "x-role": "hacker"}
    
    r = requests.get(f"{BASE}/knowledge/list", headers=headers)
    if r.status_code == 403:
        print("    ✅ Invalid role rejected (403)")
    else:
        print(f"    ❌ Invalid role should be rejected, got: {r.status_code}")
        return False
    
    return True

def test_backward_compatibility():
    """No x-role header should default to viewer (backward-compatible)."""
    print("\n6️⃣  Backward Compatibility (defaults to viewer)...")
    headers = {"x-api-key": API_KEY}  # No x-role header
    
    # Should succeed: list (viewer permission)
    r = requests.get(f"{BASE}/knowledge/list", headers=headers)
    if r.status_code == 200:
        print("    ✅ No x-role defaults to viewer (can list)")
    else:
        print(f"    ❌ Default viewer should list, got: {r.status_code}")
        return False
    
    # Should fail: ingest (viewer can't write)
    r = requests.post(
        f"{BASE}/knowledge/ingest",
        headers={**headers, "Content-Type": "application/json"},
        json={"text": "test", "source": "compat"}
    )
    if r.status_code == 403:
        print("    ✅ Default viewer blocked from ingest (403)")
    else:
        print(f"    ❌ Default viewer should be blocked from ingest, got: {r.status_code}")
        return False
    
    return True

if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  🔒 RBAC Verification Suite          ║")
    print("╚════════════════════════════════════════╝")
    
    # Wait for service
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
    
    results = []
    results.append(("Viewer (read-only)", test_viewer_read_only()))
    results.append(("Editor (read+write)", test_editor_can_write()))
    results.append(("Admin (full access)", test_admin_full_access()))
    results.append(("Admin key auto-role", test_admin_key_grants_admin_role()))
    results.append(("Invalid role rejection", test_invalid_role()))
    results.append(("Backward compatibility", test_backward_compatibility()))
    
    print("\n╔════════════════════════════════════════╗")
    print("║  📊 Test Results                      ║")
    print("╚════════════════════════════════════════╝\n")
    
    passed = sum(1 for _, result in results if result)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print(f"\n  Score: {passed}/{len(results)} tests passed\n")
    
    if passed == len(results):
        print("  🎉 ALL RBAC TESTS PASSED! Role-based access control is fully operational!")
    else:
        print(f"  ⚠️  {len(results) - passed} test(s) failed")
    
    exit(0 if passed == len(results) else 1)
