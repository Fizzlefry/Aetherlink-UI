from fastapi.testclient import TestClient
from ..api.main import app

def test_rate_limit_json_shape(monkeypatch):
    c = TestClient(app)
    # Try multiple hits without API key to trigger error pathway reliably
    got_err = False
    for _ in range(10):
        r = c.get("/ops/model-status")
        if r.status_code == 429:
            body = r.json()
            assert "error" in body
            assert body["error"]["type"] in ("rate_limited", "http_error")
            got_err = True
            break
    assert got_err
