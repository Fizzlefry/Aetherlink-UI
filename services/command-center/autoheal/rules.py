"""
Phase X: Auto-Healing Rules & Policy Configuration
Safety limits and execution policies for autonomous healing actions.

This module defines:
- Maximum replay counts per strategy
- Time windows and cooldown periods
- Tenant-specific overrides
- Strategy priorities
"""

from typing import Dict, Any

# === STRATEGY EXECUTION LIMITS ===
# These prevent runaway auto-healing in edge cases

AUTOHEAL_LIMITS = {
    "REPLAY_RECENT": {
        # Maximum deliveries to replay in one cycle
        "max_deliveries": 25,
        
        # Only replay deliveries from last N minutes
        "time_window_minutes": 10,
        
        # Minimum confidence score to proceed
        "min_confidence": 0.70,
        
        # Cooldown between replays to same endpoint
        "cooldown_minutes": 5,
        
        # Only replay these triage labels
        "allowed_triage_labels": [
            "transient_endpoint_down",
            "rate_limited",
        ],
    },
    
    "DEFER_AND_MONITOR": {
        # How long to wait before rechecking
        "recheck_after_seconds": 120,
        
        # Maximum deferrals before escalating
        "max_deferrals": 3,
        
        # Alert threshold for too many deferrals
        "alert_after_deferrals": 2,
    },
    
    "ESCALATE_OPERATOR": {
        # Create incident ticket in UI
        "create_incident": True,
        
        # Send notification (future: email/Slack)
        "notify_operator": True,
        
        # Priority level
        "priority": "high",
        
        # Auto-assign to on-call operator
        "auto_assign": False,
    },
    
    "RATE_LIMIT_SOURCE": {
        # Reduce tenant delivery rate by this factor
        "throttle_factor": 0.5,
        
        # Duration of rate limit
        "duration_minutes": 30,
        
        # Require admin approval for limits > this duration
        "require_approval_above_minutes": 60,
    },
    
    "SILENCE_DUPES": {
        # Group identical errors within this window
        "dedup_window_seconds": 300,
        
        # Maximum occurrences before silencing
        "max_occurrences": 10,
        
        # Duration of silence
        "silence_duration_minutes": 15,
    },
}


# === STRATEGY PRIORITIES ===
# When multiple strategies are applicable, use this order

STRATEGY_PRIORITIES = {
    "ESCALATE_OPERATOR": 1,      # Highest priority - always defer to human
    "RATE_LIMIT_SOURCE": 2,      # Protect system resources
    "REPLAY_RECENT": 3,          # Auto-fix when safe
    "SILENCE_DUPES": 4,          # Reduce noise
    "DEFER_AND_MONITOR": 5,      # Lowest - wait and see
}


# === TENANT-SPECIFIC OVERRIDES ===
# Some tenants may have custom policies

TENANT_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "tenant-premium": {
        "autoheal_enabled": True,
        "max_replay_deliveries": 50,  # Higher limit for premium tier
        "auto_escalate_after_minutes": 5,  # Faster escalation
    },
    
    "tenant-qa": {
        "autoheal_enabled": True,
        "max_replay_deliveries": 100,  # QA can handle more aggressive healing
        "skip_operator_notification": True,  # Don't alert for QA failures
    },
    
    # Add more tenant configs as needed
}


# === GLOBAL SAFETY SETTINGS ===

GLOBAL_SAFETY = {
    # Maximum total auto-heals per hour (across all tenants/endpoints)
    "max_heals_per_hour": 100,
    
    # Maximum concurrent healing operations
    "max_concurrent_heals": 5,
    
    # Disable auto-healing globally (emergency kill switch)
    "autoheal_enabled": True,
    
    # Require explicit operator approval for critical incidents
    "require_approval_for_critical": True,
    
    # Log every auto-healing decision to Phase VIII M10 audit
    "audit_all_actions": True,
    
    # Dry-run mode: predict but don't execute
    "dry_run": False,
}


# === INCIDENT ESCALATION THRESHOLDS ===

ESCALATION_THRESHOLDS = {
    # Escalate if failures exceed this count
    "max_failures_before_escalation": 50,
    
    # Escalate if same endpoint fails repeatedly
    "max_consecutive_endpoint_failures": 5,
    
    # Escalate if multiple tenants affected simultaneously
    "multi_tenant_incident_count": 3,
    
    # Escalate if system-wide failure rate exceeds this
    "system_failure_rate_threshold": 0.30,  # 30%
}


# === TIME WINDOWS ===

TIME_WINDOWS = {
    # Recent activity window for analysis
    "recent_window_minutes": 5,
    
    # Baseline comparison period
    "baseline_window_minutes": 60,
    
    # Historical pattern analysis period
    "historical_analysis_hours": 24,
    
    # Incident memory (how long to track resolved incidents)
    "incident_memory_hours": 168,  # 1 week
}


def get_tenant_config(tenant_id: str) -> Dict[str, Any]:
    """
    Get effective configuration for a tenant, applying overrides.
    
    Args:
        tenant_id: Tenant identifier
    
    Returns:
        Merged configuration dictionary
    """
    # Start with global defaults
    config = {
        "autoheal_enabled": GLOBAL_SAFETY["autoheal_enabled"],
        "max_replay_deliveries": AUTOHEAL_LIMITS["REPLAY_RECENT"]["max_deliveries"],
        "cooldown_minutes": AUTOHEAL_LIMITS["REPLAY_RECENT"]["cooldown_minutes"],
        "require_approval": False,
    }
    
    # Apply tenant-specific overrides
    if tenant_id in TENANT_OVERRIDES:
        config.update(TENANT_OVERRIDES[tenant_id])
    
    return config


def is_autoheal_allowed(
    tenant_id: str,
    endpoint: str,
    strategy: str
) -> tuple[bool, str]:
    """
    Check if auto-healing is allowed for this combination.
    
    Args:
        tenant_id: Tenant requesting healing
        endpoint: Target endpoint
        strategy: Proposed strategy
    
    Returns:
        (allowed: bool, reason: str)
    """
    # Check global kill switch
    if not GLOBAL_SAFETY["autoheal_enabled"]:
        return False, "Auto-healing disabled globally"
    
    # Check tenant configuration
    tenant_config = get_tenant_config(tenant_id)
    if not tenant_config.get("autoheal_enabled", True):
        return False, f"Auto-healing disabled for tenant {tenant_id}"
    
    # Check if strategy is recognized
    if strategy not in AUTOHEAL_LIMITS:
        return False, f"Unknown strategy: {strategy}"
    
    # Check dry-run mode
    if GLOBAL_SAFETY["dry_run"]:
        return False, "System in dry-run mode (prediction only)"
    
    # All checks passed
    return True, "Auto-healing allowed"


def get_strategy_limits(strategy: str, tenant_id: str) -> Dict[str, Any]:
    """
    Get execution limits for a strategy with tenant overrides applied.
    
    Args:
        strategy: Strategy name
        tenant_id: Tenant identifier
    
    Returns:
        Limits dictionary
    """
    # Get base limits
    limits = AUTOHEAL_LIMITS.get(strategy, {}).copy()
    
    # Apply tenant overrides
    tenant_config = get_tenant_config(tenant_id)
    
    if strategy == "REPLAY_RECENT":
        if "max_replay_deliveries" in tenant_config:
            limits["max_deliveries"] = tenant_config["max_replay_deliveries"]
    
    return limits
