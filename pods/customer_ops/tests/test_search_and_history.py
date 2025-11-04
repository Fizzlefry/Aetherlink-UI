"""
Tests for lead history and search endpoints
"""
from fastapi.testclient import TestClient
from api.main import create_app


def test_lead_history_endpoint():
    """Test retrieving conversation history for a lead."""
    app = create_app()
    client = TestClient(app)
    
    # Create a lead with details
    resp = client.post(
        "/v1/lead",
        json={"name": "TestUser", "phone": "555-0001", "details": "I need a metal roof estimate"},
    )
    assert resp.status_code == 200, f"Failed to create lead: {resp.text}"
    
    data = resp.json()
    lead_id = data["lead_id"]
    
    # Retrieve history
    hist_resp = client.get(f"/v1/lead/{lead_id}/history?limit=10")
    assert hist_resp.status_code == 200, f"Failed to get history: {hist_resp.text}"
    
    hist_data = hist_resp.json()
    assert "items" in hist_data
    assert len(hist_data["items"]) > 0, "Expected at least one message in history"
    
    # Verify message structure
    msg = hist_data["items"][0]
    assert "role" in msg
    assert "text" in msg
    assert "timestamp" in msg


def test_search_leads_by_keyword():
    """Test searching leads by keyword across conversation history."""
    app = create_app()
    client = TestClient(app)
    
    # Create leads with different details
    client.post("/v1/lead", json={"name": "Alice", "phone": "555-1001", "details": "metal roof installation"})
    client.post("/v1/lead", json={"name": "Bob", "phone": "555-1002", "details": "solar panel quote"})
    client.post("/v1/lead", json={"name": "Charlie", "phone": "555-1003", "details": "metal siding repair"})
    
    # Search for "metal"
    search_resp = client.get("/v1/search?q=metal&limit=10")
    assert search_resp.status_code == 200, f"Search failed: {search_resp.text}"
    
    search_data = search_resp.json()
    assert "results" in search_data
    assert "count" in search_data
    assert search_data["count"] >= 2, "Expected at least 2 results for 'metal'"
    
    # Verify result structure
    if search_data["results"]:
        result = search_data["results"][0]
        assert "lead_id" in result
        assert "score" in result
        assert "preview" in result
        assert result["score"] > 0


def test_search_no_results():
    """Test search with no matching keywords."""
    app = create_app()
    client = TestClient(app)
    
    # Search for something unlikely
    search_resp = client.get("/v1/search?q=xyzabc123&limit=10")
    assert search_resp.status_code == 200
    
    search_data = search_resp.json()
    assert search_data["count"] == 0
    assert search_data["results"] == []


def test_histogram_metric_recorded():
    """Test that lead enrichment scores are recorded in histogram."""
    from api.main import LEAD_SCORE_HIST
    
    app = create_app()
    client = TestClient(app)
    
    # Get initial metric count
    initial_count = LEAD_SCORE_HIST._sum._value  # Access internal counter
    
    # Create a lead (triggers enrichment + histogram)
    resp = client.post(
        "/v1/lead",
        json={"name": "MetricTest", "phone": "555-9999", "details": "urgent metal roof repair needed"},
    )
    assert resp.status_code == 200
    
    # Verify histogram was updated
    final_count = LEAD_SCORE_HIST._sum._value
    assert final_count > initial_count, "Histogram should have recorded a score observation"
