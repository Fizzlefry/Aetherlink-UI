from fastapi.testclient import TestClient
from ..api.main import app

def test_missing_api_key_returns_json_error():
    c = TestClient(app)
    r = c.post("/chat", json={"message": "hi"})
    assert r.status_code in (401, 403)
    body = r.json()
    assert "error" in body and "type" in body["error"] and "message" in body["error"]

def test_validation_error_shape():
    c = TestClient(app)
    # Force validation by sending non-JSON content-type on JSON endpoint
    r = c.post("/chat", data="not-json")
    assert r.status_code in (400, 422)
    body = r.json()
    assert "error" in body and body["error"]["type"] in ("validation_error", "http_error")
