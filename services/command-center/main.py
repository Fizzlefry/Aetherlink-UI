import asyncio
import json
import logging
import os
import shutil
import sqlite3
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# import alert_evaluator
# import alert_store
# import event_store
import httpx
from ops_insight_analyzer import OpsInsightAnalyzer

RECOVERY_DB = Path("monitoring/recovery_events.sqlite")


def record_remediation_event(
    alertname: str,
    tenant: str,
    action: str,
    status: str,
    details: str = "",
) -> None:
    """Record a remediation event to SQLite for Grafana recovery timeline."""
    RECOVERY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RECOVERY_DB)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS remediation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                alertname TEXT,
                tenant TEXT,
                action TEXT,
                status TEXT,
                details TEXT
            )
            """
        )
        cur.execute(
            """
            INSERT INTO remediation_events (ts, alertname, tenant, action, status, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat() + "Z",
                alertname,
                tenant,
                action,
                status,
                details[:500],
            ),
        )
        conn.commit()
    finally:
        conn.close()


# from audit import audit_middleware, get_audit_stats
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge as PrometheusGauge
from prometheus_client import make_asgi_app
from pydantic import BaseModel

# from routers import alert_templates, alerts, delivery_history, events, operator_audit_router
from starlette.middleware.base import BaseHTTPMiddleware

# Phase XVII-B: Persistence backends
try:
    from .persistence import JSONBackend, SQLiteBackend
except ImportError:
    # Fallback if persistence module not available
    SQLiteBackend = None
    JSONBackend = None

# Phase XXIII: Adaptive Auto-Response
try:
    from .adaptive_cron import adaptive_auto_responder
    from .adaptive_engine import analyze_patterns

    # Phase XXIII-D: Learning Optimization
    from .learning_optimizer import (
        analyze_learning_patterns,
        record_action_outcome,
        record_operator_feedback,
    )
except ImportError:
    analyze_patterns = None
    adaptive_auto_responder = None
    record_action_outcome = None
    record_operator_feedback = None
    analyze_learning_patterns = None

# Phase XX: Real scheduler integration (optional)
try:
    from scheduler import (  # your real scheduler module
        get_all_jobs,
        pause_job,
        resume_job,
    )
except ImportError:
    get_all_jobs = None
    pause_job = None
    resume_job = None


# Adapter that provides the thin synchronous API the rest of main.py expects.
# It schedules async persistence tasks to the real async backends so existing
# code that calls DB_STORE.save_schedule(), append_event(), etc. can remain
# mostly unchanged.
class PersistenceAdapter:
    def __init__(self, sqlite_backend=None, json_backend=None, dual_write: bool = False):
        self.sqlite = sqlite_backend
        self.json = json_backend
        self.dual = dual_write

    def append_event(self, ev: dict[str, Any]) -> None:
        try:
            if self.sqlite:
                asyncio.create_task(self.sqlite.save_event(ev))
            if self.dual and self.json:
                asyncio.create_task(self.json.save_event(ev))
        except Exception as e:
            global DEGRADED_FLAG, PERSISTENCE_LAST_ERROR
            DEGRADED_FLAG = True
            PERSISTENCE_LAST_ERROR = f"Event persistence failed: {e}"

    def save_schedule(self, tenant: str, schedule: dict[str, Any]) -> None:
        # Persist full schedules snapshot (safer) from in-memory global
        try:
            if self.sqlite:
                asyncio.create_task(self.sqlite.save_schedules(ACCU_IMPORT_SCHEDULES))
            if self.dual and self.json:
                asyncio.create_task(self.json.save_schedules(ACCU_IMPORT_SCHEDULES))
        except Exception as e:
            global DEGRADED_FLAG, PERSISTENCE_LAST_ERROR
            DEGRADED_FLAG = True
            PERSISTENCE_LAST_ERROR = f"Schedule persistence failed: {e}"

    def delete_schedule(self, tenant: str) -> None:
        # After in-memory deletion, persist full snapshot
        try:
            self.save_schedule(tenant, {})  # This will handle the exception
        except Exception:
            pass  # Already handled in save_schedule

    def append_local_run(self, run: dict[str, Any]) -> None:
        try:
            if self.sqlite:
                asyncio.create_task(self.sqlite.save_local_action_runs(LOCAL_ACTION_RUNS))
            if self.dual and self.json:
                asyncio.create_task(self.json.save_local_action_runs(LOCAL_ACTION_RUNS))
        except Exception as e:
            global DEGRADED_FLAG, PERSISTENCE_LAST_ERROR
            DEGRADED_FLAG = True
            PERSISTENCE_LAST_ERROR = f"Local run persistence failed: {e}"

    def list_audit(self, limit: int = 1000) -> list[dict[str, Any]]:
        # Prefer in-memory audit for immediate reads
        return ACCU_SCHEDULER_AUDIT[:limit]

    def list_local_runs(self, limit: int = 500) -> list[dict[str, Any]]:
        return LOCAL_ACTION_RUNS[:limit]

    def list_events(
        self, tenant: str | None = None, type_prefix: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        # Events are not cached in-memory in this version; return empty list as safe default
        return []

    async def save_anomaly_event(self, anomaly: dict[str, Any]) -> int:
        """Save an anomaly event and return the event ID."""
        try:
            if self.sqlite:
                return await self.sqlite.save_anomaly_event(anomaly)
            if self.dual and self.json:
                # JSON backend doesn't support anomaly events, just log
                print(
                    f"[persist] Anomaly event saved to SQLite only: {anomaly.get('alert_name', 'unknown')}"
                )
                return 0
        except Exception as e:
            global DEGRADED_FLAG, PERSISTENCE_LAST_ERROR
            DEGRADED_FLAG = True
            PERSISTENCE_LAST_ERROR = f"Anomaly persistence failed: {e}"
            return 0
        return 0

    async def save_remediation_action(self, remediation: dict[str, Any]) -> int:
        """Save a remediation action and return the action ID."""
        try:
            if self.sqlite:
                return await self.sqlite.save_remediation_action(remediation)
            if self.dual and self.json:
                # JSON backend doesn't support remediation actions, just log
                print(
                    f"[persist] Remediation action saved to SQLite only: {remediation.get('action_type', 'unknown')}"
                )
                return 0
        except Exception as e:
            global DEGRADED_FLAG, PERSISTENCE_LAST_ERROR
            DEGRADED_FLAG = True
            PERSISTENCE_LAST_ERROR = f"Remediation persistence failed: {e}"
            return 0
        return 0


# Phase XV: Real AccuLynx Integration - Configuration
class AccuLynxConfig(BaseModel):
    base_url: str = os.getenv("ACCULYNX_BASE_URL", "https://api.acculynx.com")
    api_key: str | None = os.getenv("ACCULYNX_API_KEY")
    timeout_sec: int = int(os.getenv("ACCULYNX_TIMEOUT_SEC", "15"))


ACCU_LYNX_CONFIG = AccuLynxConfig()


# Dummy prometheus classes for when prometheus_client is not available
class Counter:
    def __init__(self, name, description, labelnames=None):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []
        self._value = self  # For compatibility with _value.get()

    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def get(self):
        return 0  # Return 0 for dummy implementation


class Gauge:
    def __init__(self, name, description, labelnames=None):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []
        self._value = self  # For compatibility

    def labels(self, **kwargs):
        return self

    def set(self, value):
        pass

    def get(self):
        return 0  # Return 0 for dummy implementation


# from rbac import require_roles
# from routers import alert_templates, alerts, delivery_history, events, operator_audit_router

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

# Phase XIV Task #4: DB Prep - Persistence Layer Migration Plan
# Current: JSON file-based persistence with atomic writes and self-healing loads
# Future: Postgres database with connection pooling and transactions
# Migration Strategy:
# 1. Add DB schema and connection management
# 2. Implement dual-write mode (JSON + DB) for data consistency
# 3. Replace save_json_safe() calls with DB INSERT/UPDATE operations
# 4. Replace load_json_self_heal() calls with DB SELECT queries
# 5. Update startup lifespan to load from DB instead of JSON files
# 6. Remove JSON file operations after successful migration
# Marked functions: save_json_safe, load_json_self_heal, log_scheduler_audit, startup persistence loading

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

# Phase XVIII: Extended health tracking
STARTED_AT: float | None = None
LAST_SCHEDULER_TICK: float | None = None
PERSISTENCE_LAST_ERROR: str | None = None
DEGRADED_FLAG: bool = False

# Track scheduler main loop heartbeat
_SCHEDULER_LAST_LOOP_TS: float | None = None

# Phase XVII-B: Persistence backends
_SQLITE_BACKEND = None
_JSON_BACKEND = None


def save_json_safe(path: Path, payload, max_snapshots: int | None = None):
    """
    Atomically write JSON and keep a few timestamped backups.

    PERSISTENCE-LAYER V1 (JSON)
    To move to Postgres, replace:
    - save_json_safe() calls with DB writes
    - load_json_self_heal() calls with DB reads
    - Startup persistence loading with DB queries
    """
    if max_snapshots is None:
        max_snapshots = MAX_JSON_SNAPSHOTS
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
    Load JSON with fallback to default if file missing/corrupted.

    PERSISTENCE-LAYER V1 (JSON)
    To move to Postgres, replace with DB queries in startup lifespan.
    """
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


# Phase XVII-B: Dual-write persistence helpers
async def persist_schedules(schedules: dict[str, Any]) -> None:
    """Save schedules to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_schedules(schedules)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_schedules(schedules)
        except Exception as e:
            print(f"[persist] Dual-write schedules failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(SCHEDULES_FILE, schedules)


async def persist_audit_entries(entries: list[dict[str, Any]]) -> None:
    """Save audit entries to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_audit_entries(entries)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_audit_entries(entries)
        except Exception as e:
            print(f"[persist] Dual-write audit failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(AUDIT_FILE, entries)


async def persist_local_action_runs(runs: list[dict[str, Any]]) -> None:
    """Save local action runs to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_local_action_runs(runs)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_local_action_runs(runs)
        except Exception as e:
            print(f"[persist] Dual-write runs failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(LOCAL_RUNS_FILE, runs)


async def persist_import_record(tenant: str, import_data: dict[str, Any]) -> None:
    """Save import record to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_import_record(tenant, import_data)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_import_record(tenant, import_data)
        except Exception as e:
            print(f"[persist] Dual-write import failed: {e}")


async def persist_event(event: dict[str, Any]) -> None:
    """Save event to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_event(event)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_event(event)
        except Exception as e:
            print(f"[persist] Dual-write event failed: {e}")


async def persist_alert(alert: dict[str, Any]) -> None:
    """Save alert to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_alert(alert)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_alert(alert)
        except Exception as e:
            print(f"[persist] Dual-write alert failed: {e}")


# Phase XV: Real AccuLynx Integration - Adapter Functions


async def acculynx_fetch_jobs(config: AccuLynxConfig, tenant: str):
    """
    Fetch jobs from AccuLynx API using httpx.
    Falls back to stub mode if no API key configured.
    """
    if not config.api_key:
        # no key → still return stub so the scheduler doesn't crash
        return {
            "ok": True,
            "source": "stub",
            "tenant": tenant,
            "jobs": [],
            "message": "AccuLynx API key not configured; returning stub data",
        }

    try:
        async with httpx.AsyncClient(timeout=config.timeout_sec) as client:
            # example path — you'd change this to the real AccuLynx endpoint
            url = f"{config.base_url}/v1/jobs"

            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }

            resp = await client.get(url, headers=headers)

            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}

            return {
                "ok": resp.status_code == 200,
                "status": resp.status_code,
                "tenant": tenant,
                "payload": payload,
            }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "tenant": tenant,
            "error": str(e),
            "message": f"AccuLynx API call failed: {e}",
        }


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


# Phase XXIII-C: Helper functions for adaptive auto-responder
async def _fetch_adaptive_recommendations(tenant: str | None = None) -> dict[str, Any]:
    """Fetch adaptive recommendations for background auto-responder."""
    if analyze_patterns is None:
        return {"ok": False, "error": "Adaptive engine not available"}

    audits = ACCU_SCHEDULER_AUDIT
    result = analyze_patterns(audits, window_hours=24, tenant=tenant)
    return {
        "ok": True,
        **result,
    }


async def _apply_adaptive_action(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply adaptive action for background auto-responder."""
    rtype: str | None = payload.get("type")
    tenant: str = payload.get("tenant", "system")

    # Phase XXIX: Apply guardrails for background auto-responder

    # 1) Check automation budget
    budget_ok, budget_reason = check_automation_budget(tenant)
    if not budget_ok:
        # Phase XXXI: Record skipped action due to budget
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="budget").inc()

        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.blocked.rate_limited",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "reason": budget_reason,
                "action_type": rtype,
                "alert_id": payload.get("alert_id"),
                "job_id": payload.get("job_id"),
            },
        )
        return {"ok": False, "error": f"Automation budget exceeded: {budget_reason}"}

    # 2) Check protected objects
    if rtype == "auto_ack_candidate":
        alert_type = payload.get("alert_type", "unknown")
        protected_ok, protected_reason = check_protected_objects("alert_ack", alert_type)
        if not protected_ok:
            # Phase XXXI: Record skipped action due to protected object
            ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="protected").inc()

            log_scheduler_audit(
                tenant=tenant,
                operation="operator.adaptive.blocked.protected_object",
                source="adaptive.auto",
                actor_type="adaptive.auto",
                metadata={
                    "reason": protected_reason,
                    "action_type": rtype,
                    "alert_type": alert_type,
                    "alert_id": payload.get("alert_id"),
                },
            )
            return {"ok": False, "error": f"Protected object: {protected_reason}"}

    # 3) Check confidence floor
    confidence = payload.get("confidence", 0.0)
    required_confidence = get_tenant_confidence_floor(tenant)
    if confidence < required_confidence:
        # Phase XXXI: Record skipped action due to low confidence
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="low_confidence").inc()

        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.blocked.low_confidence",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "confidence": confidence,
                "required": required_confidence,
                "action_type": rtype,
                "alert_id": payload.get("alert_id"),
            },
        )
        return {"ok": False, "error": f"Confidence {confidence} below floor {required_confidence}"}

    # 4) Simulation mode check
    if ADAPTIVE_AUTO_DRY_RUN:
        # Phase XXXI: Record skipped action due to dry run
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="dry_run").inc()

        # Log simulated action instead of applying
        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.simulated",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "would_apply": rtype,
                "reason": "dry_run_enabled",
                "alert_id": payload.get("alert_id"),
                "alert_type": payload.get("alert_type"),
            },
        )
        return {"ok": True, "simulated": True, "action": rtype, "reason": "dry_run_enabled"}

    # All guardrails passed - record and apply action
    record_automation_action(tenant)

    # Phase XXXI: Record executed action
    ADAPTIVE_ACTIONS_EXECUTED.labels(tenant=tenant, mode="auto").inc()

    # assisted alert ack
    if rtype == "auto_ack_candidate":
        alert_id: str | None = payload.get("alert_id")
        alertname = payload.get("alert_type") or payload.get("alertname") or "unknown_alert"

        if not alert_id:
            return {"ok": False, "error": "alert_id required"}

        try:
            # Update acknowledgment state
            ALERT_ACK_STATE[alert_id] = {
                "ack": True,
                "ack_by": tenant,
                "ack_ts": datetime.now(UTC).isoformat(),
            }

            # Log the automated acknowledgment
            log_scheduler_audit(
                tenant=tenant,
                operation="operator.alert.ack",
                source="adaptive.auto",
                metadata={"alert_id": alert_id, "applied": "adaptive.auto"},
            )

            # Record to recovery timeline
            record_remediation_event(
                alertname=alertname,
                tenant=tenant,
                action="auto_ack",
                status="success",
                details=f"Auto-acknowledged alert {alert_id}",
            )

            return {"ok": True, "applied": "alert_ack", "alert_id": alert_id}
        except Exception as e:
            # Record failure too
            record_remediation_event(
                alertname=alertname,
                tenant=tenant,
                action="auto_ack",
                status="error",
                details=str(e),
            )
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unsupported action type: {rtype}"}


async def _learning_update_callback() -> None:
    """Periodic learning model update callback."""
    logger = logging.getLogger(__name__)
    try:
        # Trigger learning analysis to update models with new data
        if analyze_learning_patterns:
            analyze_learning_patterns(ACCU_SCHEDULER_AUDIT, window_hours=24)
            logger.info("Learning models updated with latest audit data")
    except Exception as exc:
        logger.warning("Learning update failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Phase IX: Starts AccuLynx scheduler loop.
    Phase XIII: Loads persisted state from disk.
    Phase XVII: Starts replication worker if enabled.
    Phase XVIII: Starts health monitor loop.
    """
    global STARTED_AT, PERSISTENCE_LAST_ERROR
    STARTED_AT = time.time()
    PERSISTENCE_LAST_ERROR = None

    try:
        print("[startup] Lifespan starting")

        # Phase XVII-B: Initialize persistence backends
        global _SQLITE_BACKEND, _JSON_BACKEND
        try:
            if SQLiteBackend:
                _SQLITE_BACKEND = SQLiteBackend(STORE_DSN)
                await _SQLITE_BACKEND.initialize()
                print("[persist] SQLite backend initialized")
            else:
                print("[persist] SQLite backend not available")
                PERSISTENCE_LAST_ERROR = "SQLite backend class not available"

            if JSONBackend:
                _JSON_BACKEND = JSONBackend(str(DATA_DIR))
                await _JSON_BACKEND.initialize()
                print("[persist] JSON fallback backend initialized")
            else:
                print("[persist] JSON backend not available")
                if PERSISTENCE_LAST_ERROR:
                    PERSISTENCE_LAST_ERROR += "; JSON backend not available"
                else:
                    PERSISTENCE_LAST_ERROR = "JSON backend not available"
        except Exception as e:
            print(f"[persist] Failed to initialize persistence backends: {e}")
            PERSISTENCE_LAST_ERROR = str(e)

        # Phase XIII: Load persisted state from persistence backends
        try:
            # wire DB_STORE adapter for legacy callsites (synchronous API)
            global DB_STORE
            DB_STORE = PersistenceAdapter(_SQLITE_BACKEND, _JSON_BACKEND, dual_write=DUAL_WRITE)

            # expose primary/fallback stores on app.state for new codepaths
            try:
                if STORE_MODE == "sqlite" and _SQLITE_BACKEND is not None:
                    app.state.primary_store = _SQLITE_BACKEND
                    app.state.fallback_store = (
                        _JSON_BACKEND if DUAL_WRITE and _JSON_BACKEND is not None else None
                    )
                else:
                    app.state.primary_store = _JSON_BACKEND
                    app.state.fallback_store = (
                        _SQLITE_BACKEND if DUAL_WRITE and _SQLITE_BACKEND is not None else None
                    )
            except Exception:
                # app.state may not be writable in some test harnesses; ignore
                pass

            schedules = {}
            audit_entries: list[dict[str, Any]] = []
            local_runs: list[dict[str, Any]] = []

            # Prefer configured STORE_MODE backend, fallback to JSON backend
            if STORE_MODE == "sqlite" and _SQLITE_BACKEND is not None:
                try:
                    schedules = await _SQLITE_BACKEND.load_schedules()
                    audit_entries = await _SQLITE_BACKEND.load_audit_entries(
                        limit=MAX_AUDIT_ENTRIES
                    )
                    local_runs = await _SQLITE_BACKEND.load_local_action_runs(
                        limit=MAX_LOCAL_ACTION_RUNS
                    )
                    print(
                        f"[persist] Loaded state from SQLite: schedules={len(schedules)}, audit={len(audit_entries)}, runs={len(local_runs)}"
                    )
                except Exception as e:
                    print(f"[persist] SQLite load failed: {e}")

            # Always try JSON fallback if primary didn't return data
            if (not schedules or not audit_entries or not local_runs) and _JSON_BACKEND is not None:
                try:
                    if not schedules:
                        schedules = await _JSON_BACKEND.load_schedules()
                    if not audit_entries:
                        audit_entries = await _JSON_BACKEND.load_audit_entries(
                            limit=MAX_AUDIT_ENTRIES
                        )
                    if not local_runs:
                        local_runs = await _JSON_BACKEND.load_local_action_runs(
                            limit=MAX_LOCAL_ACTION_RUNS
                        )
                    print(
                        f"[persist] Loaded state from JSON fallback: schedules={len(schedules)}, audit={len(audit_entries)}, runs={len(local_runs)}"
                    )
                except Exception as e:
                    print(f"[persist] JSON fallback load failed: {e}")

            # Apply to in-memory structures (keep previous semantics)
            try:
                if schedules:
                    ACCU_IMPORT_SCHEDULES.update(schedules)
                if audit_entries:
                    ACCU_SCHEDULER_AUDIT.extend(audit_entries[-MAX_AUDIT_ENTRIES:])
                if local_runs:
                    LOCAL_ACTION_RUNS.extend(local_runs[-MAX_LOCAL_ACTION_RUNS:])
                print(
                    f"[persist] In-memory state populated: schedules={len(ACCU_IMPORT_SCHEDULES)}, audit={len(ACCU_SCHEDULER_AUDIT)}, runs={len(LOCAL_ACTION_RUNS)}"
                )
            except Exception as e:
                print(f"[persist] Failed to populate in-memory state: {e}")
        except Exception as e:
            print(f"[persist] Failed to load persisted state: {e}")

        # Phase XVIII: Re-apply auto-paused state if needed
        try:
            count = _reapply_auto_paused()
            if count:
                print(f"[health] Re-applied auto-pause to {count} tenants")
        except Exception as e:
            print(f"[health] Failed to re-apply auto-pause: {e}")

        # Phase IX: Start scheduler loop defensively
        try:
            # asyncio.create_task(acculynx_scheduler_loop())
            print("[startup] Scheduler loop skipped for testing")
        except Exception as e:
            print(f"[startup] Scheduler failed to start: {e}")

        # Phase XVII: Start replication worker if enabled
        if REPLICATION_ENABLED:
            try:
                global _REPLICA_Q
                _REPLICA_Q = asyncio.Queue(maxsize=REPLICA_QUEUE_MAXSIZE)
                # asyncio.create_task(replication_loop())
                print("[startup] Replication skipped for testing")
            except Exception as e:
                print(f"[startup] Replication worker failed: {e}")

        # Phase XVIII: Start health monitor
        try:
            # asyncio.create_task(health_loop())
            print("[startup] Health monitor skipped for testing")
        except Exception as e:
            print(f"[startup] Health monitor failed: {e}")

        # Phase XXIII-C: Start adaptive auto-responder
        if adaptive_auto_responder:
            try:
                logger = logging.getLogger(__name__)
                # Get list of tenants from audit data or config
                tenants = list(
                    set(
                        entry.get("tenant") for entry in ACCU_SCHEDULER_AUDIT if entry.get("tenant")
                    )
                )
                if not tenants:
                    tenants = [None]  # system/global if no tenants found

                # Phase XXIII-D: Learning update callback
                async def learning_update():
                    """Periodic learning model updates."""
                    if analyze_learning_patterns:
                        try:
                            # Update learning models with recent data
                            analyze_learning_patterns(ACCU_SCHEDULER_AUDIT, window_hours=24)
                            logger.info("Learning models updated")
                        except Exception as e:
                            logger.warning("Learning update failed: %s", e)

                # Start the background auto-responder
                asyncio.create_task(
                    adaptive_auto_responder(
                        fetch_recommendations=_fetch_adaptive_recommendations,
                        apply_action=_apply_adaptive_action,
                        tenants=tenants,
                        interval_seconds=300,  # 5 minutes
                        confidence_threshold=0.9,
                        learning_update_callback=learning_update,
                    )
                )
                print(
                    f"[startup] Adaptive auto-responder started for {len(tenants)} tenants with learning integration"
                )
            except Exception as e:
                print(f"[startup] Adaptive auto-responder failed to start: {e}")
        else:
            print("[startup] Adaptive auto-responder not available")

        print("[startup] All startup tasks completed")

        yield

        print("[shutdown] Lifespan shutting down")
    except Exception as e:
        print(f"[startup] Lifespan exception: {e}")
        import traceback

        traceback.print_exc()
        raise


app = FastAPI(title="AetherLink Command Center", version="0.2.0", lifespan=lifespan)

# CORS middleware for UI integration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global exception caught: {type(exc).__name__}: {exc}")
    return {"error": str(exc), "ok": False}


@app.get("/test")
def test():
    print("Test endpoint called")
    return {"ok": True}


@app.get("/ops/remediate/history")
async def get_remediation_history(
    limit: int = Query(100, ge=1, le=500),
    tenant: str | None = None,
    alertname: str | None = None,
):
    """
    Return recent remediation events for UI / operator consoles.
    Reads from monitoring/recovery_events.sqlite (created on first write).
    """
    db_path = RECOVERY_DB  # we defined this earlier
    if not db_path.exists():
        return {"items": [], "total": 0}

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        base_sql = """
            SELECT id, ts, alertname, tenant, action, status, details
            FROM remediation_events
        """
        where_clauses = []
        params: list[str] = []

        if tenant:
            where_clauses.append("tenant = ?")
            params.append(tenant)
        if alertname:
            where_clauses.append("alertname = ?")
            params.append(alertname)

        if where_clauses:
            base_sql += " WHERE " + " AND ".join(where_clauses)

        base_sql += " ORDER BY id DESC LIMIT ?"
        params.append(str(limit))

        rows = cur.execute(base_sql, params).fetchall()
        items = [
            {
                "id": r["id"],
                "ts": r["ts"],
                "alertname": r["alertname"],
                "tenant": r["tenant"],
                "action": r["action"],
                "status": r["status"],
                "details": r["details"],
            }
            for r in rows
        ]
        return {"items": items, "total": len(items)}
    finally:
        conn.close()


@app.get("/ops/insights/trends")
async def get_ops_insights():
    """
    Return analytics and trends from remediation events.
    Provides 1h and 24h summaries with deltas and top breakdowns.
    """
    analyzer = OpsInsightAnalyzer()
    return analyzer.build_insight_payload()


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

# Phase XIX Prometheus: Analytics gauges for grouped operations
analytics_all_time_gauge = PrometheusGauge(
    "aetherlink_ops_analytics_all_time", "All-time counts per grouped op label", ["label", "env"]
)

analytics_last_24h_gauge = PrometheusGauge(
    "aetherlink_ops_analytics_last_24h", "Last 24h counts per grouped op label", ["label", "env"]
)

# Phase XXXIII: Predictive Analytics & Forecasting
analytics_rolling_avg_gauge = PrometheusGauge(
    "aetherlink_analytics_rolling_avg_7d",
    "7-day rolling average operations per group",
    ["operation_group", "tenant"],
)

analytics_rate_delta_gauge = PrometheusGauge(
    "aetherlink_analytics_rate_delta_7d",
    "Rate of change (operations/day) per group",
    ["operation_group", "tenant"],
)

analytics_forecast_gauge = PrometheusGauge(
    "aetherlink_analytics_forecast_7d",
    "7-day operation forecast with confidence",
    ["operation_group", "tenant"],
)

analytics_forecast_confidence_gauge = PrometheusGauge(
    "aetherlink_analytics_forecast_confidence",
    "Forecast confidence score (0-1)",
    ["operation_group", "tenant"],
)

# Phase XXXIII: Cost/Usage Analytics
analytics_cost_total_gauge = PrometheusGauge(
    "aetherlink_analytics_cost_total", "Total automation cost per tenant", ["tenant"]
)

analytics_cost_budget_utilization_gauge = PrometheusGauge(
    "aetherlink_analytics_cost_budget_utilization",
    "Budget utilization percentage per tenant",
    ["tenant"],
)

analytics_cost_forecast_gauge = PrometheusGauge(
    "aetherlink_analytics_cost_forecast", "Forecasted cost for next period", ["tenant"]
)

analytics_cost_forecast_confidence_gauge = PrometheusGauge(
    "aetherlink_analytics_cost_forecast_confidence",
    "Cost forecast confidence score (0-1)",
    ["tenant"],
)

# Phase XXXIV: Auto-Healing metrics
remediation_actions_total_gauge = PrometheusGauge(
    "aetherlink_remediation_actions_total",
    "Total number of remediation actions taken",
    ["alert_name", "action", "tenant"],
)

# Phase XXXV: Anomaly History & Insights metrics
anomaly_events_total_gauge = PrometheusGauge(
    "aetherlink_anomaly_events_total",
    "Total number of anomaly events detected",
    ["alert_name", "severity", "anomaly_type", "tenant"],
)

recovery_mttr_seconds_gauge = PrometheusGauge(
    "aetherlink_recovery_mttr_seconds", "Mean Time To Recovery in seconds", ["tenant"]
)

anomaly_resolution_rate_gauge = PrometheusGauge(
    "aetherlink_anomaly_resolution_rate", "Rate of anomaly resolution (0-1)", ["tenant"]
)


# from rbac import require_roles
# from routers import alert_templates, alerts, delivery_history, events, operator_audit_router

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

# Phase XIV Task #4: DB Prep - Persistence Layer Migration Plan
# Current: JSON file-based persistence with atomic writes and self-healing loads
# Future: Postgres database with connection pooling and transactions
# Migration Strategy:
# 1. Add DB schema and connection management
# 2. Implement dual-write mode (JSON + DB) for data consistency
# 3. Replace save_json_safe() calls with DB INSERT/UPDATE operations
# 4. Replace load_json_self_heal() calls with DB SELECT queries
# 5. Update startup lifespan to load from DB instead of JSON files
# 6. Remove JSON file operations after successful migration
# Marked functions: save_json_safe, load_json_self_heal, log_scheduler_audit, startup persistence loading

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

# Phase XVIII: Extended health tracking
STARTED_AT: float | None = None
LAST_SCHEDULER_TICK: float | None = None
PERSISTENCE_LAST_ERROR: str | None = None
DEGRADED_FLAG: bool = False

# Track scheduler main loop heartbeat
_SCHEDULER_LAST_LOOP_TS: float | None = None

# Phase XVII-B: Persistence backends
_SQLITE_BACKEND = None
_JSON_BACKEND = None


def save_json_safe(path: Path, payload, max_snapshots: int | None = None):
    """
    Atomically write JSON and keep a few timestamped backups.

    PERSISTENCE-LAYER V1 (JSON)
    To move to Postgres, replace:
    - save_json_safe() calls with DB writes
    - load_json_self_heal() calls with DB reads
    - Startup persistence loading with DB queries
    """
    if max_snapshots is None:
        max_snapshots = MAX_JSON_SNAPSHOTS
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
    Load JSON with fallback to default if file missing/corrupted.

    PERSISTENCE-LAYER V1 (JSON)
    To move to Postgres, replace with DB queries in startup lifespan.
    """
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


# Phase XVII-B: Dual-write persistence helpers
async def persist_schedules(schedules: dict[str, Any]) -> None:
    """Save schedules to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_schedules(schedules)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_schedules(schedules)
        except Exception as e:
            print(f"[persist] Dual-write schedules failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(SCHEDULES_FILE, schedules)


async def persist_audit_entries(entries: list[dict[str, Any]]) -> None:
    """Save audit entries to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_audit_entries(entries)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_audit_entries(entries)
        except Exception as e:
            print(f"[persist] Dual-write audit failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(AUDIT_FILE, entries)


async def persist_local_action_runs(runs: list[dict[str, Any]]) -> None:
    """Save local action runs to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_local_action_runs(runs)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_local_action_runs(runs)
        except Exception as e:
            print(f"[persist] Dual-write runs failed: {e}")
    else:
        # Legacy single-write to JSON
        save_json_safe(LOCAL_RUNS_FILE, runs)


async def persist_import_record(tenant: str, import_data: dict[str, Any]) -> None:
    """Save import record to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_import_record(tenant, import_data)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_import_record(tenant, import_data)
        except Exception as e:
            print(f"[persist] Dual-write import failed: {e}")


async def persist_event(event: dict[str, Any]) -> None:
    """Save event to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_event(event)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_event(event)
        except Exception as e:
            print(f"[persist] Dual-write event failed: {e}")


async def persist_alert(alert: dict[str, Any]) -> None:
    """Save alert to both backends if dual-write enabled."""
    if DUAL_WRITE:
        try:
            if _SQLITE_BACKEND:
                await _SQLITE_BACKEND.save_alert(alert)
            if _JSON_BACKEND:
                await _JSON_BACKEND.save_alert(alert)
        except Exception as e:
            print(f"[persist] Dual-write alert failed: {e}")


# Phase XV: Real AccuLynx Integration - Adapter Functions


async def acculynx_fetch_jobs(config: AccuLynxConfig, tenant: str):
    """
    Fetch jobs from AccuLynx API using httpx.
    Falls back to stub mode if no API key configured.
    """
    if not config.api_key:
        # no key → still return stub so the scheduler doesn't crash
        return {
            "ok": True,
            "source": "stub",
            "tenant": tenant,
            "jobs": [],
            "message": "AccuLynx API key not configured; returning stub data",
        }

    try:
        async with httpx.AsyncClient(timeout=config.timeout_sec) as client:
            # example path — you'd change this to the real AccuLynx endpoint
            url = f"{config.base_url}/v1/jobs"

            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }

            resp = await client.get(url, headers=headers)

            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}

            return {
                "ok": resp.status_code == 200,
                "status": resp.status_code,
                "tenant": tenant,
                "payload": payload,
            }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "tenant": tenant,
            "error": str(e),
            "message": f"AccuLynx API call failed: {e}",
        }


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


# Phase XXIII-C: Helper functions for adaptive auto-responder
async def _fetch_adaptive_recommendations(tenant: str | None = None) -> dict[str, Any]:
    """Fetch adaptive recommendations for background auto-responder."""
    if analyze_patterns is None:
        return {"ok": False, "error": "Adaptive engine not available"}

    audits = ACCU_SCHEDULER_AUDIT
    result = analyze_patterns(audits, window_hours=24, tenant=tenant)
    return {
        "ok": True,
        **result,
    }


async def _apply_adaptive_action(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply adaptive action for background auto-responder."""
    rtype: str | None = payload.get("type")
    tenant: str = payload.get("tenant", "system")

    # Phase XXIX: Apply guardrails for background auto-responder

    # 1) Check automation budget
    budget_ok, budget_reason = check_automation_budget(tenant)
    if not budget_ok:
        # Phase XXXI: Record skipped action due to budget
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="budget").inc()

        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.blocked.rate_limited",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "reason": budget_reason,
                "action_type": rtype,
                "alert_id": payload.get("alert_id"),
                "job_id": payload.get("job_id"),
            },
        )
        return {"ok": False, "error": f"Automation budget exceeded: {budget_reason}"}

    # 2) Check protected objects
    if rtype == "auto_ack_candidate":
        alert_type = payload.get("alert_type", "unknown")
        protected_ok, protected_reason = check_protected_objects("alert_ack", alert_type)
        if not protected_ok:
            # Phase XXXI: Record skipped action due to protected object
            ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="protected").inc()

            log_scheduler_audit(
                tenant=tenant,
                operation="operator.adaptive.blocked.protected_object",
                source="adaptive.auto",
                actor_type="adaptive.auto",
                metadata={
                    "reason": protected_reason,
                    "action_type": rtype,
                    "alert_type": alert_type,
                    "alert_id": payload.get("alert_id"),
                },
            )
            return {"ok": False, "error": f"Protected object: {protected_reason}"}

    # 3) Check confidence floor
    confidence = payload.get("confidence", 0.0)
    required_confidence = get_tenant_confidence_floor(tenant)
    if confidence < required_confidence:
        # Phase XXXI: Record skipped action due to low confidence
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="low_confidence").inc()

        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.blocked.low_confidence",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "confidence": confidence,
                "required": required_confidence,
                "action_type": rtype,
                "alert_id": payload.get("alert_id"),
            },
        )
        return {"ok": False, "error": f"Confidence {confidence} below floor {required_confidence}"}

    # 4) Simulation mode check
    if ADAPTIVE_AUTO_DRY_RUN:
        # Phase XXXI: Record skipped action due to dry run
        ADAPTIVE_ACTIONS_SKIPPED.labels(tenant=tenant, reason="dry_run").inc()

        # Log simulated action instead of applying
        log_scheduler_audit(
            tenant=tenant,
            operation="operator.adaptive.simulated",
            source="adaptive.auto",
            actor_type="adaptive.auto",
            metadata={
                "would_apply": rtype,
                "reason": "dry_run_enabled",
                "alert_id": payload.get("alert_id"),
                "alert_type": payload.get("alert_type"),
            },
        )
        return {"ok": True, "simulated": True, "action": rtype, "reason": "dry_run_enabled"}

    # All guardrails passed - record and apply action
    record_automation_action(tenant)

    # Phase XXXI: Record executed action
    ADAPTIVE_ACTIONS_EXECUTED.labels(tenant=tenant, mode="auto").inc()

    # assisted alert ack
    if rtype == "auto_ack_candidate":
        alert_id: str | None = payload.get("alert_id")
        alertname = payload.get("alert_type") or payload.get("alertname") or "unknown_alert"

        if not alert_id:
            return {"ok": False, "error": "alert_id required"}

        try:
            # Update acknowledgment state
            ALERT_ACK_STATE[alert_id] = {
                "ack": True,
                "ack_by": tenant,
                "ack_ts": datetime.now(UTC).isoformat(),
            }

            # Log the automated acknowledgment
            log_scheduler_audit(
                tenant=tenant,
                operation="operator.alert.ack",
                source="adaptive.auto",
                metadata={"alert_id": alert_id, "applied": "adaptive.auto"},
            )

            # Record to recovery timeline
            record_remediation_event(
                alertname=alertname,
                tenant=tenant,
                action="auto_ack",
                status="success",
                details=f"Auto-acknowledged alert {alert_id}",
            )

            return {"ok": True, "applied": "alert_ack", "alert_id": alert_id}
        except Exception as e:
            # Record failure too
            record_remediation_event(
                alertname=alertname,
                tenant=tenant,
                action="auto_ack",
                status="error",
                details=str(e),
            )
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unsupported action type: {rtype}"}


async def _learning_update_callback() -> None:
    """Periodic learning model update callback."""
    logger = logging.getLogger(__name__)
    try:
        # Trigger learning analysis to update models with new data
        if analyze_learning_patterns:
            analyze_learning_patterns(ACCU_SCHEDULER_AUDIT, window_hours=24)
            logger.info("Learning models updated with latest audit data")
    except Exception as exc:
        logger.warning("Learning update failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Phase IX: Starts AccuLynx scheduler loop.
    Phase XIII: Loads persisted state from disk.
    Phase XVII: Starts replication worker if enabled.
    Phase XVIII: Starts health monitor loop.
    """
    global STARTED_AT, PERSISTENCE_LAST_ERROR
    STARTED_AT = time.time()
    PERSISTENCE_LAST_ERROR = None

    try:
        print("[startup] Lifespan starting")

        # Phase XVII-B: Initialize persistence backends
        global _SQLITE_BACKEND, _JSON_BACKEND
        try:
            if SQLiteBackend:
                _SQLITE_BACKEND = SQLiteBackend(STORE_DSN)
                await _SQLITE_BACKEND.initialize()
                print("[persist] SQLite backend initialized")
            else:
                print("[persist] SQLite backend not available")
                PERSISTENCE_LAST_ERROR = "SQLite backend class not available"

            if JSONBackend:
                _JSON_BACKEND = JSONBackend(str(DATA_DIR))
                await _JSON_BACKEND.initialize()
                print("[persist] JSON fallback backend initialized")
            else:
                print("[persist] JSON backend not available")
                if PERSISTENCE_LAST_ERROR:
                    PERSISTENCE_LAST_ERROR += "; JSON backend not available"
                else:
                    PERSISTENCE_LAST_ERROR = "JSON backend not available"
        except Exception as e:
            print(f"[persist] Failed to initialize persistence backends: {e}")
            PERSISTENCE_LAST_ERROR = str(e)

        # Phase XIII: Load persisted state from persistence backends
        try:
            # wire DB_STORE adapter for legacy callsites (synchronous API)
            global DB_STORE
            DB_STORE = PersistenceAdapter(_SQLITE_BACKEND, _JSON_BACKEND, dual_write=DUAL_WRITE)

            # expose primary/fallback stores on app.state for new codepaths
            try:
                if STORE_MODE == "sqlite" and _SQLITE_BACKEND is not None:
                    app.state.primary_store = _SQLITE_BACKEND
                    app.state.fallback_store = (
                        _JSON_BACKEND if DUAL_WRITE and _JSON_BACKEND is not None else None
                    )
                else:
                    app.state.primary_store = _JSON_BACKEND
                    app.state.fallback_store = (
                        _SQLITE_BACKEND if DUAL_WRITE and _SQLITE_BACKEND is not None else None
                    )
            except Exception:
                # app.state may not be writable in some test harnesses; ignore
                pass

            schedules = {}
            audit_entries: list[dict[str, Any]] = []
            local_runs: list[dict[str, Any]] = []

            # Prefer configured STORE_MODE backend, fallback to JSON backend
            if STORE_MODE == "sqlite" and _SQLITE_BACKEND is not None:
                try:
                    schedules = await _SQLITE_BACKEND.load_schedules()
                    audit_entries = await _SQLITE_BACKEND.load_audit_entries(
                        limit=MAX_AUDIT_ENTRIES
                    )
                    local_runs = await _SQLITE_BACKEND.load_local_action_runs(
                        limit=MAX_LOCAL_ACTION_RUNS
                    )
                    print(
                        f"[persist] Loaded state from SQLite: schedules={len(schedules)}, audit={len(audit_entries)}, runs={len(local_runs)}"
                    )
                except Exception as e:
                    print(f"[persist] SQLite load failed: {e}")

            # Always try JSON fallback if primary didn't return data
            if (not schedules or not audit_entries or not local_runs) and _JSON_BACKEND is not None:
                try:
                    if not schedules:
                        schedules = await _JSON_BACKEND.load_schedules()
                    if not audit_entries:
                        audit_entries = await _JSON_BACKEND.load_audit_entries(
                            limit=MAX_AUDIT_ENTRIES
                        )
                    if not local_runs:
                        local_runs = await _JSON_BACKEND.load_local_action_runs(
                            limit=MAX_LOCAL_ACTION_RUNS
                        )
                    print(
                        f"[persist] Loaded state from JSON fallback: schedules={len(schedules)}, audit={len(audit_entries)}, runs={len(local_runs)}"
                    )
                except Exception as e:
                    print(f"[persist] JSON fallback load failed: {e}")

            # Apply to in-memory structures (keep previous semantics)
            try:
                if schedules:
                    ACCU_IMPORT_SCHEDULES.update(schedules)
                if audit_entries:
                    ACCU_SCHEDULER_AUDIT.extend(audit_entries[-MAX_AUDIT_ENTRIES:])
                if local_runs:
                    LOCAL_ACTION_RUNS.extend(local_runs[-MAX_LOCAL_ACTION_RUNS:])
                print(
                    f"[persist] In-memory state populated: schedules={len(ACCU_IMPORT_SCHEDULES)}, audit={len(ACCU_SCHEDULER_AUDIT)}, runs={len(LOCAL_ACTION_RUNS)}"
                )
            except Exception as e:
                print(f"[persist] Failed to populate in-memory state: {e}")
        except Exception as e:
            print(f"[persist] Failed to load persisted state: {e}")

        # Phase XVIII: Re-apply auto-paused state if needed
        try:
            count = _reapply_auto_paused()
            if count:
                print(f"[health] Re-applied auto-pause to {count} tenants")
        except Exception as e:
            print(f"[health] Failed to re-apply auto-pause: {e}")

        # Phase IX: Start scheduler loop defensively
        try:
            # asyncio.create_task(acculynx_scheduler_loop())
            print("[startup] Scheduler loop skipped for testing")
        except Exception as e:
            print(f"[startup] Scheduler failed to start: {e}")

        # Phase XVII: Start replication worker if enabled
        if REPLICATION_ENABLED:
            try:
                global _REPLICA_Q
                _REPLICA_Q = asyncio.Queue(maxsize=REPLICA_QUEUE_MAXSIZE)
                # asyncio.create_task(replication_loop())
                print("[startup] Replication skipped for testing")
            except Exception as e:
                print(f"[startup] Replication worker failed: {e}")

        # Phase XVIII: Start health monitor
        try:
            # asyncio.create_task(health_loop())
            print("[startup] Health monitor skipped for testing")
        except Exception as e:
            print(f"[startup] Health monitor failed: {e}")

        # Phase XXIII-C: Start adaptive auto-responder
        if adaptive_auto_responder:
            try:
                logger = logging.getLogger(__name__)
                # Get list of tenants from audit data or config
                tenants = list(
                    set(
                        entry.get("tenant") for entry in ACCU_SCHEDULER_AUDIT if entry.get("tenant")
                    )
                )
                if not tenants:
                    tenants = [None]  # system/global if no tenants found

                # Phase XXIII-D: Learning update callback
                async def learning_update():
                    """Periodic learning model updates."""
                    if analyze_learning_patterns:
                        try:
                            # Update learning models with recent data
                            analyze_learning_patterns(ACCU_SCHEDULER_AUDIT, window_hours=24)
                            logger.info("Learning models updated")
                        except Exception as e:
                            logger.warning("Learning update failed: %s", e)

                # Start the background auto-responder
                asyncio.create_task(
                    adaptive_auto_responder(
                        fetch_recommendations=_fetch_adaptive_recommendations,
                        apply_action=_apply_adaptive_action,
                        tenants=tenants,
                        interval_seconds=300,  # 5 minutes
                        confidence_threshold=0.9,
                        learning_update_callback=learning_update,
                    )
                )
                print(
                    f"[startup] Adaptive auto-responder started for {len(tenants)} tenants with learning integration"
                )
            except Exception as e:
                print(f"[startup] Adaptive auto-responder failed to start: {e}")
        else:
            print("[startup] Adaptive auto-responder not available")

        print("[startup] All startup tasks completed")

        yield

        print("[shutdown] Lifespan shutting down")
    except Exception as e:
        print(f"[startup] Lifespan exception: {e}")
        import traceback

        traceback.print_exc()
        raise
