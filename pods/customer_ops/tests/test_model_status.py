from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_model_status_smoke():
    c = TestClient(app)
    r = c.get("/ops/model-status")
    assert r.status_code in (200, 401)
