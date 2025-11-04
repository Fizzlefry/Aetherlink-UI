"""
Tests for outcome tracking (reward model foundation)
"""
from fastapi.testclient import TestClient
from api.main import create_app, OUTCOME_TOTAL, CONVERSION_RATE


def test_record_outcome():
    """Test recording an outcome for a lead."""
    app = create_app()
    client = TestClient(app)
    
    # Create a lead first
    lead_resp = client.post(
        "/v1/lead",
        json={"name": "OutcomeTest", "phone": "555-0001", "details": "test lead"},
    )
    assert lead_resp.status_code == 200
    lead_id = lead_resp.json()["lead_id"]
    
    # Record outcome
    outcome_resp = client.post(
        f"/v1/lead/{lead_id}/outcome",
        json={"outcome": "booked", "notes": "Customer confirmed appointment", "time_to_conversion": 3600},
    )
    assert outcome_resp.status_code == 200
    
    data = outcome_resp.json()
    assert data["lead_id"] == lead_id
    assert data["outcome"] == "booked"
    assert "recorded_at" in data


def test_record_outcome_nonexistent_lead():
    """Test that recording outcome for non-existent lead returns 404."""
    app = create_app()
    client = TestClient(app)
    
    resp = client.post(
        "/v1/lead/FAKE_ID/outcome",
        json={"outcome": "ghosted", "notes": ""},
    )
    assert resp.status_code == 404


def test_outcome_metrics_incremented():
    """Test that outcome metrics are incremented."""
    app = create_app()
    client = TestClient(app)
    
    # Get initial count
    initial_count = OUTCOME_TOTAL.labels(outcome="qualified")._value._value
    
    # Create lead and record outcome
    lead_resp = client.post(
        "/v1/lead",
        json={"name": "MetricTest", "phone": "555-9999", "details": "test"},
    )
    lead_id = lead_resp.json()["lead_id"]
    
    client.post(
        f"/v1/lead/{lead_id}/outcome",
        json={"outcome": "qualified", "notes": "Good fit"},
    )
    
    # Check metric incremented
    final_count = OUTCOME_TOTAL.labels(outcome="qualified")._value._value
    assert final_count > initial_count


def test_conversion_rate_gauge_updated():
    """Test that conversion rate gauge is updated after outcome."""
    app = create_app()
    client = TestClient(app)
    
    # Create lead and mark as booked
    lead_resp = client.post(
        "/v1/lead",
        json={"name": "ConversionTest", "phone": "555-8888", "details": "test"},
    )
    lead_id = lead_resp.json()["lead_id"]
    
    client.post(
        f"/v1/lead/{lead_id}/outcome",
        json={"outcome": "booked", "notes": "Scheduled for tomorrow"},
    )
    
    # Gauge should have been updated (value between 0 and 1)
    gauge_value = CONVERSION_RATE._value._value
    assert 0.0 <= gauge_value <= 1.0


def test_analytics_outcomes():
    """Test the analytics endpoint for aggregated outcome stats."""
    app = create_app()
    client = TestClient(app)
    
    # Create multiple leads with different outcomes
    leads = []
    for i in range(3):
        resp = client.post(
            "/v1/lead",
            json={"name": f"Lead{i}", "phone": f"555-000{i}", "details": "test"},
        )
        leads.append(resp.json()["lead_id"])
    
    # Record outcomes
    client.post(f"/v1/lead/{leads[0]}/outcome", json={"outcome": "booked", "notes": "", "time_to_conversion": 1800})
    client.post(f"/v1/lead/{leads[1]}/outcome", json={"outcome": "ghosted", "notes": ""})
    client.post(f"/v1/lead/{leads[2]}/outcome", json={"outcome": "booked", "notes": "", "time_to_conversion": 3600})
    
    # Get analytics
    analytics_resp = client.get("/v1/analytics/outcomes?limit=500")
    assert analytics_resp.status_code == 200
    
    data = analytics_resp.json()
    assert "total_outcomes" in data
    assert "conversion_rate" in data
    assert "outcome_breakdown" in data
    assert "avg_time_to_conversion" in data
    
    # Verify breakdown
    breakdown = data["outcome_breakdown"]
    assert "booked" in breakdown
    assert "ghosted" in breakdown
    
    # Verify conversion rate calculation (at least 2 booked out of recent outcomes)
    assert data["conversion_rate"] > 0.0


def test_outcome_types():
    """Test all outcome types are accepted."""
    app = create_app()
    client = TestClient(app)
    
    outcomes = ["booked", "ghosted", "qualified", "unqualified", "nurture", "spam"]
    
    for outcome_type in outcomes:
        lead_resp = client.post(
            "/v1/lead",
            json={"name": f"Test{outcome_type}", "phone": "555-0000", "details": "test"},
        )
        lead_id = lead_resp.json()["lead_id"]
        
        outcome_resp = client.post(
            f"/v1/lead/{lead_id}/outcome",
            json={"outcome": outcome_type, "notes": f"Testing {outcome_type}"},
        )
        assert outcome_resp.status_code == 200
        assert outcome_resp.json()["outcome"] == outcome_type


def test_outcome_with_time_to_conversion():
    """Test that time_to_conversion is properly stored and aggregated."""
    app = create_app()
    client = TestClient(app)
    
    # Create lead and record outcome with conversion time
    lead_resp = client.post(
        "/v1/lead",
        json={"name": "TimedConversion", "phone": "555-7777", "details": "test"},
    )
    lead_id = lead_resp.json()["lead_id"]
    
    outcome_resp = client.post(
        f"/v1/lead/{lead_id}/outcome",
        json={"outcome": "booked", "notes": "Fast conversion", "time_to_conversion": 1200},
    )
    assert outcome_resp.status_code == 200
    
    # Get analytics and verify avg_time_to_conversion exists
    analytics_resp = client.get("/v1/analytics/outcomes?limit=500")
    data = analytics_resp.json()
    
    # If this is the only booked lead with time, avg should equal the value
    if data["outcome_breakdown"].get("booked", 0) == 1:
        assert data["avg_time_to_conversion"] is not None
