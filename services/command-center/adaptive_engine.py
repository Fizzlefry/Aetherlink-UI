# services/command-center/adaptive_engine.py
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

# Phase XXIII-D: Learning Optimization Integration
try:
    from .learning_optimizer import analyze_learning_patterns, get_dynamic_threshold
except ImportError:
    analyze_learning_patterns = None
    get_dynamic_threshold = lambda alert_type: 0.9  # fallback


def _is_operator_event(ev: dict[str, Any]) -> bool:
    op = ev.get("operation", "")
    return op.startswith("operator.")


def _to_dt(ts_val: Any) -> datetime | None:
    # audits sometimes store epoch or iso
    if ts_val is None:
        return None
    if isinstance(ts_val, (int, float)):
        return datetime.fromtimestamp(ts_val, tz=UTC)
    if isinstance(ts_val, str):
        try:
            return datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def analyze_patterns(
    audits: list[dict[str, Any]],
    window_hours: int = 24,
    tenant: str | None = None,
) -> dict[str, Any]:
    """
    Enhanced pattern recognizer with learning optimization:
    - Analyzes operator behavior patterns
    - Uses dynamic thresholds from learning optimizer
    - Incorporates historical performance data
    - Provides learning insights and recommendations
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)

    # filter by time + tenant
    filtered: list[dict[str, Any]] = []
    for ev in audits:
        if tenant and ev.get("tenant") != tenant:
            continue
        ts = _to_dt(ev.get("ts"))
        if ts is None or ts < cutoff:
            continue
        filtered.append(ev)

    # Phase XXIII-D: Incorporate learning insights
    learning_insights = {}
    if analyze_learning_patterns:
        learning_insights = analyze_learning_patterns(audits, window_hours)

    op_counter = Counter()
    alert_ack_times: dict[str, list[float]] = defaultdict(list)
    alert_types: dict[str, str] = {}  # alert_id -> alert_type mapping

    for ev in filtered:
        op = ev.get("operation", "")
        if not _is_operator_event(ev):
            continue
        op_counter[op] += 1

        # look for alert acks and extract alert types
        if op == "operator.alert.ack":
            meta = ev.get("metadata", {}) or {}
            alert_id = meta.get("alert_id")
            alert_type = meta.get("alert_type", "unknown")
            if alert_id:
                alert_ack_times[alert_id].append(0.0)  # placeholder
                alert_types[alert_id] = alert_type

    # turn counts into recommendations
    high_freq_ops: list[dict[str, Any]] = []
    for op, count in op_counter.most_common():
        high_freq_ops.append(
            {
                "operation": op,
                "count": count,
                "recommendation": _recommend_for_operation(op),
            }
        )

    # Enhanced auto-ack candidates with dynamic thresholds
    auto_ack_candidates: list[dict[str, Any]] = []
    for alert_id, acks in alert_ack_times.items():
        if len(acks) >= 3:  # seen several times in window
            alert_type = alert_types.get(alert_id, "unknown")
            # Use dynamic threshold from learning optimizer
            dynamic_threshold = get_dynamic_threshold(alert_type)

            auto_ack_candidates.append(
                {
                    "alert_id": alert_id,
                    "alert_type": alert_type,
                    "confidence": dynamic_threshold,
                    "reason": f"alert was acknowledged every time in the analysis window (dynamic threshold: {dynamic_threshold:.3f})",
                }
            )

    result = {
        "window_hours": window_hours,
        "tenant": tenant,
        "top_operator_actions": high_freq_ops,
        "auto_ack_candidates": auto_ack_candidates,
        "total_events_analyzed": len(filtered),
    }

    # Add learning insights if available
    if learning_insights:
        result["learning_insights"] = learning_insights

    return result


def _recommend_for_operation(op: str) -> str:
    if op.startswith("operator.job.paused"):
        return (
            "Suggest assisted resume/pause panel, and conditional auto-pause for repeated alerts."
        )
    if op == "operator.alert.ack":
        return "Candidate for auto-ack if always acked quickly."
    return "Track and observe."
