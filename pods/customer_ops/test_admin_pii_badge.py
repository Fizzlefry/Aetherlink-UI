#!/usr/bin/env python3
"""
Test that /admin/overview includes PII badge information.
"""
def test_admin_overview_pii_badge():
    """Verify PII field present in admin overview response"""
    from fastapi.testclient import TestClient
    from api.main import app
    
    client = TestClient(app)
    response = client.get("/admin/overview?limit=10", headers={"x-admin-key": "admin-secret-123"})
    
    assert response.status_code == 200
    data = response.json()
    
    # Get documents list (could be "documents" or "items")
    docs = data.get("documents") or data.get("items") or []
    assert isinstance(docs, list), "Response should contain a list of documents"
    
    # Find pii-test document
    found = None
    for doc in docs:
        if "pii" in doc and "pii-test" in doc.get("doc_key", ""):
            found = doc
            break
    
    assert found, "pii-test document not found in overview"
    
    # Validate PII structure
    pii = found["pii"]
    assert isinstance(pii.get("enabled"), bool), "pii.enabled should be boolean"
    assert isinstance(pii.get("types"), list), "pii.types should be list"
    
    # Validate hits
    hits = pii.get("hits", {})
    for key in ("EMAIL", "PHONE", "SSN", "CARD"):
        assert key in hits, f"Missing {key} in hits"
        assert isinstance(hits[key], int), f"{key} should be int"
    
    # At least one placeholder should be found
    total_hits = sum(hits.values())
    assert total_hits >= 1, f"Expected at least 1 PII placeholder, got {total_hits}"
    
    print(f"✅ PII badge test passed!")
    print(f"   - Enabled: {pii['enabled']}")
    print(f"   - Types: {pii['types']}")
    print(f"   - Hits: {hits}")
    print(f"   - Total: {total_hits}")


if __name__ == "__main__":
    test_admin_overview_pii_badge()
