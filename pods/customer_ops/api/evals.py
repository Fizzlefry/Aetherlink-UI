# pods/customer_ops/api/evals.py
import json
import pathlib
import time
from typing import Any

from fastapi import APIRouter, Depends

router = APIRouter()


# Import locally to avoid circular imports (ApiKeyRequired is defined in main.py)
def get_api_key():
    from .main import ApiKeyRequired

    return ApiKeyRequired


@router.post("/evals/run", dependencies=[Depends(get_api_key())])
async def evals_run(tenant: str = Depends(get_api_key())) -> dict[str, Any]:
    """Run golden test evaluations against the chat endpoint."""
    t0 = time.perf_counter()

    # Find golden.yml
    path = pathlib.Path(__file__).parent.parent / "evals" / "golden.yml"
    if not path.exists():
        return {"ok": False, "error": "no_golden_file", "message": "evals/golden.yml not found"}

    try:
        import yaml
    except ImportError:
        return {
            "ok": False,
            "error": "pyyaml_missing",
            "message": "Install PyYAML: pip install pyyaml",
        }

    # Load dataset
    try:
        ds = yaml.safe_load(path.read_text())["dataset"]
    except Exception as e:
        return {"ok": False, "error": "parse_error", "message": str(e)}

    results = []
    ok = 0

    # Use TestClient for local loopback without network overhead
    from fastapi.testclient import TestClient

    from pods.customer_ops.api.main import app

    c = TestClient(app)
    headers = {"x-api-key": tenant}

    for row in ds:
        q = row["question"]
        r = c.post("/chat", headers=headers, json={"message": q})

        try:
            j = r.json()
        except Exception:
            j = {"error": "bad_json"}

        passed = True
        reason = None

        # Check must_contain constraints
        if "must_contain" in row and isinstance(j, dict):
            out = json.dumps(j).lower()
            for m in row["must_contain"]:
                if m.lower() not in out:
                    passed = False
                    reason = f"missing: {m}"
                    break

        # Check expect_tool constraint
        if "expect_tool" in row and isinstance(j, dict):
            tool_name = row["expect_tool"]
            response_str = json.dumps(j).lower()
            if tool_name.lower() not in response_str:
                passed = False
                reason = f"expected tool: {tool_name}"

        results.append({"id": row["id"], "ok": passed, "reason": reason})

        if passed:
            ok += 1

    dt = (time.perf_counter() - t0) * 1000

    return {"ok": True, "n": len(results), "passed": ok, "latency_ms": dt, "results": results}
