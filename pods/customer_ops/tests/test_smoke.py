from fastapi.testclient import TestClient

from pods.customer_ops.api.main import app


def test_health_ops_endpoints():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    r = c.get("/ops/config")
    assert r.status_code == 200
    r = c.post("/ops/reload")
    assert r.status_code in (200, 405)


def test_semantic_cache_roundtrip():
    from pods.customer_ops.api.semcache import get_semcache, set_semcache
    payload = {"answer": "Test", "sources": ["doc://1"]}
    set_semcache("What is warranty?", payload)
    got = get_semcache("what is warranty?")
    assert got and got["answer"] == "Test"
