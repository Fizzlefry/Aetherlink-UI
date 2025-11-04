from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_lead_smoke():
    c = TestClient(app)
    r = c.post("/v1/lead", json={"name": "Jon", "phone": "7632801272", "details": "Metal roof"})
    assert r.status_code in (200, 401)  # 401 if REQUIRE_API_KEY=true locally
    if r.status_code == 200:
        assert r.json().get("ok") is True
        assert "lead_id" in r.json()["data"]


def test_metrics_endpoint():
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"agent_intent_total" in r.content
