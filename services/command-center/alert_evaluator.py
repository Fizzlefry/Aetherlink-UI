"""
Alert Rule Evaluator

Phase VI M6: Evaluates alert rules against event store and emits ops.alert.raised events.
"""

import asyncio
from typing import Dict, Any
from datetime import datetime, timezone
import uuid

import alert_store
import event_store


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
        
        # Count matching events in window
        count = event_store.count_events(
            event_type=rule["event_type"],
            source=rule["source"],
            severity=rule["severity"],
            since=since_iso,
        )
        
        # Check if threshold exceeded
        if count >= rule["threshold"]:
            # Emit alert event
            alert_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "ops.alert.raised",
                "source": "aether-command-center",
                "severity": "critical",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tenant_id": "system",
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
