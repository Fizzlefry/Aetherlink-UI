"""
Phase IX M1: Auto-Triage Engine
Automatically classifies delivery failures into actionable categories.

This is v1 — rule-based classification. Future versions can use ML models.
The interface (TriageResult) stays stable even as the implementation evolves.

Categories:
  - transient_endpoint_down: 5xx, timeouts, connection errors (safe to retry)
  - permanent_4xx: 4xx errors (needs manual fix)
  - rate_limited: 429 or rate limit signals (wait before retry)
  - unknown: No clear pattern (manual review)

Integration:
  Called by delivery_history.py to enrich delivery records with triage metadata.
  Used by Phase IX M2 (Smart Replay Advisor) to identify safe replay candidates.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TriageResult:
    """
    Classification result for a single delivery.

    Attributes:
        label: Category identifier (e.g., "transient_endpoint_down")
        score: Confidence 0-100 (higher = more certain)
        reason: Human-readable explanation
        recommended_action: Suggested next step (e.g., "retry", "manual_fix")
    """

    label: str
    score: int
    reason: str
    recommended_action: str


def _str(v: Any) -> str:
    """Safe string conversion for dict values that might be None."""
    return "" if v is None else str(v)


def classify_delivery(delivery: dict) -> TriageResult:
    """
    Classify a delivery failure into a triage category.

    Rule-based v1 implementation. Checks HTTP status codes, error messages,
    and delivery status to categorize failures.

    Expected delivery fields (best-effort):
        - status: Overall delivery status (e.g., "failed", "dead_letter")
        - http_status or status_code: HTTP response code from target
        - error_message: Error text from delivery attempt
        - attempt_count: Number of retry attempts
        - endpoint or webhook_url: Target URL

    Returns:
        TriageResult with classification metadata

    Examples:
        >>> delivery = {"status": "failed", "http_status": 503}
        >>> result = classify_delivery(delivery)
        >>> result.label
        'transient_endpoint_down'
        >>> result.recommended_action
        'retry'
    """
    status = _str(delivery.get("status", "")).lower()
    http_status = delivery.get("http_status") or delivery.get("status_code")
    error_msg = _str(delivery.get("error_message", "")).lower()

    # Rule 1: Rate limiting (highest priority)
    # 429 status or explicit rate limit language in error
    if http_status == 429 or "rate limit" in error_msg or "too many requests" in error_msg:
        return TriageResult(
            label="rate_limited",
            score=95,
            reason="Upstream returned 429 or rate-limit signal.",
            recommended_action="wait_and_retry",
        )

    # Rule 2: Transient failures (5xx, timeouts, connection issues)
    # These are temporary and usually resolve on retry
    if (
        (isinstance(http_status, int) and 500 <= http_status <= 599)
        or "connection refused" in error_msg
        or "timeout" in error_msg
        or "timed out" in error_msg
        or "upstream error" in error_msg
        or "network error" in error_msg
        or "service unavailable" in error_msg
    ):
        return TriageResult(
            label="transient_endpoint_down",
            score=90,
            reason="Upstream appears temporarily unavailable (5xx/timeout/connection error).",
            recommended_action="retry",
        )

    # Rule 3: Permanent failures (4xx client errors)
    # Usually indicate configuration issues or auth problems
    if isinstance(http_status, int) and 400 <= http_status <= 499:
        return TriageResult(
            label="permanent_4xx",
            score=85,
            reason=f"Upstream returned {http_status}, likely a configuration or auth error.",
            recommended_action="manual_fix",
        )

    # Rule 4: Failed status but no strong classification signal
    # Delivery is marked failed but we can't determine why
    if status in ("failed", "error", "dead_letter"):
        return TriageResult(
            label="unknown",
            score=60,
            reason="Delivery failed but no specific pattern matched.",
            recommended_action="review_then_retry",
        )

    # Rule 5: Catch-all for anything else
    # Shouldn't happen often but handle gracefully
    return TriageResult(
        label="unknown",
        score=50,
        reason="No error pattern detected.",
        recommended_action="none",
    )


# Future expansion hooks:
# - Add ML model fallback: if rules don't match, call model.predict()
# - Track classification accuracy: store triage + outcome for training
# - Add tenant-specific rules: some customers have custom error patterns
# - Support for multi-error deliveries: classify based on most recent error
