from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Replace with your actual admin dependency and DAL import paths
def AdminRequired():
    # TODO: Replace with real admin check
    return True

def get_deliveries_between(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    # TODO: Replace with real DB query
    # Should return a list of deliveries with keys: tenant_id, endpoint, status, triage_label
    return []

router = APIRouter(prefix="/tenant-analytics", tags=["tenant-analytics"])

COST_PER_FAILED_DELIVERY = 0.03  # $0.03 per failed delivery

def _aggregate(deliveries: List[Dict[str, Any]]):
    tenants: Dict[str, Dict[str, Any]] = {}
    for d in deliveries:
        tenant_id = d.get("tenant_id") or "unknown"
        endpoint = d.get("endpoint") or "unknown"
        status = d.get("status")
        triage = d.get("triage_label") or "UNCLASSIFIED"

        if tenant_id not in tenants:
            tenants[tenant_id] = {
                "tenant_id": tenant_id,
                "total_deliveries": 0,
                "failed_deliveries": 0,
                "endpoints": {},
                "triage_counts": {},
            }

        t = tenants[tenant_id]
        t["total_deliveries"] += 1
        if status and status >= 400:
            t["failed_deliveries"] += 1

        # endpoint stats
        ep_stats = t["endpoints"].setdefault(endpoint, {
            "endpoint": endpoint,
            "total": 0,
            "failures": 0,
        })
        ep_stats["total"] += 1
        if status and status >= 400:
            ep_stats["failures"] += 1

        # triage stats
        t["triage_counts"][triage] = t["triage_counts"].get(triage, 0) + 1

    # derive rates and costs
    for t in tenants.values():
        total = t["total_deliveries"] or 1
        t["failure_rate"] = t["failed_deliveries"] / total
        t["estimated_failure_cost"] = round(t["failed_deliveries"] * COST_PER_FAILED_DELIVERY, 2)
        # flatten endpoints to list for UI
        for ep in t["endpoints"].values():
            ep["failure_rate"] = ep["failures"] / (ep["total"] or 1)
            ep["estimated_failure_cost"] = round(ep["failures"] * COST_PER_FAILED_DELIVERY, 2)
        t["endpoints"] = list(t["endpoints"].values())

    return list(tenants.values())


@router.get("/summary", dependencies=[Depends(AdminRequired)])
def tenant_summary(hours: int = Query(24, ge=1, le=168)):
    now = datetime.utcnow()
    start = now - timedelta(hours=hours)
    deliveries = get_deliveries_between(start, now)
    tenants = _aggregate(deliveries)
    tenants.sort(key=lambda x: x["failed_deliveries"], reverse=True)
    return {
        "range_hours": hours,
        "generated_at": now.isoformat() + "Z",
        "tenants": tenants,
    }
