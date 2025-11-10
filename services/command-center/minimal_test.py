from fastapi import FastAPI

app = FastAPI(title="Test", version="0.1.0")


@app.get("/test")
def test():
    return {"ok": True}


@app.get("/ops/ping")
def ops_ping():
    return {"ok": True}


@app.get("/ops/health")
def ops_health():
    return {"ok": True}


@app.get("/api/crm/import/acculynx/schedule/status")
def schedule_status():
    return {"ok": True}


@app.get("/api/local/runs")
def local_runs():
    return {"ok": True}
