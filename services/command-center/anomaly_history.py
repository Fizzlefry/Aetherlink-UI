# services/command-center/anomaly_history.py
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List

HISTORY_PATH = Path("data/anomaly_history.jsonl")
HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

def append_anomaly_record(record: Dict[str, Any]) -> None:
    """Append a single anomaly/remediation record to history."""
    # add server-side timestamp
    record = dict(record)
    record.setdefault("ts", time.time())
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def read_anomaly_records(
    tenant: str | None = None,
    since_ts: float | None = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Read history, optionally filter by tenant and time."""
    results: List[Dict[str, Any]] = []
    if not HISTORY_PATH.exists():
        return results
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in reversed(list(f.readlines())):
            try:
                item = json.loads(line)
            except Exception:
                continue
            if tenant and item.get("tenant") != tenant:
                continue
            if since_ts and item.get("ts", 0) < since_ts:
                continue
            results.append(item)
            if len(results) >= limit:
                break
    return results