"""
Phase IX M4: Operator Insights Dashboard API
Aggregates operational metrics for decision intelligence.
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter

from rbac import admin_required

router = APIRouter(prefix="/operator-insights", tags=["operator-insights"])

async def _get_deliveries_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """Fetch deliveries from history (reuse pattern from anomalies router)."""
    from session import get_session
    from sqlalchemy import text
    
    async with get_session() as session:
        query = text("""
            SELECT 
                id, tenant_id, target, status, 
                triage_label, triage_score, attempts, max_attempts,
                created_at, last_error
            FROM deliveries
            WHERE created_at BETWEEN :start AND :end
            ORDER BY created_at DESC
        """)
        result = await session.execute(query, {"start": start, "end": end})
        rows = result.fetchall()
        
        return [
            {
                "id": row.id,
                "tenant_id": row.tenant_id,
                "target": row.target,
                "status": row.status,
                "triage_label": row.triage_label,
                "triage_score": row.triage_score,
                "attempts": row.attempts,
                "max_attempts": row.max_attempts,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_error": row.last_error,
            }
            for row in rows
        ]

@router.get("/summary")
async def get_insights_summary(
    hours: int = Query(24, ge=1, le=168),
    _admin=Depends(admin_required)
) -> Dict[str, Any]:
    """
    Get aggregated operator insights for decision-making.
    
    Args:
        hours: Time range to analyze (default: 24, max: 168/1 week)
    
    Returns:
        {
            "top_failing_endpoints": [...],
            "top_failing_tenants": [...],
            "triage_distribution": {...},
            "delivery_stats": {...},
            "replay_stats": {...},
            "time_range": {...}
        }
    """
    now = datetime.utcnow()
    start = now - timedelta(hours=hours)
    
    # Fetch all deliveries in range
    deliveries = await _get_deliveries_between(start, now)
    
    # === 1. Top Failing Endpoints ===
    endpoint_failures = Counter()
    endpoint_totals = Counter()
    
    for d in deliveries:
        endpoint = d.get("target") or "unknown"
        endpoint_totals[endpoint] += 1
        
        if d.get("status") in ("failed", "dead_letter"):
            endpoint_failures[endpoint] += 1
    
    top_failing_endpoints = [
        {
            "endpoint": endpoint,
            "failures": count,
            "total": endpoint_totals[endpoint],
            "failure_rate": round(count / endpoint_totals[endpoint] * 100, 1)
        }
        for endpoint, count in endpoint_failures.most_common(10)
    ]
    
    # === 2. Top Failing Tenants ===
    tenant_failures = Counter()
    tenant_totals = Counter()
    
    for d in deliveries:
        tenant = d.get("tenant_id") or "unknown"
        tenant_totals[tenant] += 1
        
        if d.get("status") in ("failed", "dead_letter"):
            tenant_failures[tenant] += 1
    
    top_failing_tenants = [
        {
            "tenant_id": tenant,
            "failures": count,
            "total": tenant_totals[tenant],
            "failure_rate": round(count / tenant_totals[tenant] * 100, 1)
        }
        for tenant, count in tenant_failures.most_common(10)
    ]
    
    # === 3. Triage Distribution (Phase IX M1 metrics) ===
    triage_counts = Counter(d.get("triage_label", "unclassified") for d in deliveries)
    
    triage_distribution = {
        "transient_endpoint_down": triage_counts.get("transient_endpoint_down", 0),
        "permanent_4xx": triage_counts.get("permanent_4xx", 0),
        "rate_limited": triage_counts.get("rate_limited", 0),
        "unknown": triage_counts.get("unknown", 0),
        "unclassified": triage_counts.get("unclassified", 0),
    }
    
    # === 4. Delivery Stats ===
    total_deliveries = len(deliveries)
    status_counts = Counter(d.get("status", "unknown") for d in deliveries)
    
    delivery_stats = {
        "total": total_deliveries,
        "delivered": status_counts.get("delivered", 0),
        "failed": status_counts.get("failed", 0),
        "pending": status_counts.get("pending", 0),
        "dead_letter": status_counts.get("dead_letter", 0),
        "success_rate": round(
            status_counts.get("delivered", 0) / total_deliveries * 100, 1
        ) if total_deliveries > 0 else 0.0,
    }
    
    # === 5. Replay Stats (from Phase VIII M10 audit or delivery attempts) ===
    replayed_deliveries = [d for d in deliveries if d.get("attempts", 0) > 1]
    successful_replays = [
        d for d in replayed_deliveries
        if d.get("status") == "delivered"
    ]
    
    replay_stats = {
        "total_replayed": len(replayed_deliveries),
        "replay_successes": len(successful_replays),
        "replay_success_rate": round(
            len(successful_replays) / len(replayed_deliveries) * 100, 1
        ) if replayed_deliveries else 0.0,
    }
    
    # === 6. Triage Accuracy (M1 validation) ===
    # Calculate how often triage predictions matched actual outcomes
    transient_deliveries = [d for d in deliveries if d.get("triage_label") == "transient_endpoint_down"]
    transient_successes = [d for d in transient_deliveries if d.get("attempts", 0) > 1 and d.get("status") == "delivered"]
    
    triage_accuracy = {
        "transient_retry_success_rate": round(
            len(transient_successes) / len(transient_deliveries) * 100, 1
        ) if transient_deliveries else 0.0,
        "note": "Measures how often 'transient' failures succeed on retry"
    }
    
    return {
        "top_failing_endpoints": top_failing_endpoints,
        "top_failing_tenants": top_failing_tenants,
        "triage_distribution": triage_distribution,
        "delivery_stats": delivery_stats,
        "replay_stats": replay_stats,
        "triage_accuracy": triage_accuracy,
        "time_range": {
            "hours": hours,
            "start": start.isoformat() + "Z",
            "end": now.isoformat() + "Z",
        },
        "generated_at": now.isoformat() + "Z",
    }

@router.get("/trends")
async def get_insights_trends(
    hours: int = Query(24, ge=1, le=168),
    interval_hours: int = Query(1, ge=1, le=24),
    _admin=Depends(admin_required)
) -> Dict[str, Any]:
    """
    Get time-series trends for delivery and triage metrics.
    
    Args:
        hours: Total time range to analyze
        interval_hours: Bucket size for time series (default: 1 hour)
    
    Returns:
        Time-series data for charting in UI
    """
    now = datetime.utcnow()
    start = now - timedelta(hours=hours)
    
    deliveries = await _get_deliveries_between(start, now)
    
    # Create time buckets
    num_intervals = hours // interval_hours
    intervals = []
    
    for i in range(num_intervals):
        interval_end = now - timedelta(hours=i * interval_hours)
        interval_start = interval_end - timedelta(hours=interval_hours)
        
        # Filter deliveries in this interval
        interval_deliveries = [
            d for d in deliveries
            if d.get("created_at") and
               interval_start.isoformat() <= d["created_at"] < interval_end.isoformat()
        ]
        
        # Calculate metrics for this interval
        total = len(interval_deliveries)
        failures = sum(1 for d in interval_deliveries if d.get("status") in ("failed", "dead_letter"))
        
        intervals.append({
            "timestamp": interval_start.isoformat() + "Z",
            "total_deliveries": total,
            "failures": failures,
            "success_rate": round((total - failures) / total * 100, 1) if total > 0 else 0.0,
        })
    
    # Reverse to get chronological order
    intervals.reverse()
    
    return {
        "intervals": intervals,
        "interval_hours": interval_hours,
        "total_hours": hours,
        "generated_at": now.isoformat() + "Z",
    }
