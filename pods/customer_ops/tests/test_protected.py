from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_protected_route_unauthorized():
    c = TestClient(app)
    r = c.get("/ops/model-status")
    assert r.status_code in (401, 404)


def test_protected_route_authorized():
    # patch state for test
    app.state.AUTH_KEYS = {"TKEY": "TEST"}
    c = TestClient(app)
    r = c.get("/ops/model-status", headers={"x-api-key": "TKEY"})
    assert r.status_code == 200
