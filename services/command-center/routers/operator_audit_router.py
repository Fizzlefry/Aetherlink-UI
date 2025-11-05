"""
Phase VIII M10: Operator Audit API Router

Provides read-only access to operator audit trail.

Endpoints:
- GET /audit/operator - List operator actions with filters
- GET /audit/operator/stats - Aggregate statistics
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from operator_audit import get_audit_stats, get_operator_audit_log

router = APIRouter(prefix="/audit/operator", tags=["audit"])


@router.get("")
async def list_operator_audit(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    actor: str | None = Query(None, description="Filter by actor username"),
    action: str | None = Query(None, description="Filter by action type"),
    since: datetime | None = Query(None, description="Filter by timestamp (ISO 8601)"),
) -> dict[str, Any]:
    """
    Retrieve operator audit trail with optional filters.

    Returns list of audit records sorted newest-first.

    Query params:
    - limit: Max records (default 100, max 1000)
    - actor: Filter by username (e.g., "operator-john")
    - action: Filter by type (e.g., "delivery.replay")
    - since: Only records after this timestamp

    Example:
        GET /audit/operator?limit=50&action=delivery.replay&since=2025-11-04T10:00:00Z

    Response:
        {
            "records": [
                {
                    "id": "uuid",
                    "actor": "operator-john",
                    "action": "delivery.replay",
                    "target_id": "abc-123",
                    "metadata": {"new_delivery_id": "xyz-789"},
                    "source_ip": "192.168.1.100",
                    "created_at": "2025-11-04T15:30:00Z"
                },
                ...
            ],
            "count": 42,
            "filters": {
                "limit": 50,
                "actor": null,
                "action": "delivery.replay",
                "since": "2025-11-04T10:00:00Z"
            }
        }
    """
    records = get_operator_audit_log(
        limit=limit,
        actor=actor,
        action=action,
        since=since,
    )

    return {
        "records": records,
        "count": len(records),
        "filters": {
            "limit": limit,
            "actor": actor,
            "action": action,
            "since": since.isoformat() if since else None,
        },
    }


@router.get("/stats")
async def operator_audit_stats() -> dict[str, Any]:
    """
    Get aggregate statistics about operator audit trail.

    Returns:
    - total_actions: Total number of logged actions
    - by_action: Breakdown by action type
    - top_actors: Most active operators
    - oldest_record: Timestamp of first record
    - newest_record: Timestamp of most recent record

    Example:
        GET /audit/operator/stats

    Response:
        {
            "total_actions": 247,
            "by_action": {
                "delivery.replay": 203,
                "delivery.bulk_replay": 44
            },
            "top_actors": [
                {"actor": "operator-john", "count": 150},
                {"actor": "operator-jane", "count": 97}
            ],
            "oldest_record": "2025-11-04T10:00:00Z",
            "newest_record": "2025-11-04T22:30:00Z"
        }
    """
    return get_audit_stats()
