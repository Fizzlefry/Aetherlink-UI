from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import Response, PlainTextResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import subprocess
import json
import re
import time
import requests
import queue
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from audit import write_event, tail, now_ts

# OpenTelemetry (OTLP tracing)
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
if OTEL_ENABLED:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    
    # Configure OTLP exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otelcol:4318/v1/traces")
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)

# Import OIDC auth if enabled
OIDC_ENABLED = os.getenv("OIDC_ENABLED", "false").lower() == "true"
if OIDC_ENABLED:
    from auth import require_oidc, _verify

app = FastAPI()

# Instrument with OpenTelemetry
if OTEL_ENABLED:
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()

# OIDC Protection Middleware
@app.middleware("http")
async def oidc_gate(request: Request, call_next):
    """Protect /audit and /console endpoints with OIDC when enabled"""
    if OIDC_ENABLED:
        path = request.url.path
        # Protect sensitive endpoints
        if path.startswith("/console") or path == "/audit" or path == "/ack":
            auth = request.headers.get("authorization", "")
            if not auth.lower().startswith("bearer "):
                return JSONResponse(
                    {"detail": "Missing bearer token"},
                    status_code=401
                )
            token = auth.split(" ", 1)[1]
            try:
                _ = _verify(token)
            except HTTPException as e:
                return JSONResponse(
                    {"detail": e.detail},
                    status_code=e.status_code
                )
    return await call_next(request)

# Mount SSE console for live event monitoring
if os.path.exists("/app/sse-console"):
    app.mount("/console", StaticFiles(directory="/app/sse-console", html=True), name="console")

# Configuration
AUTOHEAL_ENABLED = os.getenv("AUTOHEAL_ENABLED", "false").lower() == "true"
AUTOHEAL_DRY_RUN = os.getenv("AUTOHEAL_DRY_RUN", "true").lower() == "true"  # default safe
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")
PUBLIC_BASE_URL = os.getenv("AUTOHEAL_PUBLIC_URL", "http://localhost:9009")  # for Slack links

# Chaos-lite: Simulated failure rate for drills (0-10%)
CHAOS_FAILURE_RATE = float(os.getenv("AUTOHEAL_CHAOS_FAILURE_RATE", "0"))  # 0 = disabled, 10 = 10% fail
CHAOS_ENABLED = CHAOS_FAILURE_RATE > 0

# Cooldown per alert name (override with env if desired)
DEFAULT_COOLDOWN_SEC = int(os.getenv("AUTOHEAL_DEFAULT_COOLDOWN_SEC", "600"))
PER_ALERT_COOLDOWN_SEC = {
    "TcpEndpointDownFast": int(os.getenv("COOLDOWN_TCP_DOWN_SEC", str(DEFAULT_COOLDOWN_SEC))),
    "UptimeProbeFailing": int(os.getenv("COOLDOWN_UPTIME_FAIL_SEC", str(DEFAULT_COOLDOWN_SEC))),
    "CrmMetricsScrapeStale": int(os.getenv("COOLDOWN_SCRAPE_STALE_SEC", str(DEFAULT_COOLDOWN_SEC))),
}

# Prometheus metrics
g_enabled = Gauge("autoheal_enabled", "Whether autoheal is enabled (1/0)")
ACTION_TOTAL = Counter("autoheal_actions_total", "Autoheal actions executed", ["alertname", "result"])
ACTION_LAST_TS = Gauge("autoheal_action_last_timestamp", "Unix ts of last action", ["alertname"])
COOLDOWN_REMAINING = Gauge("autoheal_cooldown_remaining_seconds", "Cooldown remaining", ["alertname"])
AUTOHEAL_EVENT_TOTAL = Counter("autoheal_event_total", "Autoheal events by kind", ["kind"])
AUTOHEAL_ACTION_FAILURES_TOTAL = Counter("autoheal_action_failures_total", "Action failures by alertname", ["alertname"])
AUTOHEAL_LAST_EVENT_TS = Gauge("autoheal_last_event_timestamp", "Last observed autoheal event (unix ts)")

# Simple in-memory last action map
_last_action_ts: Dict[str, float] = {}

# Event bus (SSE)
_EVENT_Q: queue.Queue = queue.Queue(maxsize=1000)


def _emit(evt: Dict[str, Any]):
    """Emit event to SSE stream and audit log"""
    evt.setdefault("ts", now_ts())
    try:
        _EVENT_Q.put_nowait(evt)
    except queue.Full:
        pass
    write_event(evt)


def _cooldown_ok(alertname: str) -> bool:
    """Check if cooldown period has elapsed for this alert"""
    now = time.time()
    cd = PER_ALERT_COOLDOWN_SEC.get(alertname, DEFAULT_COOLDOWN_SEC)
    last = _last_action_ts.get(alertname, 0.0)
    rem = max(0.0, cd - (now - last))
    COOLDOWN_REMAINING.labels(alertname=alertname).set(rem)
    return rem <= 0.0


def _mark_action(alertname: str, result: str):
    """Record action execution in metrics"""
    ts = time.time()
    _last_action_ts[alertname] = ts
    ACTION_LAST_TS.labels(alertname=alertname).set(ts)
    ACTION_TOTAL.labels(alertname=alertname, result=result).inc()


def _action_for_alert(alertname: str) -> str:
    """Map alertname to remediation command"""
    if alertname == "CrmMetricsScrapeStale":
        return "docker restart crm-api"
    if alertname == "TcpEndpointDownFast":
        return "docker restart crm-api"
    if alertname == "UptimeProbeFailing":
        return "docker compose restart grafana prometheus"
    return "echo noop"


def _parse_duration(s: str) -> timedelta:
    """Parse duration string like 30m, 2h, 1d"""
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        raise ValueError("duration must be like 30m, 2h, 1d")
    qty, unit = int(m.group(1)), m.group(2)
    unit_map = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return timedelta(**{unit_map[unit]: qty})


def _create_silence(matchers: Dict[str, str], duration: str, comment: str):
    """Create silence in Alertmanager"""
    ends_at = datetime.now(timezone.utc) + _parse_duration(duration)
    payload = {
        "matchers": [{"name": k, "value": v, "isRegex": False} for k, v in matchers.items()],
        "startsAt": datetime.now(timezone.utc).isoformat(),
        "endsAt": ends_at.isoformat(),
        "createdBy": "autoheal",
        "comment": comment
    }
    r = requests.post(f"{ALERTMANAGER_URL}/api/v2/silences", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


@app.get("/")
async def root():
    """Health check endpoint"""
    g_enabled.set(1.0 if AUTOHEAL_ENABLED else 0.0)
    return {
        "status": "ok",
        "enabled": AUTOHEAL_ENABLED,
        "dry_run": AUTOHEAL_DRY_RUN,
        "chaos": {
            "enabled": CHAOS_ENABLED,
            "failure_rate_pct": CHAOS_FAILURE_RATE
        },
        "otel": {"enabled": OTEL_ENABLED},
        "oidc": {"enabled": OIDC_ENABLED},
        "actions": ["CrmMetricsScrapeStale", "TcpEndpointDownFast", "UptimeProbeFailing"],
        "public_base_url": PUBLIC_BASE_URL
    }


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    g_enabled.set(1.0 if AUTOHEAL_ENABLED else 0.0)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _iter_audit():
    """Generator to iterate audit.jsonl file"""
    try:
        with open(os.getenv("AUTOHEAL_AUDIT_PATH", "/app/audit.jsonl"), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except:
                    continue
    except FileNotFoundError:
        return

@app.get("/audit")
def audit(
    n: int = Query(200, ge=1, le=5000, description="Number of events to return"),
    since: Optional[float] = Query(None, description="Unix timestamp filter (events after)"),
    kind: Optional[str] = Query(None, description="Event kind filter"),
    alertname: Optional[str] = Query(None, description="Alert name filter"),
    contains: Optional[str] = Query(None, description="Text search in event JSON")
):
    """
    Read audit trail with optional filtering.
    Returns JSON: {"count": N, "events": [...]}
    """
    rows: List[dict] = []
    for ev in _iter_audit():
        if since and ev.get("ts", 0) < since:
            continue
        if kind and ev.get("kind") != kind:
            continue
        if alertname and ev.get("alertname") != alertname:
            continue
        if contains:
            blob = json.dumps(ev, ensure_ascii=False)
            if contains.lower() not in blob.lower():
                continue
        rows.append(ev)
    
    return {"count": len(rows[-n:]), "events": rows[-n:]}


@app.get("/events")
def sse_events():
    """Server-sent events stream for real-time autoheal events"""
    def gen():
        while True:
            evt = _EVENT_Q.get()
            AUTOHEAL_EVENT_TOTAL.labels(kind=evt.get("kind", "unknown")).inc()
            AUTOHEAL_LAST_EVENT_TS.set(evt.get("ts", now_ts()))
            yield f"data: {json.dumps(evt, separators=(',',':'))}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/alert")
async def alert_webhook(req: Request):
    """
    Receive Alertmanager webhook and execute remediation actions.
    
    Supports dry-run mode and per-alert cooldowns.
    """
    body = await req.json()
    alerts = body.get("alerts", [])
    results = []
    
    _emit({"kind": "webhook_received", "alerts": len(alerts)})
    
    for a in alerts:
        labels = a.get("labels", {})
        ann = a.get("annotations", {})
        alertname = labels.get("alertname", "")
        
        # Require opt-in
        if ann.get("autoheal", "false").lower() != "true":
            _emit({"kind": "decision_skip", "reason": "not_annotated", "alertname": alertname})
            continue
        
        # Allowlist
        if alertname not in PER_ALERT_COOLDOWN_SEC:
            _emit({"kind": "decision_skip", "reason": "not_allowlisted", "alertname": alertname})
            continue
        
        # Cooldown gate
        if not _cooldown_ok(alertname):
            _mark_action(alertname, "cooldown_skip")
            _emit({"kind": "decision_skip", "reason": "cooldown", "alertname": alertname})
            results.append({"alert": alertname, "result": "cooldown_skip"})
            continue
        
        # Execute (or dry-run)
        cmd = _action_for_alert(alertname)
        if AUTOHEAL_ENABLED and not AUTOHEAL_DRY_RUN:
            try:
                # Chaos-lite: Inject random failures for drills
                if CHAOS_ENABLED and (time.time() % 100) < CHAOS_FAILURE_RATE:
                    rc = 1  # Simulate failure
                    _mark_action(alertname, "failed")
                    AUTOHEAL_ACTION_FAILURES_TOTAL.labels(alertname=alertname).inc()
                    _emit({"kind": "action_fail", "alertname": alertname, "cmd": cmd, "rc": rc, "chaos": True})
                    results.append({"alert": alertname, "result": "chaos_injected_failure", "rc": rc})
                else:
                    rc = os.system(cmd)
                    if rc == 0:
                        _mark_action(alertname, "executed")
                        _emit({"kind": "action_ok", "alertname": alertname, "cmd": cmd})
                        results.append({"alert": alertname, "result": "executed", "rc": rc})
                    else:
                        _mark_action(alertname, "failed")
                        AUTOHEAL_ACTION_FAILURES_TOTAL.labels(alertname=alertname).inc()
                        _emit({"kind": "action_fail", "alertname": alertname, "cmd": cmd, "rc": rc})
                        results.append({"alert": alertname, "result": "failed", "rc": rc})
            except Exception as e:
                _mark_action(alertname, "error")
                AUTOHEAL_ACTION_FAILURES_TOTAL.labels(alertname=alertname).inc()
                _emit({"kind": "action_fail", "alertname": alertname, "cmd": cmd, "err": str(e)})
                results.append({"alert": alertname, "result": "error", "err": str(e)})
        else:
            _mark_action(alertname, "dry_run")
            _emit({"kind": "action_dry_run", "alertname": alertname, "cmd": cmd})
            results.append({"alert": alertname, "result": "dry_run", "cmd": cmd})
    
    return {"ok": True, "results": results}


@app.get("/ack")
def ack(labels: str, duration: str = "30m", comment: str = "Ack via Autoheal"):
    """
    Create Alertmanager silence from Slack link.
    
    Args:
        labels: URL-encoded JSON of exact label matchers, e.g. {"alertname":"TcpEndpointDownFast"}
        duration: 30m / 2h / 24h
        comment: Silence comment
    """
    try:
        matchers = json.loads(labels)
        res = _create_silence(matchers, duration, comment)
        silence_id = res.get("silenceID")
        _emit({"kind": "ack", "labels": matchers, "duration": duration, "silenceId": silence_id})
        return {"ok": True, "silenceId": silence_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9009)
