"""
Alert Delivery History Router

Phase VIII M3: Recent delivery history for observability.
Shows what happened to each alert delivery over time.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import event_store
from fastapi import APIRouter, Depends, HTTPException, Query
from rbac import require_roles

router = APIRouter(prefix="/alerts/deliveries", tags=["alerts:deliveries:history"])

# Phase VIII M3: In-memory delivery history
# In production, this would query alert_delivery_queue + a completed_deliveries table
DELIVERY_HISTORY: list[dict[str, Any]] = []


def seed_delivery_history():
    """
    Seed delivery history with sample data.

    Phase VIII M3: Provides realistic delivery examples for operators to see
    what successful, failed, and pending deliveries look like.
    """
    if DELIVERY_HISTORY:
        # Already seeded
        return

    print("[delivery_history] 🌱 Seeding delivery history...")

    now = datetime.now(UTC)

    sample_deliveries = [
        {
            "id": str(uuid.uuid4()),
            "alert_event_id": "evt-" + str(uuid.uuid4())[:8],
            "tenant_id": "tenant-qa",
            "rule_id": 1,
            "rule_name": "[tpl] Alert Delivery Failures",
            "event_type": "ops.alert.delivery.failed",
            "target": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX",
            "status": "failed",
            "attempts": 3,
            "max_attempts": 5,
            "last_error": "HTTP 503: Service Unavailable from Slack",
            "next_retry_at": (now + timedelta(minutes=5)).isoformat(),
            "created_at": (now - timedelta(minutes=2)).isoformat(),
            "updated_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "alert_event_id": "evt-" + str(uuid.uuid4())[:8],
            "tenant_id": "tenant-premium",
            "rule_id": 2,
            "rule_name": "[tpl] Critical Events",
            "event_type": "ops.error.critical",
            "target": "#aether-ops",
            "status": "delivered",
            "attempts": 1,
            "max_attempts": 5,
            "last_error": None,
            "next_retry_at": None,
            "created_at": (now - timedelta(minutes=10)).isoformat(),
            "updated_at": (now - timedelta(minutes=10)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "alert_event_id": "evt-" + str(uuid.uuid4())[:8],
            "tenant_id": "tenant-qa",
            "rule_id": 3,
            "rule_name": "[tpl] High Error Rate",
            "event_type": "ops.error",
            "target": "https://hooks.slack.com/services/T11111111/B11111111/YYYYYYYYYYYYYYYYYYYY",
            "status": "pending",
            "attempts": 0,
            "max_attempts": 5,
            "last_error": None,
            "next_retry_at": (now + timedelta(seconds=30)).isoformat(),
            "created_at": (now - timedelta(seconds=15)).isoformat(),
            "updated_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "alert_event_id": "evt-" + str(uuid.uuid4())[:8],
            "tenant_id": "tenant-acme",
            "rule_id": 4,
            "rule_name": "[tpl] AutoHeal Failures",
            "event_type": "autoheal.failed",
            "target": "#aether-autoheal",
            "status": "delivered",
            "attempts": 1,
            "max_attempts": 5,
            "last_error": None,
            "next_retry_at": None,
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "updated_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "alert_event_id": "evt-" + str(uuid.uuid4())[:8],
            "tenant_id": "tenant-qa",
            "rule_id": 1,
            "rule_name": "[tpl] Alert Delivery Failures",
            "event_type": "ops.alert.delivery.failed",
            "target": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX",
            "status": "failed",
            "attempts": 5,
            "max_attempts": 5,
            "last_error": "Max attempts reached - dead lettered",
            "next_retry_at": None,
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "updated_at": (now - timedelta(minutes=30)).isoformat(),
        },
    ]

    DELIVERY_HISTORY.extend(sample_deliveries)
    print(f"[delivery_history] ✅ Seeded {len(sample_deliveries)} sample deliveries")


@router.get("/history", dependencies=[Depends(require_roles(["operator", "admin"]))])
def list_delivery_history(tenant_id: str | None = None, limit: int = Query(50, ge=1, le=200)):
    """
    List recent alert delivery history.

    Phase VIII M3: Returns recent deliveries with status, attempts, and errors.
    Operators can see what happened to each alert delivery over time.

    Query params:
    - tenant_id: Optional tenant filter
    - limit: Max entries to return (default 50, max 200)

    Requires: operator or admin role

    Example response:
    [
      {
        "id": "abc-123",
        "alert_event_id": "evt-456",
        "tenant_id": "tenant-qa",
        "rule_id": 1,
        "rule_name": "[tpl] Alert Delivery Failures",
        "event_type": "ops.alert.delivery.failed",
        "target": "https://hooks.slack.com/services/...",
        "status": "delivered",
        "attempts": 1,
        "max_attempts": 5,
        "last_error": null,
        "next_retry_at": null,
        "created_at": "2025-11-04T10:00:00Z",
        "updated_at": "2025-11-04T10:00:05Z"
      }
    ]

    Status values:
    - "delivered" - Successfully delivered to webhook
    - "pending" - Queued, waiting for next attempt
    - "failed" - Failed but retrying
    - "dead_letter" - Failed after max attempts
    """
    # Get live queue entries from Phase VII M5
    try:
        queue_entries = event_store.get_delivery_queue(limit=100)

        # Transform queue entries to history format
        live_deliveries = []
        for entry in queue_entries:
            # Determine status based on attempts
            if entry["attempt_count"] >= entry["max_attempts"]:
                status = "dead_letter"
            elif entry["attempt_count"] > 0:
                status = "failed"
            else:
                status = "pending"

            live_deliveries.append(
                {
                    "id": str(entry["id"]),
                    "alert_event_id": entry["alert_event_id"],
                    "tenant_id": None,  # Not tracked in queue yet
                    "rule_id": None,  # Could parse from alert_event_id if needed
                    "rule_name": None,
                    "event_type": None,
                    "target": entry["webhook_url"],
                    "status": status,
                    "attempts": entry["attempt_count"],
                    "max_attempts": entry["max_attempts"],
                    "last_error": entry.get("last_error"),
                    "next_retry_at": entry.get("next_attempt_at"),
                    "created_at": entry["created_at"],
                    "updated_at": entry["updated_at"],
                }
            )

        # Combine with sample history (in production, query completed_deliveries table)
        all_deliveries = live_deliveries + DELIVERY_HISTORY

        # Sort by created_at (newest first)
        all_deliveries.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Filter by tenant if specified
        if tenant_id:
            all_deliveries = [d for d in all_deliveries if d.get("tenant_id") == tenant_id]

        # Apply limit
        result = all_deliveries[:limit]

        return {"status": "ok", "count": len(result), "deliveries": result}

    except Exception as e:
        print(f"[delivery_history] ❌ Error fetching history: {e}")
        # Fallback to sample data only
        items = list(DELIVERY_HISTORY)
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        if tenant_id:
            items = [i for i in items if i.get("tenant_id") == tenant_id]

        return {"status": "ok", "count": len(items[:limit]), "deliveries": items[:limit]}


@router.get("/{delivery_id}", dependencies=[Depends(require_roles(["operator", "admin"]))])
def get_delivery_detail(delivery_id: str):
    """
    Get detailed information about a specific delivery.

    Phase VIII M3: Returns full delivery details including payload,
    attempt history, and error messages.

    Requires: operator or admin role

    Example response:
    {
      "id": "abc-123",
      "alert_event_id": "evt-456",
      "tenant_id": "tenant-qa",
      "rule_name": "[tpl] Alert Delivery Failures",
      "event_type": "ops.alert.delivery.failed",
      "target": "https://hooks.slack.com/services/...",
      "status": "delivered",
      "attempts": 1,
      "attempt_history": [
        {
          "attempt": 1,
          "timestamp": "2025-11-04T10:00:05Z",
          "status": "success",
          "http_code": 200,
          "error": null
        }
      ],
      "payload": {
        "event_id": "evt-456",
        "event_type": "ops.alert.delivery.failed",
        "severity": "error",
        ...
      },
      "created_at": "2025-11-04T10:00:00Z"
    }
    """
    # Check sample history
    for item in DELIVERY_HISTORY:
        if item["id"] == delivery_id:
            return {"status": "ok", "delivery": item}

    # Check live queue
    try:
        queue_entries = event_store.get_delivery_queue(limit=100)
        for entry in queue_entries:
            if str(entry["id"]) == delivery_id:
                return {"status": "ok", "delivery": entry}
    except Exception as e:
        print(f"[delivery_history] ❌ Error fetching delivery detail: {e}")

    raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")


@router.post("/{delivery_id}/replay", dependencies=[Depends(require_roles(["operator", "admin"]))])
def replay_delivery(delivery_id: str):
    """
    Phase VIII M7: Replay a failed or dead-lettered delivery.

    Re-enqueues the delivery into the Phase VII delivery pipeline for another attempt.
    Useful for:
    - Retrying dead-lettered deliveries after fixing the root cause
    - Testing webhook configurations
    - Manual intervention for high-priority alerts

    Returns:
        JSON with new delivery ID and status

    Example:
        POST /alerts/deliveries/abc-123/replay
        Response: {"status": "replayed", "new_id": "xyz-789", "original_id": "abc-123"}
    """
    # First, try to find the delivery
    delivery = None

    # Check sample history
    for item in DELIVERY_HISTORY:
        if item["id"] == delivery_id:
            delivery = item
            break

    # Check live queue if not in history
    if not delivery:
        try:
            queue_entries = event_store.get_delivery_queue(limit=100)
            for entry in queue_entries:
                if str(entry["id"]) == delivery_id:
                    delivery = entry
                    break
        except Exception as e:
            print(f"[delivery_history] ❌ Error fetching delivery for replay: {e}")

    if not delivery:
        raise HTTPException(status_code=404, detail=f"Delivery {delivery_id} not found")

    # Re-enqueue the delivery
    try:
        # Generate new delivery ID
        new_delivery_id = str(uuid.uuid4())

        # Create new delivery entry based on original
        new_delivery = {
            "id": new_delivery_id,
            "original_id": delivery_id,
            "alert_event_id": delivery.get("alert_event_id"),
            "tenant_id": delivery.get("tenant_id"),
            "rule_id": delivery.get("rule_id"),
            "rule_name": delivery.get("rule_name"),
            "event_type": delivery.get("event_type"),
            "webhook_url": delivery.get("target") or delivery.get("webhook_url"),
            "attempt_count": 0,  # Reset attempts
            "max_attempts": 5,
            "last_error": None,
            "next_attempt_at": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # Build alert payload for re-enqueueing
        alert_payload = {
            "alert_id": new_delivery["alert_event_id"],
            "rule_id": new_delivery["rule_id"],
            "rule_name": new_delivery["rule_name"],
            "event_type": new_delivery["event_type"],
            "tenant_id": new_delivery["tenant_id"],
            "timestamp": datetime.now(UTC).isoformat(),
            "replayed_from": delivery_id,
        }

        # Validate required fields
        if not new_delivery.get("alert_event_id") or not new_delivery.get("webhook_url"):
            raise HTTPException(
                status_code=400, detail="Delivery missing required fields (alert_event_id or webhook_url)"
            )

        # Re-enqueue into Phase VII delivery queue
        event_store.enqueue_alert_delivery(
            alert_event_id=str(new_delivery["alert_event_id"]),
            alert_payload=alert_payload,
            webhook_url=str(new_delivery["webhook_url"]),
            max_attempts=5,
        )

        print(
            f"[delivery_history] 🔄 Replayed delivery {delivery_id} as {new_delivery_id} "
            f"for tenant {new_delivery['tenant_id']}"
        )

        return {
            "status": "replayed",
            "message": "Delivery re-enqueued successfully",
            "new_id": new_delivery_id,
            "original_id": delivery_id,
            "tenant_id": new_delivery["tenant_id"],
            "target": new_delivery["webhook_url"],
        }

    except Exception as e:
        print(f"[delivery_history] ❌ Error replaying delivery {delivery_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to replay delivery: {str(e)}")
