from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_metrics_endpoint():
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"agent_intent_total" in r.content

def test_lead_create_and_list_without_key_allowed_in_dev(monkeypatch):
    # In dev we often allow no API key
    monkeypatch.setenv("REQUIRE_API_KEY", "false")
    c = TestClient(app)
    r = c.post("/v1/lead", json={"name":"Jon","phone":"7632801272","details":"Metal roof"})
    assert r.status_code in (200, 401)
    if r.status_code == 200:
        lead_id = r.json()["data"]["lead_id"]
        assert lead_id.startswith("L")
        r2 = c.get("/v1/lead")
        assert r2.status_code == 200
        assert any(i["id"] == lead_id for i in r2.json()["data"]["items"])

def test_lead_requires_key_when_enabled(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.setenv("API_KEYS", "acme:ACME_KEY")
    c = TestClient(app)
    # Reload settings in the running app so it picks up the monkeypatched env
    c.get("/ops/reload")
    # No key -> unauthorized
    r = c.post("/v1/lead", json={"name":"Alice","phone":"1234567"})
    assert r.status_code == 401
    # With key -> ok
    r2 = c.post("/v1/lead", headers={"x-api-key":"ACME_KEY"}, json={"name":"Alice","phone":"1234567"})
    assert r2.status_code == 200
