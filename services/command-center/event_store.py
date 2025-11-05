# services/command-center/event_store.py
"""
Event storage layer for Command Center.
Phase VI M2: Persistent event storage using SQLite.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("EVENT_DB_PATH", "/data/events.db")


def get_conn():
    """Get SQLite connection with dict row factory."""
    # Ensure folder exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize events database schema."""
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            tenant_id TEXT,
            severity TEXT,
            timestamp TEXT NOT NULL,
            payload TEXT,
            received_at TEXT NOT NULL,
            client_ip TEXT
        )
        """
    )
    # Indexes for common queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_source_ts ON events(source, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_ts ON events(tenant_id, timestamp)")
    conn.commit()
    conn.close()
    print("[event_store] ✅ Database initialized")


def json_dumps_safe(obj: Any) -> str:
    """Safely serialize object to JSON string."""
    try:
        return json.dumps(obj)
    except Exception:
        return "{}"


def json_loads_safe(s: str) -> Any:
    """Safely deserialize JSON string to object."""
    try:
        return json.loads(s or "{}")
    except Exception:
        return {}


def save_event(event: dict[str, Any]):
    """Save event to persistent storage."""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO events (
            event_id, event_type, source, tenant_id, severity,
            timestamp, payload, received_at, client_ip
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.get("event_id"),
            event["event_type"],
            event["source"],
            event.get("tenant_id", "default"),
            event.get("severity", "info"),
            event["timestamp"],
            json_dumps_safe(event.get("payload")),
            event["_meta"]["received_at"],
            event["_meta"].get("client_ip"),
        ),
    )
    conn.commit()
    conn.close()


def list_recent(
    limit: int = 50,
    event_type: str | None = None,
    source: str | None = None,
    tenant_id: str | None = None,
    severity: str | None = None,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve recent events from storage.

    Args:
        limit: Maximum number of events to return
        event_type: Filter by event type (optional)
        source: Filter by source service (optional)
        tenant_id: Filter by tenant ID (optional)
        severity: Filter by severity level (optional)
        since: Filter by timestamp - ISO string or epoch (optional)

    Returns:
        List of events (newest first)
    """
    conn = get_conn()

    # Build query with optional filters
    query = """
        SELECT id, event_id, event_type, source, tenant_id, severity,
               timestamp, payload, received_at, client_ip
        FROM events
        WHERE 1=1
    """
    params = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if source:
        query += " AND source = ?"
        params.append(source)

    if tenant_id:
        query += " AND tenant_id = ?"
        params.append(tenant_id)

    # Phase VI M5: Severity filtering
    if severity:
        query += " AND severity = ?"
        params.append(severity.lower())

    # Phase VI M5: Time-range filtering
    if since:
        query += " AND timestamp >= ?"
        params.append(since)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "event_id": r["event_id"],
                "event_type": r["event_type"],
                "source": r["source"],
                "tenant_id": r["tenant_id"],
                "severity": r["severity"],
                "timestamp": r["timestamp"],
                "payload": json_loads_safe(r["payload"]),
                "received_at": r["received_at"],
                "_meta": {
                    "received_at": r["received_at"],
                    "client_ip": r["client_ip"],
                },
            }
        )

    return out


def count_events(
    event_type: str | None = None,
    source: str | None = None,
    tenant_id: str | None = None,
    severity: str | None = None,
    since: str | None = None,
) -> int:
    """
    Count total events with optional filters.
    
    Phase VI M6: Added severity and since for alert evaluation.
    """
    conn = get_conn()

    query = "SELECT COUNT(*) as cnt FROM events WHERE 1=1"
    params = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if source:
        query += " AND source = ?"
        params.append(source)

    if tenant_id:
        query += " AND tenant_id = ?"
        params.append(tenant_id)

    if severity:
        query += " AND severity = ?"
        params.append(severity.lower())

    if since:
        query += " AND timestamp >= ?"
        params.append(since)

    cur = conn.execute(query, params)
    result = cur.fetchone()
    conn.close()

    return result["cnt"] if result else 0


def get_event_stats() -> dict[str, Any]:
    """
    Get event statistics for operational overview.

    Phase VI M5: Returns total events, last 24h count, and breakdown by severity.

    Returns:
        Dictionary with stats including total, last_24h, and by_severity
    """
    conn = get_conn()

    # Total events
    total_result = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
    total = total_result["cnt"] if total_result else 0

    # Events by severity
    severity_cur = conn.execute("""
        SELECT severity, COUNT(*) as cnt
        FROM events
        GROUP BY severity
    """)
    by_severity = {row["severity"]: row["cnt"] for row in severity_cur.fetchall()}

    # Last 24 hours
    last_24h_result = conn.execute("""
        SELECT COUNT(*) as cnt
        FROM events
        WHERE timestamp >= datetime('now', '-1 day')
    """).fetchone()
    last_24h = last_24h_result["cnt"] if last_24h_result else 0

    conn.close()

    return {
        "total": total,
        "last_24h": last_24h,
        "by_severity": by_severity,
    }
