"""
Alert Rule Templates Router

Phase VIII M2: Pre-built alert patterns that can be materialized into real alert rules.
Enables one-click creation of common alerting scenarios.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import alert_store
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from rbac import require_roles

router = APIRouter(prefix="/alerts/templates", tags=["alerts:templates"])

# Phase VIII M2: In-memory template registry
# In production, this could be backed by SQLite table
TEMPLATES_DB: dict[str, dict[str, Any]] = {}


class AlertTemplateIn(BaseModel):
    """Schema for creating alert rule templates"""

    name: str = Field(..., description="Template name (e.g., 'Delivery Failures → Slack')")
    description: str | None = Field(None, description="What this template does")
    event_type: str = Field(..., description="Event type to trigger on")
    source: str | None = Field(None, description="Optional source filter")
    severity: str = Field("warning", description="Event severity (info, warning, error, critical)")
    window_seconds: int = Field(300, description="Time window for threshold", gt=0)
    threshold: int = Field(1, description="Event count to trigger alert", gt=0)
    target_webhook: str | None = Field(None, description="Webhook URL for delivery")
    target_channel: str | None = Field(None, description="Channel name (e.g., #ops)")
    tenant_id: str | None = Field(None, description="Optional tenant restriction")


class AlertTemplate(AlertTemplateIn):
    """Schema for alert rule template responses"""

    id: str
    created_at: str
    updated_at: str


class MaterializeRequest(BaseModel):
    """Schema for materializing template into real alert rule"""

    tenant_id: str | None = Field(None, description="Tenant for the new rule")
    target_webhook: str | None = Field(None, description="Override webhook URL")
    enabled: bool = Field(True, description="Enable rule immediately")


@router.get("/", dependencies=[Depends(require_roles(["operator", "admin"]))])
def list_templates(tenant_id: str | None = None):
    """
    List all alert rule templates.

    Phase VIII M2: Returns pre-built alert patterns that can be materialized
    into real alert rules. Filterable by tenant.

    Query params:
    - tenant_id: Optional tenant filter (admin can see all)

    Requires: operator or admin role

    Example response:
    [
      {
        "id": "abc-123",
        "name": "Delivery Failures → Slack",
        "description": "Alerts when event deliveries start failing",
        "event_type": "ops.alert.delivery.failed",
        "severity": "warning",
        "window_seconds": 300,
        "threshold": 3,
        "target_webhook": "https://hooks.slack.com/...",
        "tenant_id": null,
        "created_at": "2024-01-15T10:00:00Z"
      }
    ]
    """
    items = list(TEMPLATES_DB.values())

    # Filter by tenant if specified
    if tenant_id:
        items = [i for i in items if i.get("tenant_id") == tenant_id or i.get("tenant_id") is None]

    return {"status": "ok", "count": len(items), "templates": items}


@router.post("/", dependencies=[Depends(require_roles(["operator", "admin"]))])
def create_template(payload: AlertTemplateIn):
    """
    Create a new alert rule template.

    Phase VIII M2: Define a reusable alert pattern that can be materialized
    into real alert rules with one click.

    Requires: operator or admin role

    Example request:
    {
      "name": "High Error Rate",
      "description": "Alert when errors exceed 10 in 5 minutes",
      "event_type": "ops.error",
      "severity": "error",
      "window_seconds": 300,
      "threshold": 10,
      "target_webhook": "https://hooks.slack.com/services/..."
    }
    """
    tpl_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    data = {
        "id": tpl_id,
        "created_at": now,
        "updated_at": now,
        **payload.model_dump(),
    }

    TEMPLATES_DB[tpl_id] = data
    print(f"[alert_templates] ✅ Created template '{payload.name}' (id: {tpl_id})")

    return {"status": "ok", "template": data}


@router.get("/{template_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
def get_template(template_id: str):
    """
    Get a specific alert rule template.

    Phase VIII M2: Retrieve template details by ID.

    Requires: operator or admin role
    """
    tpl = TEMPLATES_DB.get(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    return {"status": "ok", "template": tpl}


@router.put("/{template_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
def update_template(template_id: str, payload: AlertTemplateIn):
    """
    Update an existing alert rule template.

    Phase VIII M2: Modify template properties. Existing rules created from
    this template are not affected.

    Requires: operator or admin role
    """
    tpl = TEMPLATES_DB.get(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    # Update fields while preserving id and created_at
    tpl.update(payload.model_dump())
    tpl["updated_at"] = datetime.now(UTC).isoformat()

    print(f"[alert_templates] 🔄 Updated template '{payload.name}' (id: {template_id})")

    return {"status": "ok", "template": tpl}


@router.delete("/{template_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
def delete_template(template_id: str):
    """
    Delete an alert rule template.

    Phase VIII M2: Remove template from registry. Does not affect existing
    rules that were created from this template.

    Requires: operator or admin role
    """
    if template_id in TEMPLATES_DB:
        tpl = TEMPLATES_DB[template_id]
        del TEMPLATES_DB[template_id]
        print(f"[alert_templates] 🗑️  Deleted template '{tpl.get('name')}' (id: {template_id})")
        return {"status": "ok", "deleted": template_id}

    raise HTTPException(status_code=404, detail=f"Template {template_id} not found")


@router.post(
    "/{template_id}/materialize", dependencies=[Depends(require_roles(["operator", "admin"]))]
)
def materialize_template(template_id: str, payload: MaterializeRequest):
    """
    Materialize a template into a real alert rule.

    Phase VIII M2: Creates an actual alert rule from the template definition.
    The new rule will be monitored by the alert evaluator and can trigger
    webhook deliveries via the reliable delivery queue (Phase VII M5).

    Requires: operator or admin role

    Example request:
    {
      "tenant_id": "tenant-qa",
      "target_webhook": "https://hooks.slack.com/services/...",
      "enabled": true
    }

    Example response:
    {
      "status": "ok",
      "template_id": "abc-123",
      "rule_id": 42,
      "rule": {
        "id": 42,
        "name": "[tpl] Delivery Failures → Slack",
        "event_type": "ops.alert.delivery.failed",
        "severity": "warning",
        "window_seconds": 300,
        "threshold": 3,
        "tenant_id": "tenant-qa",
        "enabled": true
      }
    }
    """
    tpl = TEMPLATES_DB.get(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    # Determine tenant for the new rule
    tenant_id = payload.tenant_id or tpl.get("tenant_id")

    # Build alert rule from template
    # Prefix with [tpl] to indicate it came from a template
    rule_name = f"[tpl] {tpl['name']}"

    # Use webhook from request if provided, otherwise use template default
    # Note: In Phase VII M5, webhooks come from ALERT_WEBHOOKS env var
    # This is stored for reference but actual delivery uses global config
    rule_metadata = {}
    if payload.target_webhook:
        rule_metadata["target_webhook"] = payload.target_webhook
    elif tpl.get("target_webhook"):
        rule_metadata["target_webhook"] = tpl["target_webhook"]

    # Create the alert rule via alert_store
    rule_id = alert_store.create_rule(
        name=rule_name,
        severity=tpl.get("severity"),
        event_type=tpl.get("event_type"),
        source=tpl.get("source"),
        window_seconds=tpl.get("window_seconds", 300),
        threshold=tpl.get("threshold", 1),
        enabled=payload.enabled,
        tenant_id=tenant_id,
    )

    # Retrieve the created rule
    created_rule = alert_store.get_rule(rule_id)

    print(
        f"[alert_templates] 🎯 Materialized template '{tpl['name']}' → rule '{rule_name}' (id: {rule_id}, tenant: {tenant_id or 'system'})"
    )

    return {
        "status": "ok",
        "template_id": template_id,
        "rule_id": rule_id,
        "rule": created_rule,
    }


def seed_default_templates():
    """
    Seed default alert rule templates on startup.

    Phase VIII M2: Provides common alerting patterns out-of-the-box so
    operators don't start with an empty template list.
    """
    if TEMPLATES_DB:
        # Already seeded
        return

    print("[alert_templates] 🌱 Seeding default templates...")

    default_templates = [
        {
            "name": "Alert Delivery Failures",
            "description": "Notify when webhook deliveries fail after all retries (dead letter events)",
            "event_type": "ops.alert.delivery.failed",
            "source": "aether-command-center",
            "severity": "error",
            "window_seconds": 300,
            "threshold": 1,
            "target_channel": "#aether-ops",
        },
        {
            "name": "High Error Rate",
            "description": "Alert when error-level events exceed 10 in 5 minutes",
            "event_type": None,  # Any event type
            "source": None,  # Any source
            "severity": "error",
            "window_seconds": 300,
            "threshold": 10,
            "target_channel": "#aether-alerts",
        },
        {
            "name": "Critical Events",
            "description": "Immediate notification for any critical-severity event",
            "event_type": None,
            "source": None,
            "severity": "critical",
            "window_seconds": 60,
            "threshold": 1,
            "target_channel": "#aether-critical",
        },
        {
            "name": "AutoHeal Failures",
            "description": "Alert when auto-healing operations fail repeatedly",
            "event_type": "autoheal.failed",
            "source": "aether-auto-heal",
            "severity": "warning",
            "window_seconds": 600,
            "threshold": 3,
            "target_channel": "#aether-autoheal",
        },
        {
            "name": "Event Retention Issues",
            "description": "Alert when event pruning fails or encounters errors",
            "event_type": "ops.events.prune.failed",
            "source": "aether-command-center",
            "severity": "warning",
            "window_seconds": 3600,
            "threshold": 1,
            "target_channel": "#aether-ops",
        },
    ]

    now = datetime.now(UTC).isoformat()

    for template_def in default_templates:
        tpl_id = str(uuid.uuid4())
        TEMPLATES_DB[tpl_id] = {
            "id": tpl_id,
            "created_at": now,
            "updated_at": now,
            **template_def,
        }

    print(f"[alert_templates] ✅ Seeded {len(default_templates)} default templates")
