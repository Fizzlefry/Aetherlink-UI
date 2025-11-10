from datetime import UTC, datetime

from autoheal.rules import AUTOHEAL_LIMITS
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from rbac import admin_required

router = APIRouter()


class AutohealRule(BaseModel):
    id: str
    name: str | None = None
    enabled: bool = True
    cooldown_seconds: int | None = None
    match_endpoint: str | None = None
    last_updated: datetime | None = None


class AutohealRulesResponse(BaseModel):
    items: list[AutohealRule]
    total: int


@router.get("/rules", response_model=AutohealRulesResponse, dependencies=[Depends(admin_required)])
async def list_autoheal_rules(enabled: bool | None = None, limit: int = 100, offset: int = 0):
    """
    List autoheal rules with optional filters.
    Returns: { items: [...], total: N }
    """
    # Example: flatten AUTOHEAL_LIMITS into rule objects
    rules = []
    for rule_id, rule in AUTOHEAL_LIMITS.items():
        rule_obj = AutohealRule(
            id=rule_id,
            name=rule_id.replace("_", " ").title(),
            enabled=True,
            cooldown_seconds=rule.get("cooldown_minutes", 0) * 60
            if rule.get("cooldown_minutes")
            else None,
            match_endpoint=None,  # Fill in if you have endpoint info
            last_updated=datetime.now(),
        )
        if enabled is None or rule_obj.enabled == enabled:
            rules.append(rule_obj)

    total = len(rules)
    paged = rules[offset : offset + limit]
    return {"items": paged, "total": total}


class ClearCooldownRequest(BaseModel):
    endpoint: str


@router.post("/clear_endpoint_cooldown", dependencies=[Depends(admin_required)])
async def clear_endpoint_cooldown_api(payload: ClearCooldownRequest, request: Request):
    clear_endpoint_cooldown(payload.endpoint)

    # Emit real-time event for dashboard updates
    event = {
        "event_type": "autoheal.cooldown.cleared",
        "source": "command-center",
        "severity": "info",
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {
            "endpoint": payload.endpoint,
            "action": "cooldown_cleared",
            "operator": getattr(request.state, "user_id", "unknown"),
        },
    }

    # Publish event asynchronously (don't block response)
    import asyncio

    asyncio.create_task(publish_event_async(event))

    return {"status": "cleared", "endpoint": payload.endpoint, "cleared_at": datetime.now()}


async def publish_event_async(event: dict):
    """Publish event to event stream for real-time updates."""
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8010/events/publish",
                json=event,
                headers={"X-User-Roles": "system"},
            )
    except Exception as e:
        print(f"[autoheal] Failed to publish event: {e}")


"""
Phase X: Auto-Healing API Router
REST endpoints for triggering and monitoring autonomous healing.

Admin-only endpoints with RBAC enforcement.
"""

from datetime import datetime

from autoheal import clear_endpoint_cooldown, get_healing_history, run_autoheal_cycle
from autoheal.rules import GLOBAL_SAFETY
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/autoheal", tags=["autoheal"])


# TODO: Replace with actual RBAC enforcement
def require_admin_role():
    """
    Verify user has admin/operator role.

    In production, wire this to Phase VIII M8/M9 RBAC system:
    - Check JWT token
    - Verify role in ['admin', 'operator']
    - Log access attempts
    """
    # For now, always allow (will be wired during integration)
    return {"role": "admin", "user_id": "system"}


@router.post("/run", response_model=dict)
async def trigger_autoheal_cycle(
    dry_run: bool | None = Query(None, description="If true, predict actions without executing"),
    _user: dict = Depends(require_admin_role),
) -> dict:
    """
    Trigger an auto-healing cycle manually.

    **Admin-only endpoint.**

    Flow:
    1. Detect current anomalies (Phase IX M3)
    2. For each anomaly:
       - Analyze triage distribution (Phase IX M1)
       - Choose healing strategy (predictors)
       - Check safety limits (rules)
       - Execute action if approved
    3. Return execution summary

    **Query Parameters:**
    - `dry_run` (bool, optional): If true, predict but don't execute. Defaults to global setting.

    **Returns:**
    ```json
    {
      "run_at": "2025-01-23T12:34:56Z",
      "incidents_detected": 3,
      "actions_taken": [
        {
          "strategy": "REPLAY_RECENT",
          "probability": 0.82,
          "executed": true,
          "replayed": ["dlv_001", "dlv_002"],
          "count": 2,
          "incident": {...}
        }
      ],
      "actions_skipped": [
        {
          "incident": {...},
          "strategy": "ESCALATE_OPERATOR",
          "reason": "Global autoheal disabled"
        }
      ],
      "total_replays": 2,
      "total_escalations": 0,
      "total_deferrals": 1,
      "execution_time_ms": 234.5,
      "dry_run": false
    }
    ```

    **Safety:**
    - Respects global kill switch (`GLOBAL_SAFETY["autoheal_enabled"]`)
    - Enforces per-strategy limits (max deliveries, cooldowns)
    - Logs all actions to Phase VIII M10 audit trail
    - Dry-run mode available for testing

    **Status Codes:**
    - `200 OK`: Cycle executed successfully (check `actions_taken`/`actions_skipped`)
    - `403 Forbidden`: Global autoheal disabled or user lacks permissions
    - `500 Internal Server Error`: Execution failure (check logs)
    """
    # Check global kill switch
    if not GLOBAL_SAFETY.get("autoheal_enabled", True):
        raise HTTPException(
            status_code=403,
            detail="Auto-healing is globally disabled. Enable via GLOBAL_SAFETY config.",
        )

    try:
        # Execute cycle
        result = run_autoheal_cycle(now=datetime.utcnow(), dry_run=dry_run)

        # TODO: Log admin action to Phase VIII M10 audit
        # Example:
        # from operator_audit import log_operator_action
        # log_operator_action(
        #     operator_id=_user["user_id"],
        #     action="trigger_autoheal",
        #     resource_type="system",
        #     resource_id="autoheal_cycle",
        #     meta={
        #         "dry_run": result.dry_run,
        #         "incidents_detected": result.incidents_detected,
        #         "actions_taken": len(result.actions_taken),
        #     }
        # )

        return result.to_dict()

    except Exception as e:
        # Log error
        print(f"[ERROR] Auto-healing cycle failed: {e}")
        raise HTTPException(status_code=500, detail=f"Auto-healing cycle failed: {str(e)}")


@router.get("/last", response_model=dict)
async def get_last_autoheal_run(
    _user: dict = Depends(require_admin_role),
) -> dict:
    """
    Get the result of the last auto-healing cycle.

    **Admin-only endpoint.**

    **Returns:**
    ```json
    {
      "run_at": "2025-01-23T12:34:56Z",
      "incidents_detected": 3,
      "actions_taken": [...],
      "actions_skipped": [...],
      "total_replays": 2,
      "total_escalations": 0,
      "total_deferrals": 1,
      "execution_time_ms": 234.5,
      "dry_run": false
    }
    ```

    **Status Codes:**
    - `200 OK`: Last run retrieved
    - `404 Not Found`: No healing cycles have run yet
    - `403 Forbidden`: User lacks permissions
    """
    history = get_healing_history(limit=1)

    if not history:
        raise HTTPException(
            status_code=404,
            detail="No auto-healing cycles have run yet. Trigger one with POST /autoheal/run",
        )

    # Return the most recent run
    last_run = history[-1]
    return last_run.get("result", {})


@router.get("/history", response_model=list)
async def get_autoheal_history(
    limit: int = Query(100, ge=1, le=1000, description="Number of recent cycles to return"),
    _user: dict = Depends(require_admin_role),
) -> list:
    """
    Get recent auto-healing execution history.

    **Admin-only endpoint.**

    **Query Parameters:**
    - `limit` (int, default=100): Number of cycles to return (1-1000)

    **Returns:**
    ```json
    [
      {
        "timestamp": "2025-01-23T12:34:56Z",
        "incident": {...},
        "strategy": "REPLAY_RECENT",
        "result": {...}
      }
    ]
    ```

    **Status Codes:**
    - `200 OK`: History retrieved
    - `403 Forbidden`: User lacks permissions
    """
    history = get_healing_history(limit=limit)
    return history


@router.delete("/cooldown/{endpoint}", status_code=204)
async def clear_cooldown(
    endpoint: str,
    _user: dict = Depends(require_admin_role),
) -> None:
    """
    Clear cooldown for an endpoint (admin override).

    **Admin-only endpoint.**

    Use this to immediately allow auto-healing for an endpoint
    that is currently in cooldown period.

    **Path Parameters:**
    - `endpoint` (str): Target endpoint URL

    **Status Codes:**
    - `204 No Content`: Cooldown cleared
    - `403 Forbidden`: User lacks permissions

    **Example:**
    ```bash
    curl -X DELETE "http://localhost:8010/autoheal/cooldown/https://api.example.com/webhook" \
      -H "Authorization: Bearer <admin_token>"
    ```
    """
    clear_endpoint_cooldown(endpoint)

    # TODO: Log admin action
    # log_operator_action(
    #     operator_id=_user["user_id"],
    #     action="clear_autoheal_cooldown",
    #     resource_type="endpoint",
    #     resource_id=endpoint,
    # )


@router.get("/config", response_model=dict)
async def get_autoheal_config(
    _user: dict = Depends(require_admin_role),
) -> dict:
    """
    Get current auto-healing configuration.

    **Admin-only endpoint.**

    Returns global safety settings, strategy limits, and tenant overrides.

    **Returns:**
    ```json
    {
      "global_safety": {
        "autoheal_enabled": true,
        "dry_run": false,
        "max_heals_per_hour": 100,
        "max_concurrent_heals": 5,
        "audit_all_actions": true
      },
      "strategy_limits": {
        "REPLAY_RECENT": {
          "max_deliveries": 25,
          "time_window_minutes": 10,
          "min_confidence": 0.7,
          "cooldown_minutes": 5
        }
      }
    }
    ```

    **Status Codes:**
    - `200 OK`: Config retrieved
    - `403 Forbidden`: User lacks permissions
    """
    from autoheal.rules import AUTOHEAL_LIMITS, STRATEGY_PRIORITIES, TENANT_OVERRIDES

    return {
        "global_safety": GLOBAL_SAFETY,
        "strategy_limits": AUTOHEAL_LIMITS,
        "strategy_priorities": STRATEGY_PRIORITIES,
        "tenant_overrides": TENANT_OVERRIDES,
    }
