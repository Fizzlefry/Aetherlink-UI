"""Auto follow-up tasks for high-probability leads."""

from __future__ import annotations

import time

import requests
from prometheus_client import Counter

FOLLOWUP_JOBS_TOTAL = Counter(
    "followup_jobs_total",
    "Total follow-up jobs by strategy/outcome",
    ["strategy", "result"],
)


def _post_note(base_url: str, lead_id: str, note: str) -> None:
    """Optional: write a note to memory or timeline endpoint."""
    try:
        requests.post(
            f"{base_url}/v1/lead/{lead_id}/note",
            json={"note": note},
            timeout=5,
        )
    except Exception:
        pass


def run_followup(
    *,
    base_url: str,
    lead_id: str,
    strategy: str,
    message: str,
    api_key: str | None = None,
) -> str:
    """
    Simple HTTP follow-up hook; replace with SMS/Email/CRM later.

    Args:
        base_url: API base URL
        lead_id: Lead identifier
        strategy: Follow-up strategy name (for metrics)
        message: Follow-up message content
        api_key: Optional API key for authentication

    Returns:
        "ok" or "error"
    """
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    payload = {
        "lead_id": lead_id,
        "message": message,
        "strategy": strategy,
        "ts": int(time.time()),
    }

    try:
        r = requests.post(
            f"{base_url}/ops/followup-hook",
            json=payload,
            headers=headers,
            timeout=8,
        )
        r.raise_for_status()
        FOLLOWUP_JOBS_TOTAL.labels(strategy=strategy, result="ok").inc()
        _post_note(base_url, lead_id, f"Auto-followup sent ({strategy})")
        return "ok"
    except Exception:
        FOLLOWUP_JOBS_TOTAL.labels(strategy=strategy, result="error").inc()
        _post_note(base_url, lead_id, f"Auto-followup failed ({strategy})")
        return "error"
