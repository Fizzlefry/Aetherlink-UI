"""
Phase IX M3: Anomaly Detection API Router
Exposes real-time anomaly detection to operator dashboard.
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import List, Dict, Any

from anomaly_detector import (
    detect_anomalies,
    format_incident_message,
    WINDOW_MINUTES,
    BASELINE_MINUTES,
)
from rbac import admin_required

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


def _get_deliveries_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Fetch deliveries from the in-memory DELIVERY_HISTORY store.
    In production, this would query a proper database.
    """
    # Import delivery history from the delivery_history router
    from routers.delivery_history import DELIVERY_HISTORY

    # Filter deliveries by time range
    result = []
    for delivery in DELIVERY_HISTORY:
        created_at_str = delivery.get("created_at")
        if not created_at_str:
            continue

        # Parse ISO timestamp
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        # Check if in range
        if start <= created_at <= end:
            result.append(delivery)

    return result

@router.get("/current")
def get_current_anomalies(
    _admin=Depends(admin_required)
) -> Dict[str, Any]:
    """
    Detect current anomalies by comparing recent window to baseline.

    Returns:
        {
            "incidents": [...],
            "summary": {
                "total_incidents": int,
                "critical_incidents": int,
                "warning_incidents": int
            },
            "window_minutes": int,
            "baseline_minutes": int,
            "detected_at": str (ISO timestamp)
        }
    """
    from datetime import UTC

    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    baseline_start = now - timedelta(minutes=BASELINE_MINUTES)

    # Fetch deliveries from history
    recent_deliveries = _get_deliveries_between(window_start, now)
    baseline_deliveries = _get_deliveries_between(baseline_start, window_start)
    
    # Detect anomalies
    incidents = detect_anomalies(recent_deliveries, baseline_deliveries, now)
    
    # Add human-readable messages
    for incident in incidents:
        incident["message"] = format_incident_message(incident)
    
    # Calculate summary
    critical_count = sum(1 for i in incidents if i["severity"] == "critical")
    warning_count = len(incidents) - critical_count
    
    return {
        "incidents": incidents,
        "summary": {
            "total_incidents": len(incidents),
            "critical_incidents": critical_count,
            "warning_incidents": warning_count,
        },
        "window_minutes": WINDOW_MINUTES,
        "baseline_minutes": BASELINE_MINUTES,
        "detected_at": now.isoformat() + "Z",
    }

@router.get("/history")
def get_anomaly_history(
    hours: int = Query(24, ge=1, le=168),
    _admin=Depends(admin_required)
) -> Dict[str, Any]:
    """
    Get historical anomaly detection by running detector over past time ranges.
    Useful for trend analysis and validation.

    Args:
        hours: How many hours back to analyze (default: 24, max: 168/1 week)

    Returns:
        List of incident snapshots over time
    """
    from datetime import UTC

    now = datetime.now(UTC)
    snapshots = []

    # Run detector every hour for the requested period
    for hour_offset in range(hours):
        snapshot_time = now - timedelta(hours=hour_offset)
        window_start = snapshot_time - timedelta(minutes=WINDOW_MINUTES)
        baseline_start = snapshot_time - timedelta(minutes=BASELINE_MINUTES)

        recent = _get_deliveries_between(window_start, snapshot_time)
        baseline = _get_deliveries_between(baseline_start, window_start)
        
        incidents = detect_anomalies(recent, baseline, snapshot_time)
        
        if incidents:  # Only include snapshots with incidents
            snapshots.append({
                "timestamp": snapshot_time.isoformat() + "Z",
                "incident_count": len(incidents),
                "critical_count": sum(1 for i in incidents if i["severity"] == "critical"),
                "incidents": incidents[:5],  # Top 5 incidents per snapshot
            })
    
    return {
        "snapshots": snapshots,
        "hours_analyzed": hours,
        "generated_at": now.isoformat() + "Z",
    }
