# services/command-center/routers/events.py
"""
Event Control Plane API endpoints.
Phase VI M1: Event publish + schema
Phase VI M2: Event storage + streaming
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import event_store
from rbac import require_roles

router = APIRouter(prefix="/events", tags=["events"])

# Event schema registry
EVENT_SCHEMAS = {
    "service.registered": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted when a service registers with Command Center",
    },
    "service.health.failed": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted when a monitored service fails health",
    },
    "autoheal.attempted": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted by auto-heal when it attempts to restart a container",
    },
    "autoheal.succeeded": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted by auto-heal when restart succeeds",
    },
    "autoheal.failed": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted by auto-heal when restart fails",
    },
    "ai.fallback.used": {
        "required": ["event_type", "source", "timestamp", "payload"],
        "description": "Emitted by AI Orchestrator when it uses a fallback provider",
    },
}

# Simple broadcaster for SSE (M2)
subscribers: list[asyncio.Queue] = []


@router.get("/schema", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def list_schemas():
    """List all registered event schemas."""
    return {
        "status": "ok",
        "count": len(EVENT_SCHEMAS),
        "schemas": [{"event_type": et, **meta} for et, meta in EVENT_SCHEMAS.items()],
    }


@router.get("/schema/{event_type}", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def get_schema(event_type: str):
    """Get schema for specific event type."""
    schema = EVENT_SCHEMAS.get(event_type)
    if not schema:
        raise HTTPException(status_code=404, detail="Unknown event_type")
    return {
        "status": "ok",
        "event_type": event_type,
        "schema": schema,
    }


@router.post("/publish")
async def publish_event(event: dict, request: Request):
    """
    Publish an event to Command Center.

    Phase VI M1: Validate + normalize + store
    Phase VI M2: Fan out to SSE subscribers
    """
    # Validate event_type
    event_type = event.get("event_type")
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")

    schema = EVENT_SCHEMAS.get(event_type)
    if not schema:
        raise HTTPException(status_code=400, detail=f"Unknown event_type '{event_type}'")

    # Validate required fields
    for field in schema.get("required", []):
        if field not in event:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Normalize timestamp
    if "timestamp" not in event or not event["timestamp"]:
        event["timestamp"] = datetime.now(UTC).isoformat()

    # Generate event_id if not provided
    if "event_id" not in event or not event["event_id"]:
        event["event_id"] = str(uuid.uuid4())

    # Auto-inject tenant_id from middleware (Phase VII M3)
    if "tenant_id" not in event:
        header_tenant = getattr(request.state, "tenant_id", None)
        event["tenant_id"] = header_tenant if header_tenant else "default"

    # Default severity
    if "severity" not in event:
        event["severity"] = "info"

    # Attach metadata for audit
    client_host = request.client.host if request.client else "unknown"
    event["_meta"] = {
        "received_at": datetime.now(UTC).isoformat(),
        "client_ip": client_host,
    }

    # Save to persistent store (M2)
    try:
        event_store.save_event(event)
    except Exception as e:
        print(f"[events] ⚠️  Failed to save event: {e}")
        # Don't fail publish if storage fails

    # Fan out to SSE subscribers (M2)
    await _broadcast_event(event)

    return {
        "status": "ok",
        "stored": True,
        "event_type": event_type,
        "event_id": event["event_id"],
        "received_at": event["_meta"]["received_at"],
    }


@router.get("/recent", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def recent(
    request: Request,
    limit: int = 50,
    event_type: str | None = None,
    source: str | None = None,
    tenant_id: str | None = None,
    severity: str | None = None,
    since: str | None = None,
):
    """
    Retrieve recent events from storage.

    Query parameters:
    - limit: Maximum number of events (default 50)
    - event_type: Filter by event type
    - source: Filter by source service
    - tenant_id: Filter by tenant ID
    - severity: Filter by severity level (info, warning, error, critical)
    - since: Filter by timestamp (ISO format)

    Phase VI M5: Added severity and since filtering
    Phase VII M3: Tenant-aware filtering with role-based access control
    """
    # Extract tenant from header (set by TenantContextMiddleware)
    header_tenant = getattr(request.state, "tenant_id", None)
    
    # Role-based tenant enforcement:
    # - Admin/operator with no query param → uses header tenant (or none for all)
    # - Admin/operator with query param → can override to see specific tenant
    # - Non-admin → locked to header tenant (but require_roles already blocks non-admin)
    user_roles = getattr(request.state, "user_roles", [])
    is_admin = any(r in ("admin", "operator") for r in user_roles)
    
    # Effective tenant: use query param if admin provided it, otherwise header
    effective_tenant = tenant_id if (is_admin and tenant_id) else header_tenant
    
    try:
        data = event_store.list_recent(
            limit=limit,
            event_type=event_type,
            source=source,
            tenant_id=effective_tenant,
            severity=severity,
            since=since,
        )
    except Exception as e:
        print(f"[events] ⚠️  Failed to fetch events: {e}")
        data = []

    return {
        "status": "ok",
        "count": len(data),
        "events": data,
    }


@router.get("/stats", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def stats(
    request: Request,
    tenant_id: str | None = None,
):
    """
    Get event statistics for operational overview.

    Phase VI M5: Returns total events, last 24h count, and breakdown by severity.
    Phase VII M3: Added tenant_id filtering for multi-tenant stats.

    Query parameters:
    - tenant_id: Filter stats by tenant ID (optional)

    Returns:
        - total: Total event count
        - last_24h: Events in last 24 hours
        - by_severity: Breakdown by severity level (info, warning, error, critical)
    """
    # Extract tenant from header (set by TenantContextMiddleware)
    header_tenant = getattr(request.state, "tenant_id", None)
    
    # Role-based tenant enforcement
    user_roles = getattr(request.state, "user_roles", [])
    is_admin = any(r in ("admin", "operator") for r in user_roles)
    
    # Effective tenant: use query param if admin provided it, otherwise header
    effective_tenant = tenant_id if (is_admin and tenant_id) else header_tenant
    
    try:
        stats_data = event_store.get_event_stats(tenant_id=effective_tenant)
    except Exception as e:
        print(f"[events] ⚠️  Failed to fetch stats: {e}")
        stats_data = {"total": 0, "last_24h": 0, "by_severity": {}}

    return {
        "status": "ok",
        **stats_data,
    }


async def _broadcast_event(event: dict):
    """Broadcast event to all SSE subscribers."""
    if not subscribers:
        return

    msg = json.dumps(event)
    for q in subscribers:
        try:
            await q.put(msg)
        except Exception:
            # Subscriber may have disconnected
            pass


@router.get("/stream", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def stream_events():
    """
    SSE endpoint: UI can connect and receive events in real-time.

    Returns Server-Sent Events stream.
    """
    q: asyncio.Queue = asyncio.Queue()
    subscribers.append(q)

    async def event_generator():
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            if q in subscribers:
                subscribers.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================================
# Phase VII M2: Event Retention & Archival
# ============================================================================

@router.post("/prune", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def manual_prune():
    """
    Manually trigger event pruning.
    
    Phase VII M2: Deletes events older than EVENT_RETENTION_DAYS.
    Optionally archives them first if EVENT_ARCHIVE_ENABLED=true.
    
    Requires: operator or admin role
    
    Returns:
        Pruning summary with counts and configuration
    """
    try:
        result = event_store.prune_old_events()
        
        # Emit ops.events.pruned event for observability
        prune_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "ops.events.pruned",
            "source": "aether-command-center",
            "severity": "info",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": "system",
            "payload": {
                "pruned_count": result["pruned_count"],
                "cutoff": result["cutoff"],
                "retention_days": result["retention_days"],
                "archived": result["archived"],
                "archived_count": result.get("archived_count"),
                "strategy": "archive+delete" if result["archived"] else "delete-only",
            },
            "_meta": {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "client_ip": "127.0.0.1",
            },
        }
        
        # Save prune event (after prune, so it doesn't get immediately deleted)
        event_store.save_event(prune_event)
        
        # Broadcast to SSE subscribers
        await _broadcast_event(prune_event)
        
        return result
    
    except Exception as e:
        print(f"[events] ❌ Prune failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retention", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def retention_settings():
    """
    Get current event retention configuration.
    
    Phase VII M2: Returns retention settings for ops visibility.
    
    Requires: operator or admin role
    
    Returns:
        Retention configuration
    """
    return event_store.get_retention_settings()
