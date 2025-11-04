# pods/customer_ops/tests/test_lead_enrichment_smoke.py
from fastapi.testclient import TestClient

from pods.customer_ops.api.main import create_app


def test_lead_enrichment():
    """Test that lead creation includes enrichment data"""
    app = create_app()
    client = TestClient(app)
    
    # Create a lead with urgent details
    response = client.post(
        "/v1/lead",
        json={
            "name": "Jon Mikrut",
            "phone": "7632801272",
            "details": "URGENT: need estimate for metal roof today",
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert data["ok"] is True
    assert "data" in data
    
    # Verify enrichment fields are present
    lead_data = data["data"]
    assert "lead_id" in lead_data
    assert "intent" in lead_data
    assert "sentiment" in lead_data
    assert "urgency" in lead_data
    assert "score" in lead_data
    
    # Verify enrichment values
    assert lead_data["intent"] == "lead_capture"
    assert lead_data["urgency"] == "high"
    assert 0.5 <= lead_data["score"] <= 1.0


def test_lead_list_includes_history():
    """Test that lead list includes conversation history"""
    app = create_app()
    client = TestClient(app)
    
    # Create a lead
    create_response = client.post(
        "/v1/lead",
        json={
            "name": "Test User",
            "phone": "5551234567",
            "details": "Question about warranty coverage",
        },
    )
    assert create_response.status_code == 200
    
    # List leads
    list_response = client.get("/v1/lead")
    assert list_response.status_code == 200
    
    data = list_response.json()
    assert data["ok"] is True
    assert "data" in data
    assert "items" in data["data"]
    
    # Check that leads have history field
    items = data["data"]["items"]
    if items:
        lead = items[0]
        assert "last_messages" in lead
        assert isinstance(lead["last_messages"], list)
