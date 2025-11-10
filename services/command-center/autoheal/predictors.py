"""
Phase X: Auto-Healing Predictors
Strategy selection engine based on anomaly patterns and M1 triage intelligence.

Strategies:
- REPLAY_RECENT: Safe to automatically replay (transient failures)
- DEFER_AND_MONITOR: Wait and recheck (unclear pattern)
- ESCALATE_OPERATOR: Requires human decision (permanent failures)
- RATE_LIMIT_SOURCE: Throttle incoming from specific tenant
- SILENCE_DUPES: Suppress duplicate failure alerts
"""

from datetime import datetime
from typing import Any

# Strategy definitions
STRATEGY_REPLAY_RECENT = "REPLAY_RECENT"
STRATEGY_DEFER = "DEFER_AND_MONITOR"
STRATEGY_ESCALATE = "ESCALATE_OPERATOR"
STRATEGY_RATE_LIMIT = "RATE_LIMIT_SOURCE"
STRATEGY_SILENCE = "SILENCE_DUPES"


def choose_strategy(incident: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    """
    Select auto-healing strategy based on incident characteristics.

    Args:
        incident: Anomaly incident from M3 detector
        context: Additional context (recent deliveries, tenant config, etc.)

    Returns:
        Strategy name string

    Decision tree:
    1. Check if pattern is transient (spike without persistent failures) → REPLAY
    2. Check if failure cluster is massive (>50 failures) → ESCALATE
    3. Check if endpoint shows intermittent pattern → DEFER
    4. Check if single tenant flooding → RATE_LIMIT
    5. Default to DEFER for safety
    """
    context = context or {}

    # Extract incident signals
    spike_detected = incident.get("spike_detected", False)
    failure_cluster = incident.get("failure_cluster_detected", False)
    recent_failures = incident.get("recent_failures", 0)
    recent_count = incident.get("recent_count", 0)
    severity = incident.get("severity", "warning")

    # Extract context signals
    triage_labels = context.get("triage_labels", [])
    historical_pattern = context.get("historical_pattern", {})
    tenant_config = context.get("tenant_config", {})

    # Rule 1: Massive failure cluster → escalate to operator
    # This is too risky to auto-fix without human validation
    if failure_cluster and recent_failures > 50:
        return STRATEGY_ESCALATE

    # Rule 2: Traffic spike without failures → likely capacity issue
    # Don't auto-replay, just monitor
    if spike_detected and not failure_cluster:
        if recent_failures < 5:
            return STRATEGY_DEFER  # Probably just traffic increase

    # Rule 3: High percentage of transient failures → safe to replay
    # Use Phase IX M1 triage intelligence
    transient_count = sum(
        1 for label in triage_labels if label in ("transient_endpoint_down", "rate_limited")
    )
    transient_ratio = transient_count / len(triage_labels) if triage_labels else 0.0

    if transient_ratio > 0.7 and recent_failures <= 25:
        # >70% transient, small enough batch → safe to auto-replay
        return STRATEGY_REPLAY_RECENT

    # Rule 4: All permanent 4xx errors → don't auto-replay
    permanent_count = sum(1 for label in triage_labels if label == "permanent_4xx")
    permanent_ratio = permanent_count / len(triage_labels) if triage_labels else 0.0

    if permanent_ratio > 0.8:
        # >80% permanent failures → needs manual fix
        return STRATEGY_ESCALATE

    # Rule 5: Single tenant generating >90% of traffic → rate limit
    if context.get("single_tenant_dominant", False):
        return STRATEGY_RATE_LIMIT

    # Rule 6: Repeated identical errors → silence duplicates
    if context.get("duplicate_error_ratio", 0.0) > 0.9:
        return STRATEGY_SILENCE

    # Default: defer and monitor
    # Wait for more data before acting
    return STRATEGY_DEFER


def predict_outcome_probability(
    incident: dict[str, Any], strategy: str, context: dict[str, Any] | None = None
) -> float:
    """
    Predict probability of successful healing outcome.

    Args:
        incident: Anomaly incident
        strategy: Proposed healing strategy
        context: Additional context

    Returns:
        Probability between 0.0 and 1.0

    Uses:
    - M1 triage scores
    - M4 historical replay success rates
    - Endpoint reliability metrics
    """
    context = context or {}

    # Base probability by strategy
    base_probs = {
        STRATEGY_REPLAY_RECENT: 0.75,  # Phase VIII M9 has good success rate
        STRATEGY_DEFER: 0.60,  # Medium confidence in wait-and-see
        STRATEGY_ESCALATE: 0.90,  # High confidence operator can fix
        STRATEGY_RATE_LIMIT: 0.70,  # Usually effective for floods
        STRATEGY_SILENCE: 0.85,  # Safe operation, low risk
    }

    prob = base_probs.get(strategy, 0.50)

    # Adjust based on triage scores (Phase IX M1)
    avg_triage_score = context.get("avg_triage_score", 50)
    if avg_triage_score > 80:
        prob += 0.10  # High confidence classification → better prediction
    elif avg_triage_score < 30:
        prob -= 0.15  # Low confidence → worse prediction

    # Adjust based on historical success (Phase IX M4)
    endpoint_success_rate = context.get("endpoint_success_rate", 0.5)
    if strategy == STRATEGY_REPLAY_RECENT:
        # Replay probability heavily influenced by endpoint reliability
        prob = (prob + endpoint_success_rate) / 2

    # Adjust based on incident severity
    severity = incident.get("severity", "warning")
    if severity == "critical" and strategy != STRATEGY_ESCALATE:
        prob -= 0.20  # Critical incidents need human oversight

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, prob))


def analyze_triage_distribution(deliveries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze triage label distribution for context enrichment.

    Args:
        deliveries: List of delivery records with triage labels

    Returns:
        Statistics for strategy decision-making
    """
    if not deliveries:
        return {
            "transient_ratio": 0.0,
            "permanent_ratio": 0.0,
            "rate_limited_ratio": 0.0,
            "avg_triage_score": 50.0,
            "labels": [],
        }

    labels = [d.get("triage_label", "unknown") for d in deliveries]
    scores = [d.get("triage_score", 50) for d in deliveries]

    total = len(labels)
    transient_count = sum(1 for l in labels if l == "transient_endpoint_down")
    permanent_count = sum(1 for l in labels if l == "permanent_4xx")
    rate_limited_count = sum(1 for l in labels if l == "rate_limited")

    return {
        "transient_ratio": transient_count / total,
        "permanent_ratio": permanent_count / total,
        "rate_limited_ratio": rate_limited_count / total,
        "avg_triage_score": sum(scores) / len(scores),
        "labels": labels,
        "total_deliveries": total,
    }


def should_apply_autoheal(
    incident: dict[str, Any], strategy: str, context: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """
    Final safety check before executing auto-healing action.

    Args:
        incident: Anomaly incident
        strategy: Proposed strategy
        context: Additional context

    Returns:
        (should_apply: bool, reason: str)
    """
    context = context or {}

    # Check 1: Never auto-heal critical incidents without operator review
    if incident.get("severity") == "critical" and strategy != STRATEGY_ESCALATE:
        return False, "Critical severity requires operator review"

    # Check 2: Ensure minimum confidence threshold
    prob = predict_outcome_probability(incident, strategy, context)
    if prob < 0.5:
        return False, f"Confidence too low ({prob:.1%})"

    # Check 3: Check if endpoint is in maintenance mode
    if context.get("endpoint_in_maintenance", False):
        return False, "Endpoint in scheduled maintenance"

    # Check 4: Rate limit check - don't heal same endpoint too frequently
    last_heal_minutes = context.get("minutes_since_last_heal", 999)
    if last_heal_minutes < 5:
        return False, f"Too soon since last heal ({last_heal_minutes}m ago)"

    # Check 5: Business hours constraint (optional, configurable)
    if context.get("require_business_hours", False):
        now = datetime.utcnow()
        # Simple check: 9 AM - 5 PM UTC (refine with timezone later)
        if not (9 <= now.hour < 17):
            return False, "Auto-heal restricted to business hours"

    # All checks passed
    return True, f"Confidence: {prob:.1%}"
