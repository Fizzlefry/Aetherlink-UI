from fastapi.testclient import TestClient
from ..api.main import app

def test_sse_error_event_on_exception(monkeypatch):
    c = TestClient(app)

    # Simulate model stream raising
    def _bad_stream(msg, system=None, context=None, tools=None):
        async def _gen():
            raise RuntimeError("boom")
            yield  # pragma: no cover
        return _gen()

    app.state.model_client.stream = _bad_stream  # type: ignore[attr-defined]
    with c.stream("POST", "/chat/stream", json={"message":"test"}, headers={"x-api-key":"abc"}) as s:
        # Read a couple events; we expect an 'error' event
        any_error = False
        for line in s.iter_lines():
            if line.decode("utf-8").startswith("event: error"):
                any_error = True
                break
        assert any_error
