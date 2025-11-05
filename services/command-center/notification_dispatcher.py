"""
Alert Notification Dispatcher

Phase VII M1: Delivers ops.alert.raised events to configured webhooks.
Supports Slack, Teams, Discord, and generic HTTP endpoints.
"""

import os
import json
import httpx
from typing import List, Dict, Any
from datetime import datetime


# Environment-based webhook configuration
DEFAULT_WEBHOOKS = os.getenv("ALERT_WEBHOOKS", "")


def get_configured_webhooks() -> List[str]:
    """
    Get list of webhook URLs from environment.
    
    Phase VII M1: Reads ALERT_WEBHOOKS env var (comma-separated URLs).
    
    Returns:
        List of webhook URLs (empty if not configured)
    """
    if not DEFAULT_WEBHOOKS:
        return []
    
    webhooks = [w.strip() for w in DEFAULT_WEBHOOKS.split(",") if w.strip()]
    return webhooks


def _to_slack_friendly(alert_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert alert event to Slack-friendly webhook payload.
    
    Phase VII M1: Uses Slack incoming webhook format.
    Also works with Discord/Teams (they accept similar JSON).
    
    Args:
        alert_event: The ops.alert.raised event dictionary
    
    Returns:
        Slack-formatted webhook payload
    """
    payload_data = alert_event.get("payload", {})
    rule_name = payload_data.get("rule_name", "unknown")
    severity = alert_event.get("severity", "unknown")
    source = alert_event.get("source", "command-center")
    matched_count = payload_data.get("matched_count", 0)
    threshold = payload_data.get("threshold", 0)
    window_seconds = payload_data.get("window_seconds", 0)
    
    # Filters that triggered the alert
    filters = payload_data.get("filters", {})
    event_type = filters.get("event_type", "any")
    filter_source = filters.get("source", "any")
    filter_severity = filters.get("severity", "any")
    
    # Build human-readable message
    text = f":rotating_light: *AetherLink Alert Triggered*\n\n"
    text += f"*Rule:* `{rule_name}`\n"
    text += f"*Severity:* `{severity.upper()}`\n"
    text += f"*Source:* `{source}`\n"
    text += f"*Threshold:* {matched_count}/{threshold} events in {window_seconds}s\n\n"
    text += f"*Filters:*\n"
    text += f"  • Event Type: `{event_type}`\n"
    text += f"  • Source: `{filter_source}`\n"
    text += f"  • Severity: `{filter_severity}`\n\n"
    text += f"*Timestamp:* {alert_event.get('timestamp', 'unknown')}\n"
    
    return {"text": text}


async def dispatch_alert(alert_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch alert event to all configured webhooks.
    
    Phase VII M1: Non-blocking delivery with graceful failure handling.
    
    Args:
        alert_event: The ops.alert.raised event to deliver
    
    Returns:
        Dispatch summary with success/failure counts
    """
    webhooks = get_configured_webhooks()
    
    if not webhooks:
        # No webhooks configured - silent no-op
        return {
            "status": "skipped",
            "reason": "no_webhooks_configured",
            "delivered": 0,
            "failed": 0,
        }
    
    delivered = 0
    failed = 0
    errors = []
    
    # Convert to Slack-friendly format
    payload = _to_slack_friendly(alert_event)
    
    # Deliver to all webhooks (non-blocking)
    async with httpx.AsyncClient(timeout=5.0) as client:
        for webhook_url in webhooks:
            try:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code >= 200 and response.status_code < 300:
                    delivered += 1
                    print(f"[notification_dispatcher] ✅ Delivered alert to {webhook_url[:50]}...")
                else:
                    failed += 1
                    errors.append(f"{webhook_url[:50]}: HTTP {response.status_code}")
                    print(f"[notification_dispatcher] ⚠️  Webhook failed: {webhook_url[:50]} (HTTP {response.status_code})")
            
            except httpx.TimeoutException:
                failed += 1
                errors.append(f"{webhook_url[:50]}: timeout")
                print(f"[notification_dispatcher] ⚠️  Webhook timeout: {webhook_url[:50]}")
            
            except Exception as e:
                failed += 1
                errors.append(f"{webhook_url[:50]}: {str(e)[:50]}")
                print(f"[notification_dispatcher] ⚠️  Webhook error: {webhook_url[:50]} - {e}")
    
    # Log summary
    if delivered > 0:
        print(f"[notification_dispatcher] 🔔 Alert delivered to {delivered}/{len(webhooks)} webhook(s)")
    
    return {
        "status": "completed",
        "delivered": delivered,
        "failed": failed,
        "total_webhooks": len(webhooks),
        "errors": errors if errors else None,
    }


def format_alert_for_testing(alert_event: Dict[str, Any]) -> str:
    """
    Format alert event as human-readable string for testing.
    
    Phase VII M1: Used in test/demo scenarios.
    
    Args:
        alert_event: The ops.alert.raised event
    
    Returns:
        Formatted string representation
    """
    payload = alert_event.get("payload", {})
    return (
        f"Alert: {payload.get('rule_name', 'unknown')} | "
        f"Severity: {alert_event.get('severity', 'unknown')} | "
        f"Count: {payload.get('matched_count', 0)}/{payload.get('threshold', 0)}"
    )
