from fastapi import FastAPI

app = FastAPI(title="AetherLink Command Center", version="0.1.0")
print("App created")

@app.get("/test")
def test():
    print("Test endpoint called")
    import sys
    sys.stdout.flush()
    return {"ok": True}

@app.get("/api/crm/import/acculynx/schedule/status")
def schedule_status():
    return {"ok": True, "schedules": {}}

@app.get("/api/local/runs")
def local_runs():
    return {"runs": []}

@app.get("/ops/ping")
def ops_ping():
    return {"status": "ok"}

@app.get("/ops/health")
def ops_health():
    return {"status": "ok"}

@app.get("/ops/db")
def ops_db():
    return {"db_status": "ok"}

print(f"App has {len(app.routes)} routes")
