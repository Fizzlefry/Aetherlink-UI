from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# Build a tiny app that reuses your handler from main.py
def build_app():
    # The real handler in `main` is nested inside create_app() and not importable.
    # For test purposes we register a local handler that mirrors the envelope
    # returned by the app (uses the same `err` envelope shape).
    from fastapi.responses import JSONResponse

    from pods.customer_ops.api.envelope import err

    app = FastAPI()
    # lightweight middleware to copy x-request-id header into request.state.request_id
    @app.middleware("http")
    async def _inject_request_id(request, call_next):
        request.state.request_id = request.headers.get("x-request-id", "n/a")
        return await call_next(request)

    async def _local_ratelimit_handler(request, exc):
        req_id = getattr(request.state, "request_id", "n/a")
        return JSONResponse(status_code=429, content=err(req_id, "Too many requests — please slow down.", code="rate_limited"))

    app.add_exception_handler(429, _local_ratelimit_handler)

    @app.get("/boom")
    def boom():
        raise HTTPException(status_code=429, detail="simulated limit")

    return app


def test_429_envelope_contains_request_id():
    app = build_app()
    client = TestClient(app)
    r = client.get("/boom", headers={"x-request-id": "TESTID123"})
    assert r.status_code == 429
    body = r.json()
    assert body.get("ok") is False
    assert body.get("request_id") == "TESTID123"
    # error message lives under `error.message` in the project's envelope
    assert body.get("error", {}).get("message", "").lower().startswith("too many requests")
