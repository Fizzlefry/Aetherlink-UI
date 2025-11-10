"""
Phase IX M3: Anomaly & Burst Detection
Real-time sliding-window anomaly detection for delivery failures.

Detects:
- Traffic spikes (>50% increase in 5min vs 1hr baseline)
- Failure clusters (>10x baseline failure rate)
- Per-tenant and per-endpoint anomalies

Performance: O(n) scan, sub-second for typical workloads
"""

from collections import defaultdict
from datetime import datetime
from typing import Any

# Configuration
WINDOW_MINUTES = 5  # Recent activity window
BASELINE_MINUTES = 60  # Historical baseline period
SPIKE_FACTOR = 1.5  # 50% increase threshold
FAILURE_MULTIPLIER = 10  # 10x baseline for failure clusters


def _group_by_tenant_endpoint(
    deliveries: list[dict[str, Any]],
) -> dict[tuple, list[dict[str, Any]]]:
    """Group deliveries by (tenant_id, target) for analysis."""
    buckets = defaultdict(list)
    for d in deliveries:
        tenant = d.get("tenant_id", "unknown")
        endpoint = d.get("target", "unknown")
        key = (tenant, endpoint)
        buckets[key].append(d)
    return buckets


def _is_failure(delivery: dict[str, Any]) -> bool:
    """Determine if a delivery represents a failure using M1 triage + status."""
    # Use Phase IX M1 triage classification
    triage_label = delivery.get("triage_label", "")
    if triage_label in ("permanent_4xx", "transient_endpoint_down"):
        return True

    # Fallback to status check
    status = delivery.get("status", "")
    return status in ("failed", "dead_letter")


def detect_anomalies(
    recent_deliveries: list[dict[str, Any]],
    baseline_deliveries: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Detect anomalies by comparing recent window to baseline.

    Args:
        recent_deliveries: Deliveries from last WINDOW_MINUTES
        baseline_deliveries: Deliveries from BASELINE_MINUTES period
        now: Current timestamp (for testing)

    Returns:
        List of incident dictionaries with detection metadata
    """
    now = now or datetime.utcnow()

    recent_buckets = _group_by_tenant_endpoint(recent_deliveries)
    baseline_buckets = _group_by_tenant_endpoint(baseline_deliveries)

    incidents = []

    for key, recent_items in recent_buckets.items():
        tenant_id, endpoint = key
        baseline_items = baseline_buckets.get(key, [])

        # Calculate totals
        recent_total = len(recent_items)
        baseline_total = max(len(baseline_items), 1)  # Avoid division by zero

        # Traffic spike detection
        spike_detected = recent_total > baseline_total * SPIKE_FACTOR

        # Failure cluster detection (using M1 triage classification)
        recent_failures = [r for r in recent_items if _is_failure(r)]
        baseline_failures = [b for b in baseline_items if _is_failure(b)]

        recent_fail_count = len(recent_failures)
        baseline_fail_count = max(len(baseline_failures), 1)

        failure_cluster_detected = recent_fail_count > baseline_fail_count * FAILURE_MULTIPLIER

        # Create incident if any anomaly detected
        if spike_detected or failure_cluster_detected:
            # Calculate severity
            severity = "critical" if failure_cluster_detected else "warning"

            # Build incident record
            incidents.append(
                {
                    "tenant_id": tenant_id,
                    "endpoint": endpoint,
                    "recent_count": recent_total,
                    "baseline_count": baseline_total,
                    "recent_failures": recent_fail_count,
                    "baseline_failures": baseline_fail_count,
                    "spike_detected": spike_detected,
                    "failure_cluster_detected": failure_cluster_detected,
                    "severity": severity,
                    "spike_multiplier": round(recent_total / baseline_total, 2),
                    "failure_multiplier": round(recent_fail_count / baseline_fail_count, 2),
                    "detected_at": now.isoformat() + "Z",
                    "window_minutes": WINDOW_MINUTES,
                    "baseline_minutes": BASELINE_MINUTES,
                }
            )

    # Sort by severity (critical first) and failure count
    incidents.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, -x["recent_failures"]))

    return incidents


def format_incident_message(incident: dict[str, Any]) -> str:
    """Generate human-readable incident message for UI display."""
    tenant = incident["tenant_id"]
    endpoint = incident["endpoint"]

    if incident["failure_cluster_detected"]:
        multiplier = incident["failure_multiplier"]
        failures = incident["recent_failures"]
        return (
            f"🚨 Failure Cluster: {failures} failures to {endpoint} "
            f"({multiplier}x normal) – Tenant: {tenant}"
        )
    elif incident["spike_detected"]:
        multiplier = incident["spike_multiplier"]
        count = incident["recent_count"]
        return (
            f"⚠️ Traffic Spike: {count} deliveries to {endpoint} "
            f"({multiplier}x normal) – Tenant: {tenant}"
        )

    return f"Anomaly detected: {endpoint} – Tenant: {tenant}"
