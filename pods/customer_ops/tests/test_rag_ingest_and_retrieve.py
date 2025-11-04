from fastapi.testclient import TestClient

from ..api.main import app


def test_ingest_and_retrieve():
    c = TestClient(app)
    h = {"x-api-key": "ABC123"}
    # Ingest
    text = "AetherLink uses CustomerOps pods. The hotline is 555-0101. Lead xyz is high priority."
    r = c.post("/knowledge/ingest", headers=h, json={"text": text, "source": "unit"})
    assert r.status_code == 200
    assert r.json()["ingested_chunks"] >= 1

    # Ask a related question; expect 200 and not crash (we don't assert model text, just path)
    q = {"message": "Where is lead xyz tracked?"}
    r2 = c.post("/chat", headers=h, json=q)
    assert r2.status_code in (200, 429)  # allow rate limit in CI
