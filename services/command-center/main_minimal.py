# from prometheus_client import Counter
import time
from typing import Any

from fastapi import FastAPI, Request

LOCAL_ACTION_RUNS: list[dict[str, Any]] = []
MAX_LOCAL_ACTION_RUNS = 50

# local_actions_total = Counter(
#     "aetherlink_local_actions_total",
#     "Total local actions invoked from UI",
#     ["tenant", "action"],
# )

app = FastAPI()


@app.get("/test")
def test():
    return {"message": "Hello World"}


@app.post("/api/local/run")
async def local_run(request: Request):
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")
        body = await request.json()
        action = body.get("action")
        if not action:
            return {"ok": False, "error": "action is required"}

        run_rec = {
            "action": action,
            "tenant": tenant,
            "timestamp": time.time(),
            "ok": True,
            "stdout": f"Executed {action}",
            "stderr": "",
            "error": None,
        }

        LOCAL_ACTION_RUNS.insert(0, run_rec)
        if len(LOCAL_ACTION_RUNS) > MAX_LOCAL_ACTION_RUNS:
            LOCAL_ACTION_RUNS.pop()

        # Increment Prometheus counter
        # local_actions_total.labels(tenant=tenant, action=action).inc()

        return {"ok": True, "stdout": f"Executed {action}", "stderr": "", "error": None}
    except Exception as e:
        print(f"Error in local_run: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/local/runs")
async def list_local_runs():
    try:
        return {"runs": LOCAL_ACTION_RUNS}
    except Exception as e:
        print(f"Error in list_local_runs: {e}")
        return {"runs": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
