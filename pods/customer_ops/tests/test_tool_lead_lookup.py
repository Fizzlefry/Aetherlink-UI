from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_tool_lead_lookup():
    c = TestClient(app)
    r = c.post("/chat", json={"message": "Call lead_lookup with lead_id=xyz"})
    assert r.status_code in (200, 401)
    if r.status_code == 200:
        js = r.json()
        # May return text or tool_result depending on model behavior
        assert "reply" in js or "tool_result" in js
