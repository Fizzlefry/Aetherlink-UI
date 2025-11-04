import json
import os
import threading
import time
from typing import Any

try:
    from prometheus_client import Histogram

    AUDIT_WRITE_SECONDS = Histogram(
        "autoheal_audit_write_seconds",
        "Time spent writing to audit log",
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    )
    _METRICS_ENABLED = True
except ImportError:
    _METRICS_ENABLED = False

_AUDIT_PATH = os.getenv("AUTOHEAL_AUDIT_PATH", "/app/audit.jsonl")
_LOCK = threading.Lock()


def now_ts() -> float:
    return time.time()


def write_event(event: dict[str, Any]) -> None:
    start = time.time()
    event.setdefault("ts", now_ts())
    line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    with _LOCK:
        with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # Record write latency (SLO-4)
    if _METRICS_ENABLED:
        duration = time.time() - start
        AUDIT_WRITE_SECONDS.observe(duration)


def tail(n: int = 200) -> str:
    try:
        with _LOCK:
            with open(_AUDIT_PATH, encoding="utf-8") as f:
                lines = f.readlines()[-n:]
        return "".join(lines)
    except FileNotFoundError:
        return ""
