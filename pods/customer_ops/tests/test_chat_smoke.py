from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_chat_requires_message_or_auth():
    c = TestClient(app)
    r = c.post("/chat", json={})
    assert r.status_code in (400, 401)
