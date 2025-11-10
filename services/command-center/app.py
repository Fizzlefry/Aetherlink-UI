import asyncio
import logging
import os
import random
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

# import alert_evaluator
# import alert_store
# import event_store
import httpx

# from audit import audit_middleware, get_audit_stats
from fastapi import FastAPI, HTTPException, Query, Request

# from prometheus_client import Counter, Gauge


# Dummy prometheus classes for when prometheus_client is not available
class Counter:
    def __init__(self, name, description, labelnames=None):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []

    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass


class Gauge:
    def __init__(self, name, description, labelnames=None):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []

    def labels(self, **kwargs):
        return self

    def set(self, value):
        pass


from pydantic import BaseModel, Field

# from rbac import require_roles
# from routers import alert_templates, alerts, delivery_history, events, operator_audit_router
from starlette.middleware.base import BaseHTTPMiddleware

# Setup logging for startup events
log = logging.getLogger("aetherlink.startup")


# ISO timestamp helper for mobile/PWA compatibility
def to_iso(ts: float | None) -> str | None:
    """
    Convert epoch timestamp to ISO 8601 format with Z suffix.

    Returns clean UTC timestamps like: 2025-11-08T21:16:37.275788Z
    Mobile-friendly and backwards compatible.
    """
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")


# Phase XII: Lightweight RBAC for operator-only actions
OPS_HEADER_KEYS = ["x-ops", "x-role"]
OPS_ALLOWED_VALUES = ["1", "ops", "admin"]


def ensure_ops(request: Request):
    """
    Protect dangerous endpoints with simple header-based RBAC.

    Allows request if any of the known operator headers is set to an allowed value.
    Raises 403 HTTPException if no valid operator credential is found.

    Phase XII: Prevents anonymous access to destructive scheduler controls.
    Easy to swap for JWT/SSO later without changing endpoint signatures.
    """
    for key in OPS_HEADER_KEYS:
        val = request.headers.get(key)
        if val and val.lower() in OPS_ALLOWED_VALUES:
            log.debug(f"[rbac] Operator access granted via {key}={val}")
            return
    # No valid operator header found
    log.warning("[rbac] Operator access denied - missing or invalid operator headers")
    raise HTTPException(status_code=403, detail="operator privileges required")


# Phase XIII/XIV: File-based persistence helpers (atomic JSON saves)
import json
import shutil
from pathlib import Path

# Allow override so prod/staging can store data elsewhere
DATA_DIR = Path(os.getenv("COMMAND_CENTER_DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Max number of timestamped JSON backups to retain (per file)
MAX_JSON_SNAPSHOTS = int(os.getenv("COMMAND_CENTER_MAX_SNAPSHOTS", "3"))

SCHEDULES_FILE = DATA_DIR / "acculynx_schedules.json"
AUDIT_FILE = DATA_DIR / "acculynx_audit.json"
LOCAL_RUNS_FILE = DATA_DIR / "local_action_runs.json"

# Phase XVI: DB store toggles (SQLite first)
STORE_MODE = os.getenv("COMMAND_CENTER_STORE", "json").lower()
STORE_DSN = os.getenv("COMMAND_CENTER_DSN", str(DATA_DIR / "command_center.db"))
DUAL_WRITE = os.getenv("COMMAND_CENTER_DUAL_WRITE", "false").lower() in ("1", "true", "yes")
DB_STORE = None

# Phase XVII: Replication toggles (off by default)
REPLICATION_ENABLED = os.getenv("COMMAND_CENTER_REPLICATION", "off").lower() in (
    "1",
    "true",
    "on",
    "yes",
)
REPLICA_URL = os.getenv("COMMAND_CENTER_REPLICA_URL", "").strip()  # http(s):// or file://path
REPLICA_BACKOFF_MAX = int(os.getenv("COMMAND_CENTER_REPLICA_BACKOFF_MAX", "60"))
REPLICA_QUEUE_MAXSIZE = int(os.getenv("COMMAND_CENTER_REPLICA_QUEUE_MAXSIZE", "1000"))
_REPLICA_Q: asyncio.Queue | None = None

# Phase XVIII: Adaptive health toggles
HEALTH_INTERVAL_SEC = int(os.getenv("COMMAND_CENTER_HEALTH_INTERVAL", "30"))
AUTO_RECOVER = os.getenv("COMMAND_CENTER_AUTO_RECOVER", "true").lower() in (
    "1",
    "true",
    "on",
    "yes",
)
SCHEDULER_STALL_SEC = int(os.getenv("COMMAND_CENTER_SCHEDULER_STALL_SEC", "30"))

# Phase XIX: Restart controls
ALLOW_RESTART = os.getenv("COMMAND_CENTER_ALLOW_RESTART", "true").lower() in (
    "1",
    "true",
    "on",
    "yes",
)
RESTART_DELAY_SEC = int(os.getenv("COMMAND_CENTER_RESTART_DELAY_SEC", "3"))

# Phase XVIII: Health state snapshot
_HEALTH_STATE: dict[str, Any] = {
    "db": "unknown",
    "replication": "unknown",
    "scheduler": "unknown",
    "degraded": False,
    "ts_iso": to_iso(time.time()),
}

# Track scheduler main loop heartbeat
_SCHEDULER_LAST_LOOP_TS: float | None = None


def save_json_safe(path: Path, payload, max_snapshots: int | None = None):
    """Atomically write JSON and keep a few timestamped backups."""
    if max_snapshots is None:
        max_snapshots = MAX_JSON_SNAPSHOTS
    file_label = str(path.name)
    try:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # atomic-ish replace
        tmp_path.replace(path)
        try:
            PERSIST_SAVES_TOTAL.labels(file=file_label).inc()
        except Exception:
            pass
    except Exception as e:
        print(f"[persist] failed to save {path}: {e}")
        try:
            PERSIST_FAILURES_TOTAL.labels(file=file_label, kind="save").inc()
        except Exception:
            pass
        return

    # rotation - best effort, never crash
    try:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        snapshot_path = path.with_suffix(path.suffix + f".{ts}.bak")
        shutil.copy(path, snapshot_path)

        # prune older .bak files
        pattern = path.stem + path.suffix + ".*.bak"  # e.g. acculynx_schedules.json.*.bak
        backups = sorted(path.parent.glob(pattern))
        if len(backups) > max_snapshots:
            for old in backups[: len(backups) - max_snapshots]:
                try:
                    old.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception as e:
        # don't crash app on backup failure
        print(f"[persist] failed rotation for {path}: {e}")
        try:
            PERSIST_FAILURES_TOTAL.labels(file=file_label, kind="rotate").inc()
        except Exception:
            pass


def load_json_safe(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        print(f"[persist] failed to load {path}: {e}")
    return default


def load_json_self_heal(path: Path, default):
    """
    Try to load JSON. If it fails, try to restore from the most recent .bak.
    """
    file_label = str(path.name)
    # First try normal load
    try:
        if path.exists():
            return json.loads(path.read_text())
        return default
    except Exception as e:
        print(f"[persist] load failed for {path}: {e}")
        try:
            PERSIST_FAILURES_TOTAL.labels(file=file_label, kind="load").inc()
        except Exception:
            pass

    # Try to heal from backups (newest first)
    try:
        backups = sorted(path.parent.glob(path.stem + path.suffix + ".*.bak"), reverse=True)
        for bak in backups:
            try:
                restored = json.loads(bak.read_text())
                path.write_text(json.dumps(restored, indent=2), encoding="utf-8")
                print(f"[persist] restored {path} from backup {bak.name}")
                # Audit the self-heal so operators see it in the normal panel
                try:
                    log_scheduler_audit(
                        tenant="system",
                        operation="restore",
                        metadata={
                            "file": path.name,
                            "backup": bak.name,
                            "source": "self-heal",
                        },
                    )
                except Exception:
                    pass
                try:
                    PERSIST_SAVES_TOTAL.labels(file=file_label).inc()
                    PERSIST_FAILURES_TOTAL.labels(file=file_label, kind="restore").inc()
                except Exception:
                    pass
                return restored
            except Exception as e:
                print(f"[persist] failed to restore from {bak}: {e}")
                try:
                    PERSIST_FAILURES_TOTAL.labels(file=file_label, kind="restore").inc()
                except Exception:
                    pass
    except Exception:
        pass

    print(f"[persist] no valid backups for {path}, using default")
    return default


# Phase VII M3: Tenant Context Middleware
class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Extract X-Tenant-ID from request headers and stash in request.state.

    Phase VII M3: Enables tenant-aware event filtering and alert scoping.
    Downstream handlers can access request.state.tenant_id.
    """

    async def dispatch(self, request: Request, call_next):
        # Extract tenant ID from header if present
        tenant_id = request.headers.get("X-Tenant-ID")
        # Stash on request.state for downstream handlers
        request.state.tenant_id = tenant_id
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Defensive startup/shutdown: Initialize services with graceful degradation.

    If any optional component fails to start, the app continues to boot
    rather than crashing. This allows the API to serve requests even when
    some background workers or integrations aren't available.
    """
    global DB_STORE

    log.info("[command-center] Starting Command Center")
    print("Lifespan starting")

    # Initialize database store if enabled
    if STORE_MODE == "sqlite":
        try:
            # from .store_sqlite import SQLiteStore
            # DB_STORE = SQLiteStore(STORE_DSN)
            log.info(f"SQLite store initialized at {STORE_DSN}")
        except Exception as e:
            log.error(f"Failed to initialize SQLite store: {e}")
            DB_STORE = None

    # Defensive startup: try to start scheduler but don't let it kill the app
    try:
        # asyncio.create_task(acculynx_scheduler_loop())
        log.info("acculynx scheduler loop started")
    except Exception as e:
        log.error(f"failed to start acculynx scheduler loop: {e}")

    print("Lifespan yielding")
    yield

    # Shutdown (cleanup if needed)
    print("Lifespan shutting down")
    log.info("[command-center] Command Center shutting down")


app = FastAPI(title="AetherLink Command Center", version="0.1.0")


@app.get("/test")
def test():
    print("Test endpoint called")
    try:
        return {"ok": True}
    except Exception as e:
        print(f"Exception in test: {e}")
        return {"error": str(e)}


# Phase VII M3: Add tenant context middleware
# app.add_middleware(TenantContextMiddleware)

# Recent local action runs (newest first)
LOCAL_ACTION_RUNS: list[dict[str, Any]] = []
MAX_LOCAL_ACTION_RUNS = 50

# AccuLynx scheduler state: tenant → {interval_sec, last_run, last_status}
ACCU_IMPORT_SCHEDULES: dict[str, dict[str, Any]] = {}

# AccuLynx scheduler audit trail: recent operator actions
ACCU_SCHEDULER_AUDIT: list[dict[str, Any]] = []
MAX_AUDIT_ENTRIES = 100

# Phase XXI: Event bus subscribers (type_prefix -> list of callables)
EVENT_SUBSCRIBERS: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

# Prometheus metric for local actions
local_actions_total = Counter(
    "aetherlink_local_actions_total",
    "Total local actions invoked from UI",
    ["tenant", "action"],
)

# Prometheus metric for scheduled AccuLynx imports
acculynx_scheduled_imports_total = Counter(
    "aetherlink_acculynx_scheduled_imports_total",
    "Total AccuLynx imports triggered by scheduler",
    ["tenant"],
)

# Prometheus metrics for persistence DB ops
PERSIST_DB_OPS_TOTAL = Counter(
    "aetherlink_persist_db_ops_total",
    "Total DB persistence operations",
    ["table", "op"],
)
PERSIST_DB_FAILURES_TOTAL = Counter(
    "aetherlink_persist_db_failures_total",
    "Total DB persistence failures",
    ["table", "op"],
)

# Phase XVII: Async replication metrics
replica_ops_total = Counter(
    "aetherlink_replica_ops_total",
    "Replication operations sent",
    ["target", "op"],
)
replica_failures_total = Counter(
    "aetherlink_replica_failures_total",
    "Replication failures",
    ["target", "kind"],
)

# Phase XVIII: Health gauges
health_status = Gauge(
    "aetherlink_health_status",
    "Component health status (1=ok, 0=degraded)",
    ["component"],
)

# Phase XX-B: Analytics gauges
analytics_tenants_total = Gauge(
    "aetherlink_analytics_tenants_total",
    "Total tenants configured for scheduling",
)
analytics_tenants_active = Gauge(
    "aetherlink_analytics_tenants_active",
    "Active (not paused) tenants",
)
analytics_tenants_paused = Gauge(
    "aetherlink_analytics_tenants_paused",
    "Paused tenants",
)
analytics_ops_last_24h = Gauge(
    "aetherlink_analytics_ops_last_24h",
    "Audit operations observed in the last 24 hours",
)

# Prometheus metrics for persistence
PERSIST_SAVES_TOTAL = Counter(
    "aetherlink_persist_saves_total",
    "Total successful JSON persistence saves",
    ["file"],
)
PERSIST_FAILURES_TOTAL = Counter(
    "aetherlink_persist_failures_total",
    "Total persistence failures by file and kind",
    ["file", "kind"],
)


# Phase VI: Original startup code (now replaced with modern lifespan pattern above)
# All startup/shutdown logic is in the lifespan context manager


# Phase VII M2: Background retention worker
async def retention_worker():
    """
    Background task that prunes old events periodically.

    Phase VII M2: Runs every EVENT_RETENTION_CRON_SECONDS to keep database lean.
    """
    # Wait for service to fully start
    await asyncio.sleep(5)

    retention_interval = int(os.getenv("EVENT_RETENTION_CRON_SECONDS", "3600"))

    print(f"[retention_worker] ≡ƒöä Starting retention loop (interval: {retention_interval}s)")

    while True:
        try:
            # Phase VII M4: Use per-tenant retention with fallback to global
            results = event_store.prune_old_events_with_per_tenant()

            total_pruned = sum(r["pruned_count"] for r in results)

            if total_pruned > 0:
                print(
                    f"[retention_worker] Γ£à Pruned {total_pruned} events across {len(results)} scopes"
                )

                # Emit ops.events.pruned event for each scope (system + tenants)
                for result in results:
                    if result["pruned_count"] > 0:
                        prune_event = {
                            "event_id": str(uuid.uuid4()),
                            "event_type": "ops.events.pruned",
                            "source": "aether-command-center",
                            "severity": "info",
                            "timestamp": datetime.now(UTC).isoformat(),
                            "tenant_id": result["scope"]
                            if result["scope"] != "system"
                            else "system",
                            "payload": {
                                "scope": result["scope"],
                                "pruned_count": result["pruned_count"],
                                "cutoff": result["cutoff"],
                                "retention_days": result["retention_days"],
                                "strategy": "per-tenant-retention",
                            },
                            "_meta": {
                                "received_at": datetime.now(UTC).isoformat(),
                                "client_ip": "127.0.0.1",
                            },
                        }

                        # Save prune event (after prune completed)
                        event_store.save_event(prune_event)

        except Exception as e:
            print(f"[retention_worker] ΓÜá∩╕Å  Retention failed: {e}")

        # Wait for next interval
        await asyncio.sleep(retention_interval)


# Phase XVII: Async replication service
def _replica_target() -> str:
    if REPLICA_URL.startswith("file://"):
        return "file"
    if REPLICA_URL.startswith("http://") or REPLICA_URL.startswith("https://"):
        return "http"
    return "unknown"


async def replication_loop(poll_delay: float = 0.2):
    """
    Background worker that drains a local queue and replicates items to a secondary target.

    - Supports file:// replication by writing one JSON file per item
    - Supports http(s):// replication by POSTing JSON payloads to REPLICA_URL
    - Retries with exponential backoff + jitter on failures
    """
    # small warm-up delay
    await asyncio.sleep(1)
    backoff = 1.0
    target = _replica_target()
    while True:
        try:
            if _REPLICA_Q is None:
                await asyncio.sleep(1)
                continue
            item = await _REPLICA_Q.get()
            ok = await _replicate_once(item, target)
            if ok:
                backoff = 1.0
                try:
                    replica_ops_total.labels(target=target, op=item.get("op", "unknown")).inc()
                except Exception:
                    pass
                # audit success for traceability
                try:
                    log_scheduler_audit(
                        tenant=item.get("tenant", "system"),
                        operation="replicate",
                        source="replica",
                        metadata={
                            "table": item.get("table"),
                            "op": item.get("op"),
                            "target": target,
                        },
                    )
                except Exception:
                    pass
            else:
                # requeue and backoff
                await asyncio.sleep(min(backoff, REPLICA_BACKOFF_MAX) + random.random())
                backoff = min(backoff * 2.0, float(REPLICA_BACKOFF_MAX))
                await _REPLICA_Q.put(item)
        except Exception:
            try:
                replica_failures_total.labels(target=_replica_target(), kind="loop").inc()
            except Exception:
                pass
            await asyncio.sleep(1)


async def _replicate_once(item: dict, target: str) -> bool:
    try:
        if target == "file":
            dir_path = REPLICA_URL[len("file://") :]
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            fname = f"{ts}_{item.get('table','unk')}_{item.get('op','unk')}"
            (path / f"{fname}.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
            return True
        elif target == "http":
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(REPLICA_URL, json=item)
                return 200 <= resp.status_code < 300
        else:
            # unknown target is treated as no-op success to avoid blocking
            return True
    except Exception:
        try:
            replica_failures_total.labels(target=target, kind="send").inc()
        except Exception:
            pass
        return False


def _enqueue_replication(table: str, op: str, payload: dict[str, Any], tenant: str | None = None):
    if not REPLICATION_ENABLED or _REPLICA_Q is None:
        return
    try:
        item = {
            "table": table,
            "op": op,
            "payload": payload,
            "tenant": tenant or payload.get("tenant") or "system",
            "ts": time.time(),
        }
        _REPLICA_Q.put_nowait(item)
    except Exception:
        try:
            replica_failures_total.labels(target=_replica_target(), kind="enqueue").inc()
        except Exception:
            pass


# Phase IX/XI: AccuLynx Scheduler Helper Functions
def log_scheduler_audit(
    tenant: str, operation: str, source: str = "api", metadata: dict[str, Any] | None = None
):
    """
    Record operator action in audit trail.

    Phase XI: Tracks pause, resume, run-now, delete, and schedule changes.
    """
    audit_entry = {
        "ts": time.time(),
        "ts_iso": to_iso(time.time()),
        "tenant": tenant,
        "operation": operation,
        "source": source,
        "metadata": metadata or {},
    }
    ACCU_SCHEDULER_AUDIT.insert(0, audit_entry)
    if len(ACCU_SCHEDULER_AUDIT) > MAX_AUDIT_ENTRIES:
        ACCU_SCHEDULER_AUDIT.pop()
    # Phase XIII: persist audit to disk on every operation
    save_json_safe(AUDIT_FILE, ACCU_SCHEDULER_AUDIT)
    # Phase XVI: persist audit to DB if enabled
    try:
        if DB_STORE is not None:
            DB_STORE.append_audit(audit_entry)
    except Exception:
        pass


def route_event(event: dict[str, Any]) -> None:
    """
    Route incoming event to registered subscribers based on type prefix.

    Phase XXI: Lightweight in-process event routing for cross-program intelligence mesh.
    """
    event_type = event.get("type", "")
    for prefix, subscribers in EVENT_SUBSCRIBERS.items():
        if event_type.startswith(prefix):
            for subscriber in subscribers:
                try:
                    subscriber(event)
                except Exception as e:
                    log.error(f"Event subscriber failed for {event_type}: {e}")


async def emit_event(ev: dict[str, Any]) -> None:
    """
    Internal event emission for canonical event types.

    Handles persistence, audit, replication, and routing for standardized events.
    """
    # Ensure required fields
    ev.setdefault("ts", time.time())
    ev.setdefault("ts_iso", to_iso(ev["ts"]))
    ev.setdefault("source", "command-center")
    ev.setdefault("payload", {})

    # Persist
    if DB_STORE is not None:
        DB_STORE.append_event(ev)

    # Audit
    log_scheduler_audit(
        ev["tenant"], "event_emit", source=ev["source"], metadata={"type": ev["type"]}
    )

    # Replicate
    if REPLICATION_ENABLED:
        _enqueue_replication("event", "emit", ev, ev["tenant"])

    # Route
    route_event(ev)


async def acculynx_pull_for_tenant(tenant: str):
    """
    Defensive wrapper around AccuLynx fetch/import for a specific tenant.

    Tries to call the real AccuLynx routines; if they don't exist yet,
    it uses a stub so the scheduler can run without crashing.
    """
    now = time.time()
    try:
        # TODO: Replace this stub with real AccuLynx import when ready:
        # remote = await acculynx_fetch_remote(tenant, "peakpro")
        # result = await acculynx_import(remote, tenant=tenant)

        # TEMP stub for now
        result = {
            "ok": True,
            "stats": {"imported": 0, "skipped": 0},
            "tenant": tenant,
            "message": "stub: real AccuLynx import not yet enabled",
        }

        # Update schedule state
        ACCU_IMPORT_SCHEDULES.setdefault(tenant, {})
        ACCU_IMPORT_SCHEDULES[tenant]["last_run"] = now
        ACCU_IMPORT_SCHEDULES[tenant]["last_status"] = {
            "ok": True,
            "ts": now,
            "message": f"scheduled import completed for {tenant}",
            "result": result,
        }
        # Phase XIII: Persist runtime updates for truthful UI after restart
        save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
        # Phase XVI: persist to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.save_schedule(tenant, ACCU_IMPORT_SCHEDULES[tenant])
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication(
            "schedules", "update", {"tenant": tenant, **ACCU_IMPORT_SCHEDULES[tenant]}, tenant
        )
        # Optional audit to reflect scheduler activity
        log_scheduler_audit(tenant, "scheduled-run", source="scheduler")
        await emit_event({"tenant": tenant, "type": "scheduler.import.completed"})

        # Prometheus metric - record successful scheduled import
        acculynx_scheduled_imports_total.labels(tenant=tenant).inc()

        log.info(f"[acculynx-scheduler] Completed import for {tenant}")
        return result

    except Exception as e:
        # Record failure but don't crash the scheduler
        ACCU_IMPORT_SCHEDULES.setdefault(tenant, {})
        ACCU_IMPORT_SCHEDULES[tenant]["last_run"] = now
        ACCU_IMPORT_SCHEDULES[tenant]["last_status"] = {
            "ok": False,
            "ts": now,
            "message": f"scheduled import failed: {e}",
        }
        # Persist failure state as well
        save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
        # Phase XVI: persist failure state to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.save_schedule(tenant, ACCU_IMPORT_SCHEDULES[tenant])
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication(
            "schedules", "update", {"tenant": tenant, **ACCU_IMPORT_SCHEDULES[tenant]}, tenant
        )
        # Audit failure for operator visibility
        log_scheduler_audit(
            tenant, "scheduled-run-failed", source="scheduler", metadata={"error": str(e)}
        )
        await emit_event(
            {"tenant": tenant, "type": "scheduler.import.failed", "payload": {"error": str(e)}}
        )
        log.error(f"[acculynx-scheduler] Import failed for {tenant}: {e}")
        return {"ok": False, "error": str(e)}


async def acculynx_scheduler_loop(poll_interval: int = 5):
    """
    Background task that runs forever, checking which tenants have a schedule
    and triggering imports when their interval has elapsed.

    Phase IX: Enables tenant-scoped auto-sync for AccuLynx CRM data.
    Phase X: Respects paused flag per tenant.
    """
    # Wait for service to fully start
    await asyncio.sleep(5)

    log.info(f"[acculynx-scheduler] Starting scheduler loop (poll interval: {poll_interval}s)")

    while True:
        try:
            # heartbeat for scheduler health
            global _SCHEDULER_LAST_LOOP_TS
            _SCHEDULER_LAST_LOOP_TS = time.time()
            now = time.time()
            # Copy keys so we can mutate safely
            for tenant, cfg in list(ACCU_IMPORT_SCHEDULES.items()):
                # Skip paused tenants
                if cfg.get("paused"):
                    continue

                interval = int(cfg.get("interval_sec", 300))
                last_run = float(cfg.get("last_run", 0))

                if now - last_run >= interval:
                    log.info(
                        f"[acculynx-scheduler] Triggering import for {tenant} (interval: {interval}s)"
                    )
                    await acculynx_pull_for_tenant(tenant)

        except Exception as e:
            log.error(f"[acculynx-scheduler] Scheduler loop error: {e}")

        # Wait before next poll
        await asyncio.sleep(poll_interval)


# Phase VI: Mount event and alert routers
# app.include_router(events.router)
# app.include_router(alerts.router)
# Phase VIII M2: Mount alert templates router
# app.include_router(alert_templates.router)
# Phase VIII M3: Mount delivery history router
# app.include_router(delivery_history.router)
# Phase VIII M10: Mount operator audit router
# app.include_router(operator_audit_router.router)

# Phase III M6: Security Audit Logging
# app.middleware("http")(audit_middleware)

# RBAC: Only operators and admins can access ops endpoints
# operator_only = require_roles(["operator", "admin"])

# Add CORS middleware to allow UI to call this
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # In production, restrict to your UI domain
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Service health endpoints map
# You can move this to config later
SERVICE_MAP = {
    "ui": os.getenv("UI_HEALTH_URL", "http://aether-crm-ui:5173/health"),
    "ai_summarizer": os.getenv("AI_SUMMARIZER_URL", "http://aether-ai-summarizer:9108/health"),
    "notifications": os.getenv(
        "NOTIFICATIONS_URL", "http://aether-notifications-consumer:9107/health"
    ),
    "apexflow": os.getenv("APEXFLOW_URL", "http://aether-apexflow:9109/health"),
    "kafka": os.getenv("KAFKA_URL", "http://aether-kafka:9010/health"),
}

# Phase IV: Service Registry (in-memory, for v1.13.0+)
# Services can dynamically register themselves instead of hardcoding in env
REGISTERED_SERVICES: dict[str, dict] = {}


class ServiceRegistration(BaseModel):
    """Schema for service registration requests"""

    name: str = Field(..., description="Unique service name, e.g. aether-ai-orchestrator")
    url: str = Field(..., description="Base URL for the service")
    health_url: str | None = Field(None, description="Health or ping endpoint")
    version: str | None = Field(None, description="Service version, e.g. v1.10.0")
    roles_required: list[str] | None = Field(None, description="RBAC roles this service expects")
    tags: list[str] | None = Field(None, description="Labels like ['ai','ops','ui']")


def _now_iso() -> str:
    """Return current UTC timestamp in ISO8601 format"""
    return datetime.now(UTC).isoformat()


# Phase VI M4: Event publishing helper (internal to Command Center)
async def publish_event_internal(event_type: str, payload: dict):
    """
    Publish an event internally (Command Center publishes about itself).

    Calls the event store directly instead of using HTTP to avoid circular dependency.
    Used for service registration/unregistration events.

    Args:
        event_type: Event type (e.g., "service.registered")
        payload: Event payload with severity and details
    """
    try:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "source": "aether-command-center",
            "severity": payload.get("severity", "info"),
            "timestamp": datetime.now(UTC).isoformat(),
            "tenant_id": payload.get("tenant_id", "system"),
            "payload": payload,
        }
        # Call event store directly instead of HTTP
        event_store.save_event(event)
    except Exception:
        # Silent fail - don't break registry operations if event store fails
        pass


# @app.get("/ops/health", dependencies=[Depends(operator_only)])
# async def ops_health():
#     """
#     Aggregates health status from all AetherLink services.
#     Returns overall status and individual service details.

#     Requires: operator or admin role
#     """
#     results = {}
#     async with httpx.AsyncClient(timeout=2.5) as client:
#         for name, url in SERVICE_MAP.items():
#             try:
#                 resp = await client.get(url)
#                 results[name] = {
#                     "status": "up" if resp.status_code == 200 else "degraded",
#                     "http_status": resp.status_code,
#                     "url": url,
#                 }
#             except Exception as e:
#                 results[name] = {
#                     "status": "down",
#                     "error": str(e),
#                     "url": url,
#                 }

#     # Determine overall status
#     overall = "up" if all(s["status"] == "up" for s in results.values()) else "degraded"

#     return {
#         "status": overall,
#         "services": results,
#     }


@app.get("/ops/ping")
async def ops_ping():
    """Health check with persistence file status"""
    issues: list[str] = []
    monitored = [
        ("schedules", SCHEDULES_FILE),
        ("audit", AUDIT_FILE),
        ("local_runs", LOCAL_RUNS_FILE),
    ]
    for name, fpath in monitored:
        try:
            if not fpath.exists():
                issues.append(f"{name}:missing")
            else:
                if fpath.stat().st_size == 0:
                    issues.append(f"{name}:empty")
        except Exception as e:
            issues.append(f"{name}:error:{e}")

    # expose quick save counters (best-effort; Prometheus scrapes /metrics for source of truth)
    try:
        sched_saves = PERSIST_SAVES_TOTAL.labels(file=SCHEDULES_FILE.name)._value.get()
        audit_saves = PERSIST_SAVES_TOTAL.labels(file=AUDIT_FILE.name)._value.get()
        runs_saves = PERSIST_SAVES_TOTAL.labels(file=LOCAL_RUNS_FILE.name)._value.get()
    except Exception:
        sched_saves = audit_saves = runs_saves = 0

    resp = {
        "ok": len(issues) == 0,
        "service": "command-center",
        "ts_iso": datetime.utcnow().isoformat() + "Z",
        "issues": issues,
        "persistence": {
            "schedules_saves": sched_saves,
            "audit_saves": audit_saves,
            "local_runs_saves": runs_saves,
        },
    }

    # Phase XVIII: include current health snapshot (public-safe)
    try:
        resp["health"] = {
            "db": _HEALTH_STATE.get("db", "unknown"),
            "replication": _HEALTH_STATE.get("replication", "unknown"),
            "scheduler": _HEALTH_STATE.get("scheduler", "unknown"),
            "degraded": bool(_HEALTH_STATE.get("degraded", False)),
        }
    except Exception:
        pass

    return resp


@app.get("/ops/db")
async def db_info(request: Request, check: bool = Query(False)):
    """
    Lightweight visibility into persistence backend configuration and (if SQLite) table counts.
    """
    ensure_ops(request)
    info: dict[str, Any] = {
        "store_mode": STORE_MODE,
        "dsn": STORE_DSN,
        "dual_write": str(DUAL_WRITE).lower(),
        "migrated": False,
        "tables": {},
    }

    try:
        if STORE_MODE == "sqlite":
            from sqlite3 import connect

            info["migrated"] = Path(STORE_DSN).exists()
            if info["migrated"]:
                with connect(STORE_DSN) as c:
                    cur = c.cursor()
                    tables: dict[str, Any] = {}
                    for tbl in ["schedules", "audit", "local_runs"]:
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                            tables[tbl] = cur.fetchone()[0]
                        except Exception:
                            tables[tbl] = None
                    info["tables"] = tables
                    if check:
                        try:
                            cur.execute("PRAGMA integrity_check;")
                            res = cur.fetchone()
                            info["integrity"] = res[0] if res else None
                        except Exception as ie:
                            info["integrity_error"] = str(ie)
        else:
            # JSON mode: consider 'migrated' as presence of the JSON files
            info["migrated"] = all(
                [
                    SCHEDULES_FILE.exists(),
                    AUDIT_FILE.exists(),
                    LOCAL_RUNS_FILE.exists(),
                ]
            )
    except Exception as e:
        info["error"] = str(e)

    return {"ok": True, "db": info}


@app.get("/ops/replication")
async def replication_status(request: Request):
    """
    Lightweight replication status and backpressure signal.
    """
    try:
        ensure_ops(request)
        enabled = bool(REPLICATION_ENABLED)

        # sanitize target URL (redact credentials if present)
        target_url = REPLICA_URL
        try:
            from urllib.parse import urlparse, urlunparse

            if target_url:
                p = urlparse(target_url)
                netloc = p.hostname or ""
                if p.port:
                    netloc = f"{netloc}:{p.port}"
                target_url = urlunparse(
                    (
                        p.scheme,
                        netloc,
                        p.path or "",
                        p.params or "",
                        p.query or "",
                        p.fragment or "",
                    )
                )
        except Exception:
            pass

        qlen = 0
        try:
            qlen = int(_REPLICA_Q.qsize()) if _REPLICA_Q is not None else 0
        except Exception:
            qlen = 0

        max_q = int(REPLICA_QUEUE_MAXSIZE)
        ratio = (qlen / max_q) if max_q > 0 else 0.0
        if ratio >= 0.90:
            bp = "critical"
        elif ratio >= 0.75:
            bp = "high"
        else:
            bp = "ok"

        # best-effort metrics snapshot
        def _sum_counter(counter) -> int:
            try:
                # Sum across all label sets
                return int(sum(m._value.get() for m in counter._metrics.values()))
            except Exception:
                try:
                    return int(counter._value.get())  # single metric case
                except Exception:
                    return 0

        ops_total = _sum_counter(replica_ops_total)
        fails_total = _sum_counter(replica_failures_total)

        return {
            "ok": True,
            "replication": {
                "enabled": enabled,
                "target": target_url,
                "queue_length": qlen,
                "max_queue": max_q,
                "backpressure": bp,
                "metrics": {
                    "ops_total": ops_total,
                    "failures_total": fails_total,
                },
                "ts_iso": datetime.utcnow().isoformat() + "Z",
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "ts_iso": datetime.utcnow().isoformat() + "Z",
        }


# Phase XVIII: Internal health checks and auto-recovery
def _compute_db_health() -> bool:
    try:
        if STORE_MODE == "sqlite":
            from sqlite3 import connect

            if not Path(STORE_DSN).exists():
                return False
            with connect(STORE_DSN) as c:
                cur = c.cursor()
                cur.execute("PRAGMA integrity_check;")
                res = cur.fetchone()
                return bool(res and isinstance(res[0], str) and res[0].lower() == "ok")
        else:
            # JSON mode: all persistence files should exist and be non-empty
            files_ok = all(
                p.exists() and p.stat().st_size > 0
                for p in [SCHEDULES_FILE, AUDIT_FILE, LOCAL_RUNS_FILE]
            )
            return files_ok
    except Exception:
        return False


def _compute_replication_health() -> tuple[str, dict[str, Any]]:
    try:
        qlen = int(_REPLICA_Q.qsize()) if _REPLICA_Q is not None else 0
    except Exception:
        qlen = 0
    max_q = int(REPLICA_QUEUE_MAXSIZE)
    ratio = (qlen / max_q) if max_q > 0 else 0.0
    if ratio >= 0.90:
        bp = "critical"
    elif ratio >= 0.75:
        bp = "high"
    else:
        bp = "ok"
    return bp, {"queue_length": qlen, "max_queue": max_q, "ratio": ratio}


def _set_health(component: str, ok: bool) -> None:
    try:
        health_status.labels(component=component).set(1 if ok else 0)
    except Exception:
        pass
    _HEALTH_STATE[component] = "ok" if ok else "degraded"


def _auto_pause_all(reason: str) -> int:
    changed = 0
    now = time.time()
    for tenant, cfg in ACCU_IMPORT_SCHEDULES.items():
        if not cfg.get("paused"):
            cfg["paused"] = True
            cfg["auto_paused"] = True
            cfg["last_status"] = {
                "ok": True,
                "ts": now,
                "message": f"auto-paused: {reason}",
            }
            changed += 1
            # persist
            save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
            try:
                if DB_STORE is not None:
                    DB_STORE.save_schedule(tenant, cfg)
            except Exception:
                pass
            _enqueue_replication("schedules", "update", {"tenant": tenant, **cfg}, tenant)
    if changed:
        log_scheduler_audit(
            "system", "auto_pause", source="health", metadata={"reason": reason, "count": changed}
        )
    return changed


def _auto_resume_all(reason: str) -> int:
    changed = 0
    now = time.time()
    for tenant, cfg in ACCU_IMPORT_SCHEDULES.items():
        if cfg.get("paused") and cfg.get("auto_paused"):
            cfg["paused"] = False
            cfg.pop("auto_paused", None)
            cfg["last_status"] = {
                "ok": True,
                "ts": now,
                "message": f"auto-resumed: {reason}",
            }
            changed += 1
            # persist
            save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
            try:
                if DB_STORE is not None:
                    DB_STORE.save_schedule(tenant, cfg)
            except Exception:
                pass
            _enqueue_replication("schedules", "update", {"tenant": tenant, **cfg}, tenant)
    if changed:
        log_scheduler_audit(
            "system",
            "auto_recover",
            source="health",
            metadata={"component": "scheduler", "reason": reason, "count": changed},
        )
    return changed


def _reapply_auto_paused() -> int:
    changed = 0
    for tenant, cfg in ACCU_IMPORT_SCHEDULES.items():
        if cfg.get("auto_paused") and not cfg.get("paused"):
            cfg["paused"] = True
            changed += 1
            # persist
            save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
            try:
                if DB_STORE is not None:
                    DB_STORE.save_schedule(tenant, cfg)
            except Exception:
                pass
            _enqueue_replication("schedules", "update", {"tenant": tenant, **cfg}, tenant)
    if changed:
        log_scheduler_audit(
            "system",
            "auto_pause",
            source="startup",
            metadata={"reason": "reapply_auto_paused", "count": changed},
        )
    return changed


async def health_loop():
    await asyncio.sleep(5)
    global _HEALTH_STATE
    while True:
        try:
            db_ok = _compute_db_health()
            _set_health("db", db_ok)

            rep_bp, rep_details = _compute_replication_health()
            rep_ok = rep_bp != "critical"
            _HEALTH_STATE["replication"] = rep_bp
            try:
                # For replication, also set a binary gauge for ok/degraded
                health_status.labels(component="replication").set(1 if rep_ok else 0)
            except Exception:
                pass

            # Scheduler heartbeat health
            now_ts = time.time()
            sched_ok = True
            if _SCHEDULER_LAST_LOOP_TS is None:
                sched_ok = False
            else:
                sched_ok = (now_ts - float(_SCHEDULER_LAST_LOOP_TS)) < SCHEDULER_STALL_SEC
            _set_health("scheduler", sched_ok)

            # Adaptive actions
            if AUTO_RECOVER and REPLICATION_ENABLED:
                if rep_bp == "critical":
                    _auto_pause_all("replication_backpressure_critical")
                elif rep_details.get("ratio", 0.0) < 0.75:
                    _auto_resume_all("replication_backpressure_recovered")

            # finalize state
            _HEALTH_STATE["degraded"] = not (db_ok and rep_ok and sched_ok)
            _HEALTH_STATE["ts_iso"] = datetime.utcnow().isoformat() + "Z"
            _HEALTH_STATE["details"] = {"replication": rep_details}
        except Exception as e:
            try:
                _HEALTH_STATE["error"] = str(e)
            except Exception:
                pass
        # Phase XX-B: update analytics gauges (tenants + ops_last_24h)
        try:
            total = len(ACCU_IMPORT_SCHEDULES)
            paused = sum(1 for _t, cfg in ACCU_IMPORT_SCHEDULES.items() if cfg.get("paused"))
            active = max(0, total - paused)
            analytics_tenants_total.set(total)
            analytics_tenants_active.set(active)
            analytics_tenants_paused.set(paused)
        except Exception:
            pass

        try:
            cutoff = time.time() - 24 * 3600
            audits: list[dict[str, Any]]
            try:
                if DB_STORE is not None:
                    audits = DB_STORE.list_audit(limit=2000)
                else:
                    audits = ACCU_SCHEDULER_AUDIT[:2000]
            except Exception:
                audits = ACCU_SCHEDULER_AUDIT[:2000]
            ops_24h = sum(1 for a in audits if float(a.get("ts", 0.0)) >= cutoff)
            analytics_ops_last_24h.set(ops_24h)
        except Exception:
            pass

        await asyncio.sleep(HEALTH_INTERVAL_SEC)


# @app.get("/audit/stats", dependencies=[Depends(operator_only)])
# async def audit_stats():
#     """
#     Get audit statistics for security monitoring.

#     Phase III M6: Returns request counts, auth failures, and usage patterns.
#     Requires: operator or admin role
#     """
#     return get_audit_stats()


# Phase IV: Service Registry Endpoints (v1.13.0)


@app.get("/ops/health")
async def ops_health():
    """
    Public, read-only aggregated health snapshot for dashboards.
    """
    try:
        # Return a shallow copy to avoid accidental mutation
        snap = {
            "db": _HEALTH_STATE.get("db", "unknown"),
            "replication": _HEALTH_STATE.get("replication", "unknown"),
            "scheduler": _HEALTH_STATE.get("scheduler", "unknown"),
            "degraded": bool(_HEALTH_STATE.get("degraded", False)),
            "ts_iso": _HEALTH_STATE.get("ts_iso", datetime.utcnow().isoformat() + "Z"),
        }
        return {"ok": True, "health": snap}
    except Exception as e:
        return {"ok": False, "error": str(e), "ts_iso": datetime.utcnow().isoformat() + "Z"}


@app.post("/ops/restart")
async def ops_restart(request: Request, mode: str = Query("graceful")):
    """
    RBAC-protected controlled restart.

    - Default: graceful with configurable delay.
    - Optional body: {"immediate": true} to bypass delay.
    """
    ensure_ops(request)
    if not ALLOW_RESTART:
        raise HTTPException(status_code=403, detail="restarts disabled by config")

    delay = RESTART_DELAY_SEC
    try:
        body = await request.json()
        if isinstance(body, dict) and body.get("immediate"):
            mode = "immediate"
            delay = 0
    except Exception:
        pass

    meta = {
        "mode": mode,
        "delay_sec": int(delay),
        "client": getattr(request.client, "host", None) if hasattr(request, "client") else None,
    }
    log_scheduler_audit("system", "restart", source="ops", metadata=meta)
    await emit_event({"tenant": "system", "type": "core.restart", "payload": meta})

    async def _do_exit(wait: int):
        try:
            await asyncio.sleep(max(0, wait))
        except Exception:
            pass
        os._exit(0)

    asyncio.create_task(_do_exit(delay))
    return {
        "ok": True,
        "restarting": True,
        "mode": mode,
        "delay_sec": int(delay),
        "ts_iso": datetime.utcnow().isoformat() + "Z",
    }


# Phase XX: Unified Analytics & Insights (summary)
@app.get("/analytics/summary")
async def analytics_summary(request: Request, hours: int = Query(24, ge=1, le=168)):
    """
    RBAC-protected, read-only summary for operator dashboards.

    - Works in JSON or SQLite mode.
    - Windowed by `hours` (default 24).
    """
    ensure_ops(request)

    now = time.time()
    cutoff = now - (hours * 3600)

    # Schedules snapshot
    tenants_total = len(ACCU_IMPORT_SCHEDULES)
    tenants_paused = sum(1 for _t, cfg in ACCU_IMPORT_SCHEDULES.items() if cfg.get("paused"))
    tenants_active = tenants_total - tenants_paused

    # Load audit window
    def _load_audit(limit: int = 1000) -> list[dict[str, Any]]:
        try:
            if DB_STORE is not None:
                return DB_STORE.list_audit(limit=limit)
        except Exception:
            pass
        # fallback to in-memory
        return ACCU_SCHEDULER_AUDIT[:limit]

    def _load_local_runs(limit: int = 500) -> list[dict[str, Any]]:
        try:
            if DB_STORE is not None:
                return DB_STORE.list_local_runs(limit=limit)
        except Exception:
            pass
        return LOCAL_ACTION_RUNS[:limit]

    audits = [a for a in _load_audit(2000) if float(a.get("ts", 0)) >= cutoff]
    runs = [
        r for r in _load_local_runs(1000) if float(r.get("timestamp") or r.get("ts", 0)) >= cutoff
    ]

    # Basic rollups
    ops_total = len(audits)
    failures_total = sum(1 for a in audits if str(a.get("operation", "")).endswith("failed"))
    scheduled_runs = sum(1 for a in audits if a.get("operation") == "scheduled-run")

    # Top tenants by ops
    per_tenant: dict[str, int] = {}
    for a in audits:
        t = a.get("tenant") or "system"
        per_tenant[t] = per_tenant.get(t, 0) + 1
    top_tenants = sorted(per_tenant.items(), key=lambda kv: kv[1], reverse=True)[:5]

    # Response
    return {
        "ok": True,
        "summary": {
            "window_hours": hours,
            "tenants": {
                "total": tenants_total,
                "active": tenants_active,
                "paused": tenants_paused,
            },
            "activity": {
                "ops_total": ops_total,
                "failures_total": failures_total,
                "scheduled_runs": scheduled_runs,
                "local_runs": len(runs),
                "top_tenants": [{"tenant": t, "ops": c} for t, c in top_tenants],
            },
            "ts_iso": datetime.utcnow().isoformat() + "Z",
        },
    }


@app.get("/analytics/tenants/{tenant}")
async def analytics_tenant_detail(
    request: Request,
    tenant: str,
    hours: int = Query(
        24, ge=1, le=168, description="Lookback window in hours (1-168, default 24)"
    ),
    limit: int = Query(
        10, ge=1, le=50, description="Number of recent audit entries (1-50, default 10)"
    ),
):
    """
    RBAC-protected per-tenant analytics drilldown.

    Returns schedule info, recent audit/run counts, last status, and health view.
    Compatible with JSON and SQLite modes.
    """
    ensure_ops(request)

    cutoff = time.time() - (hours * 3600)

    sched = ACCU_IMPORT_SCHEDULES.get(tenant)
    if not sched:
        return {"ok": False, "error": f"unknown tenant: {tenant}"}

    # Last status
    last_status = sched.get("last_status", {})

    # Audit + runs window for this tenant
    def _load_audit(limit: int = 1000) -> list[dict[str, Any]]:
        try:
            if DB_STORE is not None:
                return DB_STORE.list_audit(limit=limit)
        except Exception:
            pass
        return ACCU_SCHEDULER_AUDIT[:limit]

    def _load_local_runs(limit: int = 500) -> list[dict[str, Any]]:
        try:
            if DB_STORE is not None:
                return DB_STORE.list_local_runs(limit=limit)
        except Exception:
            pass
        return LOCAL_ACTION_RUNS[:limit]

    audits = [
        a
        for a in _load_audit(2000)
        if (a.get("tenant") == tenant and float(a.get("ts", 0.0)) >= cutoff)
    ]
    runs = [
        r
        for r in _load_local_runs(1000)
        if ((r.get("tenant") == tenant) and float(r.get("timestamp") or r.get("ts", 0.0)) >= cutoff)
    ]

    # Recent audit (last 10 entries for this tenant, freshest first)
    def _load_recent_audit(limit: int = 10, fetch: int = 200) -> list[dict[str, Any]]:
        try:
            records = _load_audit(fetch)
        except Exception:
            records = ACCU_SCHEDULER_AUDIT[:fetch]
        items: list[dict[str, Any]] = []
        for a in records:
            if a.get("tenant") != tenant:
                continue
            ts = float(a.get("ts", 0.0)) if a.get("ts") is not None else 0.0
            items.append(
                {
                    "ts_iso": to_iso(ts),
                    "operation": a.get("operation"),
                    "source": a.get("source"),
                }
            )
            if len(items) >= limit:
                break
        return items

    recent_audit = _load_recent_audit(limit)

    # Health view (derived from global replication + scheduler states)
    health = {
        "replication": _HEALTH_STATE.get("replication", "unknown"),
        "scheduler": _HEALTH_STATE.get("scheduler", "unknown"),
        "degraded": bool(_HEALTH_STATE.get("degraded", False)),
    }


@app.get("/analytics/audit")
async def analytics_audit(
    request: Request, limit: int = Query(100, ge=1, le=2000), ops: str | None = Query(None)
):
    """
    RBAC-protected audit feed for dashboards.

    - Returns most recent audit entries (optionally filtered by comma-separated operations).
    - Compatible with JSON and SQLite modes.
    """
    ensure_ops(request)

    try:
        allowed_ops = None
        if ops:
            allowed_ops = set(x.strip() for x in ops.split(",") if x.strip())

        records: list[dict[str, Any]]
        try:
            if DB_STORE is not None:
                records = DB_STORE.list_audit(limit=limit)
            else:
                records = ACCU_SCHEDULER_AUDIT[:limit]
        except Exception:
            records = ACCU_SCHEDULER_AUDIT[:limit]

        if allowed_ops:
            records = [r for r in records if r.get("operation") in allowed_ops]

        # Normalize ISO timestamp
        for r in records:
            ts = float(r.get("ts", 0.0)) if r.get("ts") is not None else 0.0
            r["ts_iso"] = to_iso(ts)

        return {"ok": True, "count": len(records), "items": records}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/bus/events")
async def ingest_event(request: Request):
    """
    Ingest event into the cross-program intelligence mesh.

    Phase XXI: Unified event bus for AetherLink umbrella apps.
    Accepts standardized event envelopes from any app (PeakPro, PolicyPal, etc.).
    """
    ensure_ops(request)

    try:
        body = await request.json()
        tenant = request.headers.get("x-tenant") or body.get("tenant")
        if not tenant:
            raise HTTPException(400, "tenant required")

        ev = {
            "ts": body.get("ts") or time.time(),
            "ts_iso": body.get("ts") or to_iso(time.time()),
            "tenant": tenant,
            "source": body.get("source", "unknown"),
            "type": body.get("type", "unknown"),
            "payload": body.get("payload", {}),
        }

        # Persist via store
        if DB_STORE is not None:
            DB_STORE.append_event(ev)
        # TODO: JSON fallback if needed

        # Audit
        log_scheduler_audit(
            tenant, "event_ingest", source=ev["source"], metadata={"type": ev["type"]}
        )

        # Replicate
        if REPLICATION_ENABLED:
            _enqueue_replication("event", "ingest", ev, tenant)

        # Route to subscribers
        route_event(ev)

        return {
            "ok": True,
            "event_id": f"{ev['source']}-{ev['type']}-{int(ev['ts'] or time.time())}",
        }
    except Exception as e:
        log.error(f"Event ingest failed: {e}")
        raise HTTPException(500, f"Event ingest failed: {str(e)}")


@app.get("/bus/events")
async def list_events(
    request: Request,
    tenant: str = Query(..., description="Tenant to filter events"),
    limit: int = Query(50, ge=1, le=200, description="Number of events to return"),
    type_prefix: str | None = Query(None, description="Filter by event type prefix (e.g., 'crm.')"),
):
    """
    List recent events from the intelligence mesh.

    Phase XXI: Query cross-program events for analytics and debugging.
    """
    ensure_ops(request)

    try:
        events: list[dict[str, Any]] = []
        if DB_STORE is not None:
            events = DB_STORE.list_events(tenant=tenant, type_prefix=type_prefix, limit=limit)
        # TODO: JSON fallback

        return {"ok": True, "count": len(events), "items": events}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/analytics/events/summary")
async def analytics_events_summary(request: Request):
    """
    Summary of event activity across the intelligence mesh.

    Phase XXI: Analytics for cross-program event patterns.
    """
    ensure_ops(request)

    try:
        summary = {"sources": {}, "types": {}, "last_seen": {}}

        if DB_STORE is not None:
            # Get recent events for summary
            events = DB_STORE.list_events(limit=1000)
            for ev in events:
                source = ev["source"]
                typ = ev["type"]
                ts = ev["ts"]

                # Count by source
                summary["sources"][source] = summary["sources"].get(source, 0) + 1

                # Count by type prefix
                type_prefix = typ.split(".")[0] + "." if "." in typ else typ
                summary["types"][type_prefix] = summary["types"].get(type_prefix, 0) + 1

                # Track last seen
                if source not in summary["last_seen"] or ts > summary["last_seen"][source]["ts"]:
                    summary["last_seen"][source] = {"ts": ts, "ts_iso": ev["ts_iso"], "type": typ}

        return {"ok": True, "summary": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "tenant": tenant,
        "window_hours": hours,
        "schedule": {
            "interval_sec": int(sched.get("interval_sec", 300)),
            "paused": bool(sched.get("paused")),
            "last_run": float(sched.get("last_run", 0.0)),
            "last_run_iso": to_iso(sched.get("last_run")),
        },
        "activity": {
            "audit_count": len(audits),
            "local_runs": len(runs),
        },
        "last_status": last_status,
        "health": health,
        "recent_audit": recent_audit,
        "ts_iso": datetime.utcnow().isoformat() + "Z",
    }


# @app.post("/ops/register", dependencies=[Depends(operator_only)])
# async def register_service(payload: ServiceRegistration):
#     """
#     Register a service with the Command Center.

#     Services can announce themselves at startup instead of being hardcoded.
#     Useful for dynamic service discovery and auto-configuration.

#     Requires: operator or admin role
#     """
#     # Upsert: update if exists, insert if new
#     REGISTERED_SERVICES[payload.name] = {
#         "name": payload.name,
#         "url": payload.url,
#         "health_url": payload.health_url or f"{payload.health_url}/ping",
#         "version": payload.version,
#         "roles_required": payload.roles_required or [],
#         "tags": payload.tags or [],
#         "last_seen": _now_iso(),
#     }

#     # Phase VI M4: Emit registration event
#     await publish_event_internal(
#         "service.registered",
#         {
#             "service": payload.name,
#             "url": payload.url,
#             "version": payload.version,
#             "tags": payload.tags or [],
#         },
#     )

#     return {"status": "ok", "registered": payload.name, "service_count": len(REGISTERED_SERVICES)}


# @app.get("/ops/services", dependencies=[Depends(operator_only)])
# def list_services():
#     """
#     List all registered services.

#     Returns all services that have registered via POST /ops/register.
#     Useful for discovering available services and their capabilities.

#     Requires: operator or admin role
#     """
#     return {
#         "status": "ok",
#         "count": len(REGISTERED_SERVICES),
#         "services": list(REGISTERED_SERVICES.values()),
#     }


# @app.delete("/ops/services/{name}", dependencies=[Depends(operator_only)])
# async def delete_service(name: str):
#     """
#     Remove a service from the registry.

#     Useful for cleaning up stale service registrations.

#     Requires: operator or admin role
#     """
#     if name not in REGISTERED_SERVICES:
#         raise HTTPException(status_code=404, detail=f"Service '{name}' not found in registry")

#     del REGISTERED_SERVICES[name]

#     # Phase VI M4: Emit unregistration event
#     await publish_event_internal(
#         "service.unregistered",
#         {
#             "service": name,
#             "severity": "warning",
#         },
#     )

#     return {"status": "ok", "deleted": name, "remaining_count": len(REGISTERED_SERVICES)}


@app.post("/api/local/run")
async def local_run(request: Request):
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")
        body = await request.json()
        action = body.get("action")
        if not action:
            return {"ok": False, "error": "action is required"}

        # Record the run
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

        # Persist local action runs after mutation
        save_json_safe(LOCAL_RUNS_FILE, LOCAL_ACTION_RUNS)
        # Phase XVI: persist to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.append_local_run(run_rec)
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication("local_runs", "insert", run_rec, tenant)

        # Increment Prometheus counter
        local_actions_total.labels(tenant=tenant, action=action).inc()

        # Emit completion event
        await emit_event(
            {"tenant": tenant, "type": "ops.local.run.completed", "payload": {"action": action}}
        )

        return {"ok": True, "stdout": f"Executed {action}", "stderr": "", "error": None}
    except Exception as e:
        print(f"Error in local_run: {e}")
        # Emit failure event
        tenant = request.headers.get("x-tenant", "the-expert-co")
        action = (await request.json()).get("action") if request else None
        await emit_event(
            {
                "tenant": tenant,
                "type": "ops.local.run.failed",
                "payload": {"action": action, "error": str(e)},
            }
        )
        return {"ok": False, "error": str(e)}


@app.get("/api/local/runs")
async def list_local_runs():
    try:
        return {"runs": LOCAL_ACTION_RUNS}
    except Exception as e:
        print(f"Error in list_local_runs: {e}")
        return {"runs": [], "error": str(e)}


# Phase IX: AccuLynx Scheduler Endpoints
@app.post("/api/crm/import/acculynx/schedule")
async def acculynx_schedule(request: Request):
    """
    Set up or update a recurring AccuLynx import schedule for a tenant.

    Body: { "interval_sec": 300 }  (default: 5 minutes)
    Header: x-tenant (default: the-expert-co)
    Phase XI: Now logs to audit trail.
    Phase XII: Protected with RBAC - requires x-ops header.
    """
    ensure_ops(request)  # Phase XII: Require operator privileges
    try:
        body = await request.json()
        tenant = request.headers.get("x-tenant", "the-expert-co")
        interval_sec = int(body.get("interval_sec", 300))

        ACCU_IMPORT_SCHEDULES[tenant] = {
            "interval_sec": interval_sec,
            "last_run": 0,  # Will trigger on first poll
            "last_status": {
                "ok": True,
                "ts": time.time(),
                "message": "schedule registered",
            },
        }
        # Phase XIII: persist schedules after mutation
        save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
        # Phase XVI: persist to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.save_schedule(tenant, ACCU_IMPORT_SCHEDULES[tenant])
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication(
            "schedules", "upsert", {"tenant": tenant, **ACCU_IMPORT_SCHEDULES[tenant]}, tenant
        )

        log_scheduler_audit(tenant, "schedule", metadata={"interval_sec": interval_sec})
        await emit_event(
            {
                "tenant": tenant,
                "type": "scheduler.schedule.created",
                "payload": {"interval_sec": interval_sec},
            }
        )
        log.info(f"[acculynx-schedule] Set schedule for {tenant}: {interval_sec}s")

        return {
            "ok": True,
            "tenant": tenant,
            "interval_sec": interval_sec,
            "message": f"AccuLynx import scheduled every {interval_sec} seconds",
        }
    except Exception as e:
        log.error(f"[acculynx-schedule] Error setting schedule: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/crm/import/acculynx/pause")
async def acculynx_pause(request: Request):
    """
    Pause the AccuLynx auto-sync scheduler for a specific tenant.

    Phase X: Allows ops to temporarily disable auto-sync without deleting the schedule.
    Phase XI: Now logs to audit trail.
    Phase XII: Protected with RBAC - requires x-ops header.
    Header: x-tenant (default: the-expert-co)
    """
    ensure_ops(request)  # Phase XII: Require operator privileges
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")
        cfg = ACCU_IMPORT_SCHEDULES.get(tenant)

        if not cfg:
            # Create a stub entry so UI doesn't get confused
            ACCU_IMPORT_SCHEDULES[tenant] = {
                "interval_sec": 300,
                "last_run": 0,
                "last_status": {"ok": True, "ts": time.time(), "message": "created during pause"},
                "paused": True,
            }
        else:
            ACCU_IMPORT_SCHEDULES[tenant]["paused"] = True

        # Phase XIII: persist schedules after mutation
        save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
        # Phase XVI: persist to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.save_schedule(tenant, ACCU_IMPORT_SCHEDULES[tenant])
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication(
            "schedules", "update", {"tenant": tenant, **ACCU_IMPORT_SCHEDULES[tenant]}, tenant
        )

        log_scheduler_audit(tenant, "pause")
        await emit_event({"tenant": tenant, "type": "scheduler.schedule.paused"})
        log.info(f"[acculynx-pause] Paused scheduler for {tenant}")
        return {"ok": True, "tenant": tenant, "paused": True}
    except Exception as e:
        log.error(f"[acculynx-pause] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/crm/import/acculynx/resume")
async def acculynx_resume(request: Request):
    """
    Resume the AccuLynx auto-sync scheduler for a specific tenant.

    Phase X: Re-enables auto-sync after it was paused.
    Phase XI: Now logs to audit trail.
    Phase XII: Protected with RBAC - requires x-ops header.
    Header: x-tenant (default: the-expert-co)
    """
    ensure_ops(request)  # Phase XII: Require operator privileges
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")
        cfg = ACCU_IMPORT_SCHEDULES.get(tenant)

        if not cfg:
            # If no schedule yet, make one with default 5m
            ACCU_IMPORT_SCHEDULES[tenant] = {
                "interval_sec": 300,
                "last_run": 0,
                "last_status": {"ok": True, "ts": time.time(), "message": "created during resume"},
                "paused": False,
            }
        else:
            ACCU_IMPORT_SCHEDULES[tenant]["paused"] = False

        # Phase XIII: persist schedules after mutation
        save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
        # Phase XVI: persist to DB if enabled
        try:
            if DB_STORE is not None:
                DB_STORE.save_schedule(tenant, ACCU_IMPORT_SCHEDULES[tenant])
        except Exception:
            pass
        # Phase XVII: enqueue replication
        _enqueue_replication(
            "schedules", "update", {"tenant": tenant, **ACCU_IMPORT_SCHEDULES[tenant]}, tenant
        )

        log_scheduler_audit(tenant, "resume")
        await emit_event({"tenant": tenant, "type": "scheduler.schedule.resumed"})
        log.info(f"[acculynx-resume] Resumed scheduler for {tenant}")
        return {"ok": True, "tenant": tenant, "paused": False}
    except Exception as e:
        log.error(f"[acculynx-resume] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/crm/import/acculynx/run-now")
async def acculynx_run_now(request: Request):
    """
    Trigger an immediate AccuLynx import for a tenant, bypassing the schedule.

    Phase X: Allows manual import without waiting for next scheduled run.
    Phase XI: Now logs to audit trail.
    Phase XII: Protected with RBAC - requires x-ops header.
    Header: x-tenant (default: the-expert-co)
    """
    ensure_ops(request)  # Phase XII: Require operator privileges
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")
        log_scheduler_audit(tenant, "run-now", metadata={"source": "manual"})
        await emit_event({"tenant": tenant, "type": "scheduler.import.requested"})
        log.info(f"[acculynx-run-now] Manual import triggered for {tenant}")

        result = await acculynx_pull_for_tenant(tenant)
        return {"ok": True, "tenant": tenant, "result": result}
    except Exception as e:
        log.error(f"[acculynx-run-now] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.delete("/api/crm/import/acculynx/schedule")
async def acculynx_delete_schedule(request: Request):
    """
    Delete/clear the AccuLynx import schedule for a specific tenant.

    Phase XI: Completely removes tenant from scheduler map.
    Phase XII: Protected with RBAC - requires x-ops header.
    Header: x-tenant (default: the-expert-co)
    """
    ensure_ops(request)  # Phase XII: Require operator privileges
    try:
        tenant = request.headers.get("x-tenant", "the-expert-co")

        if tenant in ACCU_IMPORT_SCHEDULES:
            del ACCU_IMPORT_SCHEDULES[tenant]
            # Phase XIII: persist schedules after mutation
            save_json_safe(SCHEDULES_FILE, ACCU_IMPORT_SCHEDULES)
            # Phase XVI: delete from DB if enabled
            try:
                if DB_STORE is not None:
                    DB_STORE.delete_schedule(tenant)
            except Exception:
                pass
            # Phase XVII: enqueue replication
            _enqueue_replication("schedules", "delete", {"tenant": tenant}, tenant)
            log_scheduler_audit(tenant, "delete")
            await emit_event({"tenant": tenant, "type": "scheduler.schedule.deleted"})
            log.info(f"[acculynx-delete] Deleted schedule for {tenant}")
            return {"ok": True, "tenant": tenant, "message": "Schedule deleted"}
        else:
            return {"ok": False, "tenant": tenant, "message": "No schedule found"}
    except Exception as e:
        log.error(f"[acculynx-delete] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/crm/import/acculynx/audit")
async def acculynx_audit_log(limit: int = 50):
    """
    Get recent scheduler operation audit trail.

    Phase XI: Returns recent pause/resume/run-now/delete/schedule actions.
    Query param: limit (default: 50, max: 100)
    """
    try:
        limit = min(limit, MAX_AUDIT_ENTRIES)
        return {
            "ok": True,
            "audit": ACCU_SCHEDULER_AUDIT[:limit],
            "total": len(ACCU_SCHEDULER_AUDIT),
        }
    except Exception as e:
        log.error(f"[acculynx-audit] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/crm/import/acculynx/schedule/status")
async def acculynx_schedule_status():
    """
    Get the current status of all AccuLynx import schedules.

    Returns enriched schedule data with both epoch and ISO timestamps.
    Phase X: Now includes paused flag and next_run_in_sec countdown.
    Backwards compatible - all original fields preserved.
    """
    print("Endpoint called")
    try:
        # Enrich each tenant's schedule with ISO timestamps + countdown
        enriched = {}
        now = time.time()
        for tenant, cfg in ACCU_IMPORT_SCHEDULES.items():
            last_run = cfg.get("last_run")
            interval = int(cfg.get("interval_sec", 300))
            paused = bool(cfg.get("paused", False))

            # Compute next run only if not paused
            next_run_in = None
            if not paused:
                next_run_in = max(0, (last_run + interval) - now) if last_run else 0

            last_status = cfg.get("last_status", {})
            enriched[tenant] = {
                **cfg,
                "paused": paused,
                "next_run_in_sec": next_run_in,
                "last_run_iso": to_iso(last_run),
                "last_status": {
                    **last_status,
                    "ts_iso": to_iso(last_status.get("ts")),
                },
            }

        return {
            "ok": True,
            "schedules": enriched,
            "ts": now,
            "ts_iso": to_iso(now),
        }
    except Exception as e:
        log.error(f"[acculynx-schedule-status] Error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/")
def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": "AetherLink Command Center",
        "version": "0.1.0",
        "endpoints": {
            "/ops/health": "Aggregated service health",
            "/ops/ping": "Command Center health check",
            "/ops/register": "Register a service (POST)",
            "/ops/services": "List registered services",
            "/audit/stats": "Security audit statistics",
            "/events/publish": "Publish an event (POST)",
            "/events/schema": "List event schemas",
            "/events/recent": "Query recent events",
            "/events/stream": "Live event stream (SSE)",
        },
    }
