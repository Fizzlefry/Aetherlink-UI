"""
Alert Rules API Router

Phase VI M6: CRUD endpoints for alert threshold rules.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alert_store
import alert_evaluator
from rbac import require_roles


router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertRuleCreate(BaseModel):
    """Schema for creating alert rules"""

    name: str = Field(..., description="Human-readable rule name")
    severity: Optional[str] = Field(
        None, description="Filter by severity (info, warning, error, critical)"
    )
    event_type: Optional[str] = Field(
        None, description="Filter by event type (e.g., autoheal.failed)"
    )
    source: Optional[str] = Field(
        None, description="Filter by source service (e.g., aether-auto-heal)"
    )
    window_seconds: int = Field(..., description="Time window in seconds", gt=0)
    threshold: int = Field(..., description="Number of events to trigger alert", gt=0)
    enabled: bool = Field(True, description="Whether rule is active")


class AlertRuleResponse(BaseModel):
    """Schema for alert rule responses"""

    id: int
    name: str
    severity: Optional[str]
    event_type: Optional[str]
    source: Optional[str]
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


@router.get(
    "/rules/{rule_id}", dependencies=[Depends(require_roles(["operator", "admin"]))]
)
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


@router.delete(
    "/rules/{rule_id}", dependencies=[Depends(require_roles(["operator", "admin"]))]
)
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
async def evaluate_now():
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
