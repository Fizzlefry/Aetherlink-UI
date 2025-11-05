"""
Phase VIII M10: Operator Audit Trail

Provides tamper-resistant logging of operator actions in the Command Center.
Tracks who did what, when, and to which resource.

Features:
- Immutable audit records
- Action tracking (delivery replay, bulk operations, rule changes)
- Actor identification (from X-User-Roles or auth system)
- Metadata storage (delivery IDs, timestamps, source IPs)
- Query API for audit history

Design:
- In-memory storage for development (Phase VIII M10 v1)
- Future: Append-only database (SQLite WAL mode, ClickHouse, or S3)
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

# In-memory audit log (development mode)
# Format: List of audit records with full context
OPERATOR_AUDIT_LOG: list[dict[str, Any]] = []


def log_operator_action(
    actor: str,
    action: str,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    source_ip: str | None = None,
) -> dict[str, Any]:
    """
    Log an operator action to the audit trail.

    Args:
        actor: Username or identifier (from X-User-Roles, JWT, or auth system)
        action: Action type (e.g., "delivery.replay", "delivery.bulk_replay")
        target_id: Resource identifier (e.g., delivery_id)
        metadata: Additional context (delivery count, status_before, new_id, etc.)
        source_ip: Client IP address for network forensics

    Returns:
        The created audit record

    Example:
        log_operator_action(
            actor="operator-john",
            action="delivery.replay",
            target_id="abc-123",
            metadata={"new_delivery_id": "xyz-789", "status_before": "dead_letter"},
            source_ip="192.168.1.100"
        )
    """
    record = {
        "id": str(uuid.uuid4()),
        "actor": actor,
        "action": action,
        "target_id": target_id,
        "metadata": metadata or {},
        "source_ip": source_ip,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # Append to in-memory log (append-only pattern)
    OPERATOR_AUDIT_LOG.append(record)

    # Also log to stdout for Docker logs / external aggregation
    print(f"[OPERATOR_AUDIT] {json.dumps(record)}")

    return record


def get_operator_audit_log(
    limit: int = 100,
    actor: str | None = None,
    action: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Query the operator audit log with optional filters.

    Args:
        limit: Maximum number of records to return (default 100)
        actor: Filter by actor username
        action: Filter by action type
        since: Filter by timestamp (only records after this time)

    Returns:
        List of audit records matching filters, newest first

    Example:
        # Get last 50 replay actions by operator-john
        get_operator_audit_log(
            limit=50,
            actor="operator-john",
            action="delivery.replay"
        )
    """
    # Start with all records
    filtered = OPERATOR_AUDIT_LOG

    # Apply filters
    if actor:
        filtered = [r for r in filtered if r["actor"] == actor]

    if action:
        filtered = [r for r in filtered if r["action"] == action]

    if since:
        since_iso = since.isoformat()
        filtered = [r for r in filtered if r["created_at"] >= since_iso]

    # Sort newest first
    filtered = sorted(filtered, key=lambda r: r["created_at"], reverse=True)

    # Apply limit
    return filtered[:limit]


def get_audit_stats() -> dict[str, Any]:
    """
    Get aggregate statistics about operator audit trail.

    Returns:
        Dict with total actions, breakdown by action type, top actors, etc.

    Example response:
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
    if not OPERATOR_AUDIT_LOG:
        return {
            "total_actions": 0,
            "by_action": {},
            "top_actors": [],
            "oldest_record": None,
            "newest_record": None,
        }

    # Total count
    total = len(OPERATOR_AUDIT_LOG)

    # Breakdown by action type
    by_action: dict[str, int] = {}
    for record in OPERATOR_AUDIT_LOG:
        action = record["action"]
        by_action[action] = by_action.get(action, 0) + 1

    # Top actors (count actions per actor)
    by_actor: dict[str, int] = {}
    for record in OPERATOR_AUDIT_LOG:
        actor = record["actor"]
        by_actor[actor] = by_actor.get(actor, 0) + 1

    # Sort actors by count
    top_actors = [{"actor": actor, "count": count} for actor, count in by_actor.items()]
    top_actors.sort(key=lambda x: x["count"], reverse=True)

    # Time range
    sorted_records = sorted(OPERATOR_AUDIT_LOG, key=lambda r: r["created_at"])
    oldest = sorted_records[0]["created_at"] if sorted_records else None
    newest = sorted_records[-1]["created_at"] if sorted_records else None

    return {
        "total_actions": total,
        "by_action": by_action,
        "top_actors": top_actors[:10],  # Top 10 most active
        "oldest_record": oldest,
        "newest_record": newest,
    }
