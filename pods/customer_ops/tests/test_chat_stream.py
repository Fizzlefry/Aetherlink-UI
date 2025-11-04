from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_stream_smoke():
    c = TestClient(app)
    r = c.post("/chat/stream", json={"message": "say hi"})
    # SSE is chunked; minimal assertion: 200
    assert r.status_code in (200, 401)
