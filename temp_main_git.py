import asyncio
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import alert_evaluator
import alert_store
import event_store
import httpx
from audit import audit_middleware, get_audit_stats
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter
from pydantic import BaseModel, Field
from rbac import require_roles
from routers import alert_templates, alerts, delivery_history, events, operator_audit_router
from starlette.middleware.base import BaseHTTPMiddleware


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


app = FastAPI(title="AetherLink Command Center", version="0.1.0")

# Phase VII M3: Add tenant context middleware
app.add_middleware(TenantContextMiddleware)

# Recent local action runs (newest first)
LOCAL_ACTION_RUNS: list[dict[str, Any]] = []
MAX_LOCAL_ACTION_RUNS = 50

# Prometheus metric for local actions
local_actions_total = Counter(
    "aetherlink_local_actions_total",
    "Total local actions invoked from UI",
    ["tenant", "action"],
)


# Phase VI: Initialize event store and alert store on startup
@app.on_event("startup")
async def startup_event():
    """Initialize event control plane, alert system, and retention worker."""
    print("[command-center] ≡ƒÜÇ Starting Command Center")
    event_store.init_db()
    print("[command-center] Γ£à Event Control Plane ready")

    # Phase VI M6: Initialize alert store and start evaluator
    alert_store.init_db()
    print("[command-center] Γ£à Alert Rules database ready")

    # Start alert evaluator background task
    asyncio.create_task(alert_evaluator.alert_evaluator_loop())
    print("[command-center] ≡ƒÜ¿ Alert Evaluator started")

    # Phase VII M5: Start delivery dispatcher background task
    asyncio.create_task(alert_evaluator.delivery_dispatcher_loop())
    print("[command-center] ≡ƒô« Delivery Dispatcher started")

    # Phase VII M2: Start retention worker background task
    asyncio.create_task(retention_worker())
    print("[command-center] ≡ƒùæ∩╕Å  Retention Worker started")

    # Phase VIII M2: Seed default alert templates
    alert_templates.seed_default_templates()
    print("[command-center] ≡ƒôï Alert Templates ready")

    # Phase VIII M3: Seed delivery history
    delivery_history.seed_delivery_history()
    print("[command-center] ≡ƒô£ Delivery History ready")


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


# Phase VI: Mount event and alert routers
app.include_router(events.router)
app.include_router(alerts.router)
# Phase VIII M2: Mount alert templates router
app.include_router(alert_templates.router)
# Phase VIII M3: Mount delivery history router
app.include_router(delivery_history.router)
# Phase VIII M10: Mount operator audit router
app.include_router(operator_audit_router.router)

# Phase III M6: Security Audit Logging
app.middleware("http")(audit_middleware)

# RBAC: Only operators and admins can access ops endpoints
operator_only = require_roles(["operator", "admin"])

# Add CORS middleware to allow UI to call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your UI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/ops/health", dependencies=[Depends(operator_only)])
async def ops_health():
    """
    Aggregates health status from all AetherLink services.
    Returns overall status and individual service details.

    Requires: operator or admin role
    """
    results = {}
    async with httpx.AsyncClient(timeout=2.5) as client:
        for name, url in SERVICE_MAP.items():
            try:
                resp = await client.get(url)
                results[name] = {
                    "status": "up" if resp.status_code == 200 else "degraded",
                    "http_status": resp.status_code,
                    "url": url,
                }
            except Exception as e:
                results[name] = {
                    "status": "down",
                    "error": str(e),
                    "url": url,
                }

    # Determine overall status
    overall = "up" if all(s["status"] == "up" for s in results.values()) else "degraded"

    return {
        "status": overall,
        "services": results,
    }


@app.get("/ops/ping")
def ping():
    """
    Simple health check for the Command Center service itself.
    """
    return {"status": "ok"}


@app.get("/audit/stats", dependencies=[Depends(operator_only)])
async def audit_stats():
    """
    Get audit statistics for security monitoring.

    Phase III M6: Returns request counts, auth failures, and usage patterns.
    Requires: operator or admin role
    """
    return get_audit_stats()


# Phase IV: Service Registry Endpoints (v1.13.0)


@app.post("/ops/register", dependencies=[Depends(operator_only)])
async def register_service(payload: ServiceRegistration):
    """
    Register a service with the Command Center.

    Services can announce themselves at startup instead of being hardcoded.
    Useful for dynamic service discovery and auto-configuration.

    Requires: operator or admin role
    """
    # Upsert: update if exists, insert if new
    REGISTERED_SERVICES[payload.name] = {
        "name": payload.name,
        "url": payload.url,
        "health_url": payload.health_url or f"{payload.url}/ping",
        "version": payload.version,
        "roles_required": payload.roles_required or [],
        "tags": payload.tags or [],
        "last_seen": _now_iso(),
    }

    # Phase VI M4: Emit registration event
    await publish_event_internal(
        "service.registered",
        {
            "service": payload.name,
            "url": payload.url,
            "version": payload.version,
            "tags": payload.tags or [],
            "severity": "info",
        },
    )

    return {"status": "ok", "registered": payload.name, "service_count": len(REGISTERED_SERVICES)}


@app.get("/ops/services", dependencies=[Depends(operator_only)])
def list_services():
    """
    List all registered services.

    Returns all services that have registered via POST /ops/register.
    Useful for discovering available services and their capabilities.

    Requires: operator or admin role
    """
    return {
        "status": "ok",
        "count": len(REGISTERED_SERVICES),
        "services": list(REGISTERED_SERVICES.values()),
    }


@app.delete("/ops/services/{name}", dependencies=[Depends(operator_only)])
async def delete_service(name: str):
    """
    Remove a service from the registry.

    Useful for cleaning up stale service registrations.

    Requires: operator or admin role
    """
    if name not in REGISTERED_SERVICES:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found in registry")

    del REGISTERED_SERVICES[name]

    # Phase VI M4: Emit unregistration event
    await publish_event_internal(
        "service.unregistered",
        {
            "service": name,
            "severity": "warning",
        },
    )

    return {"status": "ok", "deleted": name, "remaining_count": len(REGISTERED_SERVICES)}


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
            "error": None
        }
        
        LOCAL_ACTION_RUNS.insert(0, run_rec)
        if len(LOCAL_ACTION_RUNS) > MAX_LOCAL_ACTION_RUNS:
            LOCAL_ACTION_RUNS.pop()
        
        # Increment Prometheus counter
        local_actions_total.labels(tenant=tenant, action=action).inc()
        
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
