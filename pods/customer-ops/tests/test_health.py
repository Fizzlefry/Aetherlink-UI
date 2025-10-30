import httpx


HTTP_OK = 200


def test_health_endpoint():
    """Integration-style smoke test — expects the API to be running on localhost:8000
    This test is intended to be run after the Docker Compose dev stack is started by CI.
    """
    resp = httpx.get("http://localhost:8000/health", timeout=10.0)
    assert resp.status_code == HTTP_OK
    payload = resp.json()
    assert isinstance(payload, dict)
    assert payload.get("ok") is True
