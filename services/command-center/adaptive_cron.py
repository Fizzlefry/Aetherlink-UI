# services/command-center/adaptive_cron.py
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_CONFIDENCE_THRESHOLD = 0.9


async def adaptive_auto_responder(
    fetch_recommendations: Callable[..., Any],
    apply_action: Callable[[dict[str, Any]], Any],
    *,
    tenants: Sequence[str | None] | None = None,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    learning_update_callback: Callable[[], Any] | None = None,
) -> None:
    """
    Periodically:
    1. fetch /ops/adaptive/recommendations (per tenant)
    2. find auto-ack candidates with confidence >= threshold
    3. call /ops/adaptive/apply for each
    4. update learning models with new data
    5. swallow errors (this should never take your API down)
    """
    # if no tenants provided, just run once for "system"/global
    tenants = tenants or [None]

    while True:
        try:
            for tenant in tenants:
                await _process_tenant(
                    tenant,
                    fetch_recommendations,
                    apply_action,
                    confidence_threshold,
                )

            # Phase XXIII-D: Periodic learning model updates
            if learning_update_callback:
                try:
                    await _maybe_await(learning_update_callback())
                except Exception as exc:  # pragma: no cover
                    logger.warning("learning update failed: %s", exc)

        except Exception as exc:  # pragma: no cover
            logger.exception("adaptive_auto_responder loop error: %s", exc)

        await asyncio.sleep(interval_seconds)


async def _process_tenant(
    tenant: str | None,
    fetch_recommendations: Callable[..., Any],
    apply_action: Callable[[dict[str, Any]], Any],
    confidence_threshold: float,
) -> None:
    # 1) get recs
    recs = await _maybe_await(fetch_recommendations(tenant=tenant))
    if not recs or not recs.get("ok"):
        return

    auto_cands: list[dict[str, Any]] = recs.get("auto_ack_candidates") or []

    # safety: max 5 auto-actions per tenant per loop
    processed = 0
    for cand in auto_cands:
        if processed >= 5:
            break

        conf = float(cand.get("confidence") or 0.0)
        if conf < confidence_threshold:
            continue

        alert_id = cand.get("alert_id")
        if not alert_id:
            continue

        # 2) apply
        payload: dict[str, Any] = {
            "type": "auto_ack_candidate",
            "alert_id": alert_id,
        }
        if tenant:
            payload["tenant"] = tenant

        try:
            resp = await _maybe_await(apply_action(payload))
            # we don't need to do anything with resp; audit will capture it
            processed += 1
        except Exception as exc:  # pragma: no cover
            logger.warning("adaptive auto-apply failed for %s: %s", alert_id, exc)


async def _maybe_await(val: Any) -> Any:
    if asyncio.iscoroutine(val) or asyncio.isfuture(val):
        return await val
    return val
