"""
Alert Rules API Router

Phase VI M6: CRUD endpoints for alert threshold rules.
"""

import os
import sys

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alert_evaluator
import alert_store
from rbac import require_roles

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertRuleCreate(BaseModel):
    """Schema for creating alert rules"""

    name: str = Field(..., description="Human-readable rule name")
    severity: str | None = Field(
        None, description="Filter by severity (info, warning, error, critical)"
    )
    event_type: str | None = Field(None, description="Filter by event type (e.g., autoheal.failed)")
    source: str | None = Field(
        None, description="Filter by source service (e.g., aether-auto-heal)"
    )
    window_seconds: int = Field(..., description="Time window in seconds", gt=0)
    threshold: int = Field(..., description="Number of events to trigger alert", gt=0)
    enabled: bool = Field(True, description="Whether rule is active")


class AlertRuleResponse(BaseModel):
    """Schema for alert rule responses"""

    id: int
    name: str
    severity: str | None
    event_type: str | None
    source: str | None
    window_seconds: int
    threshold: int
    enabled: bool
    created_at: str
    updated_at: str


@router.post("/rules", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def create_rule(request: Request, rule: AlertRuleCreate):
    """
    Create a new alert threshold rule.

    Phase VI M6: Define conditions that trigger ops.alert.raised events.
    Phase VII M3: Auto-inject tenant_id from request header for tenant-scoped alerts.

    Example:
    {
      "name": "autoheal-failures-spike",
      "severity": "error",
      "event_type": "autoheal.failed",
      "window_seconds": 300,
      "threshold": 3,
      "enabled": true
    }

    This emits an alert if 3+ autoheal.failed events occur in 5 minutes.

    Requires: operator or admin role
    """
    # Phase VII M3: Auto-inject tenant_id from middleware
    tenant_id = getattr(request.state, "tenant_id", None)

    try:
        rule_id = alert_store.create_rule(
            name=rule.name,
            severity=rule.severity,
            event_type=rule.event_type,
            source=rule.source,
            window_seconds=rule.window_seconds,
            threshold=rule.threshold,
            enabled=rule.enabled,
            tenant_id=tenant_id,
        )

        created_rule = alert_store.get_rule(rule_id)
        if not created_rule:
            raise HTTPException(status_code=500, detail="Failed to retrieve created rule")

        return {
            "status": "ok",
            "rule_id": rule_id,
            "rule": created_rule,
        }
    except Exception as e:
        print(f"[alerts] ❌ Failed to create rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def list_rules():
    """
    List all alert threshold rules.

    Phase VI M6: Returns all defined alert rules with their current state.

    Requires: operator or admin role
    """
    try:
        rules = alert_store.list_rules()
        return {"status": "ok", "count": len(rules), "rules": rules}
    except Exception as e:
        print(f"[alerts] ❌ Failed to list rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/{rule_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def get_rule(rule_id: int):
    """
    Get a specific alert rule.

    Phase VI M6: Returns detailed information about a single rule.

    Requires: operator or admin role
    """
    rule = alert_store.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return {"status": "ok", "rule": rule}


@router.delete("/rules/{rule_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def delete_rule(rule_id: int):
    """
    Delete an alert rule.

    Phase VI M6: Permanently removes an alert threshold rule.

    Requires: operator or admin role
    """
    deleted = alert_store.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return {"status": "ok", "deleted": rule_id}


@router.patch(
    "/rules/{rule_id}/enabled",
    dependencies=[Depends(require_roles(["operator", "admin"]))],
)
async def update_rule_enabled(rule_id: int, enabled: bool):
    """
    Enable or disable an alert rule.

    Phase VI M6: Toggle rule evaluation without deleting the rule.

    Requires: operator or admin role
    """
    updated = alert_store.update_rule_enabled(rule_id, enabled)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return {"status": "ok", "rule_id": rule_id, "enabled": enabled}


@router.post("/evaluate", dependencies=[Depends(require_roles(["operator", "admin"]))])
async def evaluate_rules(request: Request):
    """
    Manually trigger alert rule evaluation.

    Phase VI M6: Runs alert evaluator immediately instead of waiting for
    the scheduled background task. Useful for testing and CI.

    Requires: operator or admin role
    """
    try:
        result = await alert_evaluator.evaluate_rules_once()
        return result
    except Exception as e:
        print(f"[alerts] ❌ Failed to evaluate rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Phase VII M5: Delivery Queue Visibility Endpoints


@router.get("/deliveries/stats", dependencies=[Depends(require_roles(["operator", "admin"]))])
def get_delivery_stats():
    """
    Get alert delivery queue health statistics.

    Phase VII M5: Returns metrics for operator visibility:
    - total_queued: Total deliveries in queue
    - pending_now: Deliveries ready for immediate attempt
    - near_failure: Deliveries close to max attempts
    - dedup_window_seconds: Current dedup window setting

    Requires: operator or admin role

    Example response:
    {
      "total_queued": 12,
      "pending_now": 3,
      "near_failure": 1,
      "dedup_window_seconds": 300
    }
    """
    try:
        import event_store

        stats = event_store.get_delivery_stats()
        return stats
    except Exception as e:
        print(f"[alerts] ❌ Failed to get delivery stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deliveries", dependencies=[Depends(require_roles(["operator", "admin"]))])
def list_delivery_queue(limit: int = 100):
    """
    List all queued alert deliveries.

    Phase VII M5: Returns queue entries for troubleshooting and monitoring.
    Shows delivery attempts, errors, and retry schedules.

    Query params:
    - limit: Max entries to return (default 100)

    Requires: operator or admin role

    Example response:
    [
      {
        "id": 42,
        "alert_event_id": "abc-123",
        "webhook_url": "https://hooks.slack.com/services/...",
        "attempt_count": 2,
        "max_attempts": 5,
        "next_attempt_at": "2024-01-15T10:30:00Z",
        "last_error": "HTTP 503: Service Unavailable",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:15:00Z"
      }
    ]
    """
    try:
        import event_store

        queue = event_store.get_delivery_queue(limit=limit)
        return {"status": "ok", "count": len(queue), "deliveries": queue}
    except Exception as e:
        print(f"[alerts] ❌ Failed to list delivery queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))
