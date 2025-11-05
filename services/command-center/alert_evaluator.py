"""
Alert Rule Evaluator

Phase VI M6: Evaluates alert rules against event store and emits ops.alert.raised events.
Phase VII M1: Integrated with notification_dispatcher for webhook delivery.
"""

import asyncio
from typing import Dict, Any
from datetime import datetime, timezone
import uuid

import alert_store
import event_store
import notification_dispatcher


async def evaluate_rules_once() -> Dict[str, Any]:
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
        since = datetime.now(timezone.utc)
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "client_ip": "127.0.0.1",
                },
            }
            
            # Save alert event
            event_store.save_event(alert_event)
            
            # Phase VII M1: Dispatch alert to webhooks (non-blocking)
            try:
                dispatch_result = await notification_dispatcher.dispatch_alert(alert_event)
                if dispatch_result.get("delivered", 0) > 0:
                    print(f"[alert_evaluator] 🔔 Alert '{rule['name']}' delivered to {dispatch_result['delivered']} webhook(s)")
            except Exception as e:
                # Non-fatal: alert is already saved, webhook delivery is best-effort
                print(f"[alert_evaluator] ⚠️  Webhook dispatch failed for '{rule['name']}': {e}")
            
            triggered.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "count": count,
                "threshold": rule["threshold"],
            })
    
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
