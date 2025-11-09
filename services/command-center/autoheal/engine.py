"""
Phase X: Auto-Healing Engine
Main executor for autonomous healing operations.

Flow:
1. Detect anomalies (Phase IX M3)
2. Analyze deliveries + apply M1 triage context
3. Choose healing strategy (predictors)
4. Execute action within safety limits (rules)
5. Log to audit trail (Phase VIII M10)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .predictors import (
    choose_strategy,
    predict_outcome_probability,
    analyze_triage_distribution,
    should_apply_autoheal,
)
from .rules import (
    AUTOHEAL_LIMITS,
    GLOBAL_SAFETY,
    get_tenant_config,
    is_autoheal_allowed,
    get_strategy_limits,
)


@dataclass
class AutohealResult:
    """Result of an auto-healing cycle execution."""
    run_at: str
    incidents_detected: int
    actions_taken: List[Dict[str, Any]]
    actions_skipped: List[Dict[str, Any]]
    total_replays: int
    total_escalations: int
    total_deferrals: int
    execution_time_ms: float
    dry_run: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# In-memory state tracking (replace with Redis/DB in production)
_healing_history: List[Dict[str, Any]] = []
_last_heal_by_endpoint: Dict[str, datetime] = {}


def _get_recent_deliveries_for_incident(
    incident: Dict[str, Any],
    time_window_minutes: int = 10
) -> List[Dict[str, Any]]:
    """
    Fetch recent deliveries affected by an incident.
    Replace with actual database query in production.
    
    Args:
        incident: Anomaly incident
        time_window_minutes: How far back to look
    
    Returns:
        List of delivery records
    """
    # TODO: Replace with actual DB query
    # Example query structure:
    #
    # from session import get_session
    # from sqlalchemy import text
    #
    # async with get_session() as session:
    #     query = text("""
    #         SELECT id, tenant_id, target, status, triage_label, triage_score
    #         FROM deliveries
    #         WHERE tenant_id = :tenant_id
    #           AND target = :endpoint
    #           AND created_at >= :since
    #           AND status IN ('failed', 'dead_letter')
    #         ORDER BY created_at DESC
    #         LIMIT :max_deliveries
    #     """)
    #     result = await session.execute(query, {
    #         "tenant_id": incident["tenant_id"],
    #         "endpoint": incident["endpoint"],
    #         "since": datetime.utcnow() - timedelta(minutes=time_window_minutes),
    #         "max_deliveries": 100,
    #     })
    #     return [dict(row) for row in result.fetchall()]
    
    # For now, return empty list (will be wired in integration)
    return []


def _replay_delivery(delivery_id: str, meta: Dict[str, Any]) -> bool:
    """
    Replay a single delivery via Phase VIII M7/M9 mechanism.
    
    Args:
        delivery_id: Delivery to replay
        meta: Metadata for audit trail
    
    Returns:
        Success boolean
    """
    # TODO: Replace with actual replay call
    # Example:
    #
    # from routers.delivery_history import replay_delivery_internal
    # return await replay_delivery_internal(delivery_id, meta)
    
    # For now, simulate success
    print(f"[AUTOHEAL] Replaying delivery {delivery_id} with meta: {meta}")
    return True


def _log_autoheal_action(
    action: str,
    incident: Dict[str, Any],
    strategy: str,
    details: Dict[str, Any]
) -> None:
    """
    Log auto-healing action to Phase VIII M10 audit trail.
    
    Args:
        action: Action type (replay, escalate, defer, etc.)
        incident: Triggering incident
        strategy: Strategy applied
        details: Additional action details
    """
    # TODO: Replace with actual M10 audit call
    # Example:
    #
    # from operator_audit import log_operator_action
    # log_operator_action(
    #     operator_id="system:autoheal",
    #     action=action,
    #     resource_type="delivery",
    #     resource_id=incident.get("endpoint"),
    #     tenant_id=incident.get("tenant_id"),
    #     meta={
    #         "strategy": strategy,
    #         "incident": incident,
    #         **details,
    #     }
    # )
    
    # For now, print to console
    print(f"[AUDIT] {action} - {strategy} - {incident['endpoint']}")


def _execute_replay_strategy(
    incident: Dict[str, Any],
    limits: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute REPLAY_RECENT strategy.
    
    Args:
        incident: Anomaly incident
        limits: Strategy execution limits
        dry_run: If True, predict but don't execute
    
    Returns:
        Action result dictionary
    """
    tenant_id = incident["tenant_id"]
    endpoint = incident["endpoint"]
    time_window = limits.get("time_window_minutes", 10)
    max_deliveries = limits.get("max_deliveries", 25)
    allowed_labels = limits.get("allowed_triage_labels", [])
    
    # Fetch affected deliveries
    deliveries = _get_recent_deliveries_for_incident(incident, time_window)
    
    # Filter by triage label (only replay safe categories)
    eligible = [
        d for d in deliveries
        if d.get("triage_label") in allowed_labels
    ][:max_deliveries]
    
    if dry_run:
        return {
            "strategy": "REPLAY_RECENT",
            "dry_run": True,
            "would_replay": [d["id"] for d in eligible],
            "count": len(eligible),
            "incident": incident,
        }
    
    # Execute replays
    replayed = []
    for delivery in eligible:
        success = _replay_delivery(
            delivery["id"],
            meta={
                "autoheal": True,
                "strategy": "REPLAY_RECENT",
                "incident_id": incident.get("detected_at"),
            }
        )
        if success:
            replayed.append(delivery["id"])
    
    # Log action
    _log_autoheal_action(
        action="autoheal_replay",
        incident=incident,
        strategy="REPLAY_RECENT",
        details={
            "replayed_count": len(replayed),
            "delivery_ids": replayed,
        }
    )
    
    return {
        "strategy": "REPLAY_RECENT",
        "executed": True,
        "replayed": replayed,
        "count": len(replayed),
        "incident": incident,
    }


def _execute_escalate_strategy(
    incident: Dict[str, Any],
    limits: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute ESCALATE_OPERATOR strategy.
    
    Creates operator task / incident ticket.
    """
    if dry_run:
        return {
            "strategy": "ESCALATE_OPERATOR",
            "dry_run": True,
            "would_create_incident": True,
            "priority": limits.get("priority", "high"),
            "incident": incident,
        }
    
    # Log escalation
    _log_autoheal_action(
        action="autoheal_escalate",
        incident=incident,
        strategy="ESCALATE_OPERATOR",
        details={
            "priority": limits.get("priority", "high"),
            "reason": "Failure cluster exceeds auto-healing thresholds",
        }
    )
    
    return {
        "strategy": "ESCALATE_OPERATOR",
        "executed": True,
        "created_incident": True,
        "priority": limits.get("priority", "high"),
        "message": f"Escalated incident for {incident['endpoint']} – requires operator review",
        "incident": incident,
    }


def _execute_defer_strategy(
    incident: Dict[str, Any],
    limits: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute DEFER_AND_MONITOR strategy.
    
    Marks incident for recheck after cooldown period.
    """
    recheck_after = limits.get("recheck_after_seconds", 120)
    
    if dry_run:
        return {
            "strategy": "DEFER_AND_MONITOR",
            "dry_run": True,
            "would_recheck_after_seconds": recheck_after,
            "incident": incident,
        }
    
    # Track deferred incident
    # TODO: Store in database with recheck timestamp
    
    _log_autoheal_action(
        action="autoheal_defer",
        incident=incident,
        strategy="DEFER_AND_MONITOR",
        details={
            "recheck_after_seconds": recheck_after,
            "reason": "Waiting for clearer pattern",
        }
    )
    
    return {
        "strategy": "DEFER_AND_MONITOR",
        "executed": True,
        "recheck_after_seconds": recheck_after,
        "message": f"Deferred {incident['endpoint']} for {recheck_after}s",
        "incident": incident,
    }


def run_autoheal_cycle(
    now: Optional[datetime] = None,
    dry_run: Optional[bool] = None
) -> AutohealResult:
    """
    Execute one auto-healing cycle.
    
    Args:
        now: Current timestamp (for testing)
        dry_run: If True, predict but don't execute actions
    
    Returns:
        AutohealResult with execution summary
    
    Flow:
    1. Detect anomalies using Phase IX M3
    2. For each anomaly:
       a. Fetch recent deliveries
       b. Analyze triage distribution (M1 context)
       c. Choose strategy (predictors)
       d. Check safety limits (rules)
       e. Execute if approved
    3. Aggregate results and return
    """
    start_time = datetime.utcnow()
    now = now or start_time
    dry_run = dry_run if dry_run is not None else GLOBAL_SAFETY["dry_run"]
    
    # Import here to avoid circular dependencies
    # In production, these should be properly structured
    try:
        from anomaly_detector import detect_anomalies
    except ImportError:
        # Fallback for testing
        def detect_anomalies(recent, baseline, timestamp):
            return []
    
    # Step 1: Detect current anomalies (Phase IX M3)
    # This requires recent + baseline deliveries
    # For production integration, wire up the actual calls
    incidents = []  # detect_anomalies(...) would go here
    
    actions_taken = []
    actions_skipped = []
    total_replays = 0
    total_escalations = 0
    total_deferrals = 0
    
    # Step 2: Process each incident
    for incident in incidents:
        tenant_id = incident["tenant_id"]
        endpoint = incident["endpoint"]
        
        # Check if auto-healing is allowed
        allowed, reason = is_autoheal_allowed(tenant_id, endpoint, "REPLAY_RECENT")
        if not allowed:
            actions_skipped.append({
                "incident": incident,
                "reason": reason,
            })
            continue
        
        # Check endpoint cooldown
        last_heal = _last_heal_by_endpoint.get(endpoint)
        if last_heal:
            minutes_since = (now - last_heal).total_seconds() / 60
            cooldown = AUTOHEAL_LIMITS["REPLAY_RECENT"]["cooldown_minutes"]
            if minutes_since < cooldown:
                actions_skipped.append({
                    "incident": incident,
                    "reason": f"Cooldown active ({minutes_since:.1f}m < {cooldown}m)",
                })
                continue
        
        # Fetch recent deliveries for context
        deliveries = _get_recent_deliveries_for_incident(incident)
        
        # Analyze triage distribution (Phase IX M1)
        triage_analysis = analyze_triage_distribution(deliveries)
        
        # Build context for predictor
        context = {
            **triage_analysis,
            "endpoint_in_maintenance": False,  # TODO: Check maintenance calendar
            "minutes_since_last_heal": 999,    # TODO: Check history
        }
        
        # Choose healing strategy
        strategy = choose_strategy(incident, context)
        
        # Predict outcome probability
        probability = predict_outcome_probability(incident, strategy, context)
        
        # Final safety check
        should_apply, check_reason = should_apply_autoheal(incident, strategy, context)
        if not should_apply:
            actions_skipped.append({
                "incident": incident,
                "strategy": strategy,
                "probability": probability,
                "reason": check_reason,
            })
            continue
        
        # Get strategy limits (with tenant overrides)
        limits = get_strategy_limits(strategy, tenant_id)
        
        # Execute strategy
        result = None
        if strategy == "REPLAY_RECENT":
            result = _execute_replay_strategy(incident, limits, dry_run)
            total_replays += result.get("count", 0)
        elif strategy == "ESCALATE_OPERATOR":
            result = _execute_escalate_strategy(incident, limits, dry_run)
            total_escalations += 1
        elif strategy == "DEFER_AND_MONITOR":
            result = _execute_defer_strategy(incident, limits, dry_run)
            total_deferrals += 1
        else:
            # Unknown strategy - log and skip
            actions_skipped.append({
                "incident": incident,
                "strategy": strategy,
                "reason": f"Strategy '{strategy}' not implemented",
            })
            continue
        
        # Track execution
        if result and not dry_run:
            _last_heal_by_endpoint[endpoint] = now
            _healing_history.append({
                "timestamp": now.isoformat() + "Z",
                "incident": incident,
                "strategy": strategy,
                "result": result,
            })
        
        actions_taken.append({
            "strategy": strategy,
            "probability": probability,
            **result,
        })
    
    # Calculate execution time
    execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    return AutohealResult(
        run_at=now.isoformat() + "Z",
        incidents_detected=len(incidents),
        actions_taken=actions_taken,
        actions_skipped=actions_skipped,
        total_replays=total_replays,
        total_escalations=total_escalations,
        total_deferrals=total_deferrals,
        execution_time_ms=execution_time_ms,
        dry_run=dry_run,
    )


def get_healing_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent auto-healing execution history."""
    return _healing_history[-limit:]


def clear_endpoint_cooldown(endpoint: str) -> None:
    """Clear cooldown for an endpoint (admin override)."""
    if endpoint in _last_heal_by_endpoint:
        del _last_heal_by_endpoint[endpoint]
