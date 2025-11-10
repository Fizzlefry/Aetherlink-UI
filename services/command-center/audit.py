"""
AetherLink Security Audit Logging Middleware

Phase III M6: Tracks all requests to sensitive services with:
- Timestamp
- Service name
- Path and method
- User roles (from X-User-Roles header)
- Response status code
- Optional: Client IP

This provides operational visibility into:
- Who is accessing what
- Authorization failures (401/403)
- Service usage patterns
- Security audit trail

Phase XX M4: Enhanced with WebSocket broadcasting for live operator activity feed
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import Request

# Configure audit logger
logger = logging.getLogger("aether.audit")
logging.basicConfig(level=logging.INFO)

# In-memory audit statistics (per-service)
audit_stats: dict[str, Any] = {
    "total": 0,
    "denied_401": 0,
    "denied_403": 0,
    "by_path": {},
    "by_status": {},
}

# Import WebSocket manager for live activity broadcasting
# Use try/except to avoid circular imports
try:
    from ws_manager import operator_activity_ws_manager
except ImportError:
    operator_activity_ws_manager = None


async def _broadcast_operator_activity(payload: dict[str, Any]) -> None:
    """Broadcast operator activity to WebSocket subscribers."""
    if operator_activity_ws_manager is None:
        return
    try:
        await operator_activity_ws_manager.broadcast(
            {
                "type": "operator_activity",
                "payload": payload,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to broadcast operator activity: {e}")


async def audit_middleware(request: Request, call_next):
    """
    FastAPI middleware that logs audit records for every request.

    Usage in main.py:
        from audit import audit_middleware
        app.middleware("http")(audit_middleware)
    """
    path = request.url.path
    method = request.method
    roles = request.headers.get("X-User-Roles", "")
    client_ip = request.client.host if request.client else "unknown"
    start_time = datetime.utcnow().isoformat()

    # Process request
    response = await call_next(request)

    # Build audit record
    record = {
        "ts": start_time,
        "service": getattr(request.app, "title", "unknown"),
        "path": path,
        "method": method,
        "roles": roles,
        "status": response.status_code,
        "client_ip": client_ip,
    }

    # Log to stdout (Docker logs capture this)
    logger.info("[AUDIT] %s", json.dumps(record))

    # Update in-memory stats
    audit_stats["total"] += 1

    if response.status_code == 401:
        audit_stats["denied_401"] += 1
    elif response.status_code == 403:
        audit_stats["denied_403"] += 1

    # Track by path
    audit_stats["by_path"][path] = audit_stats["by_path"].get(path, 0) + 1

    # Track by status code
    status_key = str(response.status_code)
    audit_stats["by_status"][status_key] = audit_stats["by_status"].get(status_key, 0) + 1

    # Broadcast operator activity to WebSocket subscribers (fire-and-forget)
    # Only broadcast operator-relevant paths (avoid noise from health checks, metrics, etc.)
    if path.startswith("/ops/") or path.startswith("/api/"):
        activity_payload = {
            "path": path,
            "method": method,
            "status_code": response.status_code,
            "ts": start_time,
            "tenant": request.headers.get("x-tenant") or request.headers.get("x-tenant-id"),
            "actor": request.headers.get("x-ops-user")
            or request.headers.get("x-user-roles")
            or "unknown",
        }
        # Fire-and-forget so we don't block the request
        asyncio.create_task(_broadcast_operator_activity(activity_payload))

    return response


def get_audit_stats() -> dict[str, Any]:
    """
    Get current audit statistics.

    Returns:
        Dict with total, denied counts, and breakdowns by path/status
    """
    return {
        "total_requests": audit_stats["total"],
        "denied_401_unauthorized": audit_stats["denied_401"],
        "denied_403_forbidden": audit_stats["denied_403"],
        "by_path": dict(
            sorted(audit_stats["by_path"].items(), key=lambda x: x[1], reverse=True)[:10]
        ),  # Top 10 paths
        "by_status": audit_stats["by_status"],
    }


def reset_audit_stats():
    """Reset audit statistics (useful for testing)"""
    audit_stats["total"] = 0
    audit_stats["denied_401"] = 0
    audit_stats["denied_403"] = 0
    audit_stats["by_path"].clear()
    audit_stats["by_status"].clear()
