"""
Alert Rule Evaluator

Phase VI M6: Evaluates alert rules against event store and emits ops.alert.raised events.
Phase VII M1: Integrated with notification_dispatcher for webhook delivery.
Phase VII M5: Reliable alert delivery via queue-based dispatcher with retries.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import alert_store
import event_store
import httpx
import notification_dispatcher


async def evaluate_rules_once() -> dict[str, Any]:
    """
    Evaluate all enabled alert rules once.

    Phase VI M6: Checks each rule against the event store and emits
    ops.alert.raised events when thresholds are exceeded.

    Returns:
        Dictionary with evaluation summary
    """
    rules = alert_store.list_rules()
    triggered = []
    evaluated = 0

    for rule in rules:
        if not rule["enabled"]:
            continue

        evaluated += 1

        # Build time window
        window_seconds = rule["window_seconds"]
        since = datetime.now(UTC)
        since = since.replace(microsecond=0)
        # Subtract window_seconds
        from datetime import timedelta

        since = since - timedelta(seconds=window_seconds)
        since_iso = since.isoformat()

        # Phase VII M3: Pass rule's tenant_id to filter events by tenant
        rule_tenant_id = rule.get("tenant_id")

        # Count matching events in window
        count = event_store.count_events(
            event_type=rule["event_type"],
            source=rule["source"],
            severity=rule["severity"],
            since=since_iso,
            tenant_id=rule_tenant_id,
        )

        # Check if threshold exceeded
        if count >= rule["threshold"]:
            # Emit alert event (inherit tenant_id from rule)
            alert_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "ops.alert.raised",
                "source": "aether-command-center",
                "severity": "critical",
                "timestamp": datetime.now(UTC).isoformat(),
                "tenant_id": rule_tenant_id if rule_tenant_id else "system",
                "payload": {
                    "rule_name": rule["name"],
                    "rule_id": rule["id"],
                    "matched_count": count,
                    "window_seconds": window_seconds,
                    "threshold": rule["threshold"],
                    "filters": {
                        "event_type": rule["event_type"],
                        "source": rule["source"],
                        "severity": rule["severity"],
                    },
                },
                "_meta": {
                    "received_at": datetime.now(UTC).isoformat(),
                    "client_ip": "127.0.0.1",
                },
            }

            # Save alert event
            event_store.save_event(alert_event)

            # Phase VII M5: Enqueue alert for reliable delivery instead of immediate dispatch
            # Check dedup window first: only enqueue if not sent recently
            if event_store.check_dedup_window(rule["name"], rule_tenant_id or "system"):
                # Get configured webhooks
                webhook_urls = notification_dispatcher.get_configured_webhooks()

                if len(webhook_urls) > 0:
                    # Enqueue for each webhook URL
                    for webhook_url in webhook_urls:
                        event_store.enqueue_alert_delivery(
                            alert_event_id=alert_event["event_id"],
                            alert_payload=alert_event,
                            webhook_url=webhook_url,
                            max_attempts=5,
                        )

                    # Update dedup history (prevents re-enqueueing same alert within window)
                    event_store.update_dedup_history(rule["name"], rule_tenant_id or "system")

                    print(
                        f"[alert_evaluator] � Alert '{rule['name']}' enqueued for delivery to {len(webhook_urls)} webhook(s)"
                    )
                else:
                    print(f"[alert_evaluator] ⚠️  No webhooks configured for alert '{rule['name']}'")
            else:
                print(f"[alert_evaluator] 🔕 Alert '{rule['name']}' skipped (dedup window active)")

            triggered.append(
                {
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "count": count,
                    "threshold": rule["threshold"],
                }
            )

    return {
        "status": "ok",
        "evaluated": evaluated,
        "triggered": len(triggered),
        "alerts": triggered,
    }


async def alert_evaluator_loop():
    """
    Background task that evaluates alert rules periodically.

    Phase VI M6: Runs every 15 seconds to check for threshold violations.
    This runs as a FastAPI background task.
    """
    print("[alert_evaluator] 🚨 Starting alert evaluator loop")

    while True:
        try:
            result = await evaluate_rules_once()
            if result["triggered"] > 0:
                print(
                    f"[alert_evaluator] ⚠️  Triggered {result['triggered']} alert(s): {result['alerts']}"
                )
        except Exception as e:
            print(f"[alert_evaluator] ❌ Error evaluating rules: {e}")

        # Wait 15 seconds before next evaluation
        await asyncio.sleep(15)


async def delivery_dispatcher_loop():
    """
    Background task that processes queued alert deliveries.

    Phase VII M5: Pulls pending deliveries from the queue and attempts webhook POST.
    Implements retry logic with exponential backoff and dead letter handling.

    Architecture:
    - Every 30 seconds, fetch up to 50 pending deliveries
    - Attempt POST to webhook_url with 10-second timeout
    - On success: entry removed from queue
    - On failure: exponential backoff with capped retry (30s, 2m, 5m, cap at 30m)
    - After max_attempts (default 5): emit ops.alert.delivery.failed and remove from queue
    """
    print("[delivery_dispatcher] 📮 Starting delivery dispatcher loop")

    # Wait 10 seconds before first check (allow system startup)
    await asyncio.sleep(10)

    # Create persistent HTTP client with connection pooling
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        while True:
            try:
                # Fetch deliveries where next_attempt_at <= now
                deliveries = event_store.get_pending_deliveries(limit=50)

                if len(deliveries) > 0:
                    print(
                        f"[delivery_dispatcher] 📤 Processing {len(deliveries)} pending delivery(ies)"
                    )

                for delivery in deliveries:
                    delivery_id = delivery["id"]
                    webhook_url = delivery["webhook_url"]
                    alert_payload = delivery["alert_payload"]
                    attempt_count = delivery["attempt_count"]
                    max_attempts = delivery["max_attempts"]

                    try:
                        # Attempt webhook POST
                        response = await client.post(
                            webhook_url,
                            json=alert_payload,
                            headers={"Content-Type": "application/json"},
                        )

                        # Success: 2xx status code
                        if 200 <= response.status_code < 300:
                            event_store.update_delivery_attempt(
                                delivery_id, success=True, error_message=None
                            )
                            print(
                                f"[delivery_dispatcher] ✅ Delivered alert to {webhook_url} (status {response.status_code})"
                            )
                        else:
                            # HTTP error (4xx, 5xx)
                            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                            event_store.update_delivery_attempt(
                                delivery_id, success=False, error_message=error_msg
                            )

                            # Check if max attempts reached (after update)
                            new_attempt_count = attempt_count + 1
                            if new_attempt_count >= max_attempts:
                                # Emit dead letter event
                                dead_letter_event = {
                                    "event_id": str(uuid.uuid4()),
                                    "event_type": "ops.alert.delivery.failed",
                                    "source": "aether-command-center",
                                    "severity": "error",
                                    "timestamp": datetime.now(UTC).isoformat(),
                                    "tenant_id": alert_payload.get("tenant_id", "system"),
                                    "payload": {
                                        "alert_event_id": delivery["alert_event_id"],
                                        "webhook_url": webhook_url,
                                        "attempts": new_attempt_count,
                                        "last_error": error_msg,
                                        "alert_rule_name": alert_payload.get("payload", {}).get(
                                            "rule_name", "unknown"
                                        ),
                                    },
                                    "_meta": {
                                        "received_at": datetime.now(UTC).isoformat(),
                                        "client_ip": "127.0.0.1",
                                    },
                                }
                                event_store.save_event(dead_letter_event)
                                print(
                                    f"[delivery_dispatcher] ☠️  Dead letter: Alert delivery failed after {new_attempt_count} attempts to {webhook_url}"
                                )
                            else:
                                print(
                                    f"[delivery_dispatcher] 🔄 Retry scheduled for {webhook_url} (attempt {new_attempt_count}/{max_attempts})"
                                )

                    except httpx.TimeoutException:
                        # Timeout
                        error_msg = "Request timeout (>10s)"
                        event_store.update_delivery_attempt(
                            delivery_id, success=False, error_message=error_msg
                        )

                        new_attempt_count = attempt_count + 1
                        if new_attempt_count >= max_attempts:
                            # Emit dead letter event
                            dead_letter_event = {
                                "event_id": str(uuid.uuid4()),
                                "event_type": "ops.alert.delivery.failed",
                                "source": "aether-command-center",
                                "severity": "error",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "tenant_id": alert_payload.get("tenant_id", "system"),
                                "payload": {
                                    "alert_event_id": delivery["alert_event_id"],
                                    "webhook_url": webhook_url,
                                    "attempts": new_attempt_count,
                                    "last_error": error_msg,
                                    "alert_rule_name": alert_payload.get("payload", {}).get(
                                        "rule_name", "unknown"
                                    ),
                                },
                                "_meta": {
                                    "received_at": datetime.now(UTC).isoformat(),
                                    "client_ip": "127.0.0.1",
                                },
                            }
                            event_store.save_event(dead_letter_event)
                            print(
                                f"[delivery_dispatcher] ☠️  Dead letter: Alert delivery timed out after {new_attempt_count} attempts to {webhook_url}"
                            )
                        else:
                            print(
                                f"[delivery_dispatcher] ⏱️  Timeout for {webhook_url}, retry scheduled"
                            )

                    except Exception as e:
                        # Network error, connection refused, etc.
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        event_store.update_delivery_attempt(
                            delivery_id, success=False, error_message=error_msg
                        )

                        new_attempt_count = attempt_count + 1
                        if new_attempt_count >= max_attempts:
                            # Emit dead letter event
                            dead_letter_event = {
                                "event_id": str(uuid.uuid4()),
                                "event_type": "ops.alert.delivery.failed",
                                "source": "aether-command-center",
                                "severity": "error",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "tenant_id": alert_payload.get("tenant_id", "system"),
                                "payload": {
                                    "alert_event_id": delivery["alert_event_id"],
                                    "webhook_url": webhook_url,
                                    "attempts": new_attempt_count,
                                    "last_error": error_msg,
                                    "alert_rule_name": alert_payload.get("payload", {}).get(
                                        "rule_name", "unknown"
                                    ),
                                },
                                "_meta": {
                                    "received_at": datetime.now(UTC).isoformat(),
                                    "client_ip": "127.0.0.1",
                                },
                            }
                            event_store.save_event(dead_letter_event)
                            print(
                                f"[delivery_dispatcher] ☠️  Dead letter: Alert delivery failed after {new_attempt_count} attempts to {webhook_url} - {error_msg}"
                            )
                        else:
                            print(
                                f"[delivery_dispatcher] ⚠️  Error for {webhook_url}: {error_msg}, retry scheduled"
                            )

            except Exception as e:
                # Catch-all for dispatcher loop errors
                print(f"[delivery_dispatcher] ❌ Dispatcher loop error: {e}")

            # Wait 30 seconds before next batch
            await asyncio.sleep(30)
