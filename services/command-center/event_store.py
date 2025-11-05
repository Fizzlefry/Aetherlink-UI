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

    # Phase VII M3: Tenant filtering - include NULL tenant_id (system events)
    if tenant_id:
        query += " AND (tenant_id = ? OR tenant_id IS NULL)"
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

    # Phase VII M3: Tenant filtering - include NULL tenant_id (system events)
    if tenant_id:
        query += " AND (tenant_id = ? OR tenant_id IS NULL)"
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


def get_event_stats(tenant_id: str | None = None) -> dict[str, Any]:
    """
    Get event statistics for operational overview.

    Phase VI M5: Returns total events, last 24h count, and breakdown by severity.
    Phase VII M3: Added tenant_id filtering for multi-tenant stats.

    Args:
        tenant_id: Filter stats by tenant ID (optional)

    Returns:
        Dictionary with stats including total, last_24h, and by_severity
    """
    conn = get_conn()

    # Build WHERE clause for tenant filtering (includes NULL tenant_id for system events)
    tenant_filter = ""
    params = []
    if tenant_id:
        tenant_filter = " WHERE (tenant_id = ? OR tenant_id IS NULL)"
        params = [tenant_id]

    # Total events
    total_query = f"SELECT COUNT(*) as cnt FROM events{tenant_filter}"
    total_result = conn.execute(total_query, params).fetchone()
    total = total_result["cnt"] if total_result else 0

    # Events by severity
    severity_query = f"""
        SELECT severity, COUNT(*) as cnt
        FROM events
        {tenant_filter}
        GROUP BY severity
    """
    severity_cur = conn.execute(severity_query, params)
    by_severity = {row["severity"]: row["cnt"] for row in severity_cur.fetchall()}

    # Last 24 hours
    last_24h_where = " AND timestamp >= datetime('now', '-1 day')" if tenant_id else " WHERE timestamp >= datetime('now', '-1 day')"
    last_24h_query = f"""
        SELECT COUNT(*) as cnt
        FROM events
        {tenant_filter}{last_24h_where if not tenant_id else " AND timestamp >= datetime('now', '-1 day')"}
    """
    last_24h_params = params if tenant_id else []
    last_24h_result = conn.execute(last_24h_query, last_24h_params).fetchone()
    last_24h = last_24h_result["cnt"] if last_24h_result else 0

    conn.close()

    return {
        "total": total,
        "last_24h": last_24h,
        "by_severity": by_severity,
    }


# ============================================================================
# Phase VII M2: Event Retention & Archival
# ============================================================================

from datetime import datetime, timedelta, timezone

RETENTION_DAYS = int(os.getenv("EVENT_RETENTION_DAYS", "30"))
ARCHIVE_ENABLED = os.getenv("EVENT_ARCHIVE_ENABLED", "false").lower() == "true"
ARCHIVE_DIR = os.getenv("EVENT_ARCHIVE_DIR", "/app/data/archive")


def prune_old_events() -> dict[str, Any]:
    """
    Prune events older than retention window.
    
    Phase VII M2: Deletes events older than EVENT_RETENTION_DAYS.
    Optionally archives them to NDJSON before deletion.
    
    Returns:
        Pruning summary with cutoff timestamp and counts
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    cutoff_iso = cutoff.isoformat()
    
    conn = get_conn()
    
    # Count events to be pruned
    count_result = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE timestamp < ?",
        (cutoff_iso,)
    ).fetchone()
    prune_count = count_result["cnt"] if count_result else 0
    
    archived_count = 0
    
    # Optional: Archive before deletion
    if ARCHIVE_ENABLED and prune_count > 0:
        try:
            Path(ARCHIVE_DIR).mkdir(parents=True, exist_ok=True)
            
            # Fetch rows to archive
            rows = conn.execute(
                """
                SELECT event_id, event_type, source, severity, tenant_id, 
                       payload, timestamp, received_at, client_ip
                FROM events 
                WHERE timestamp < ?
                ORDER BY timestamp ASC
                """,
                (cutoff_iso,)
            ).fetchall()
            
            if rows:
                # Create archive file with cutoff date
                archive_filename = f"events-{cutoff.date()}.ndjson"
                archive_path = Path(ARCHIVE_DIR) / archive_filename
                
                with archive_path.open("a", encoding="utf-8") as f:
                    for row in rows:
                        event_dict = {
                            "event_id": row["event_id"],
                            "event_type": row["event_type"],
                            "source": row["source"],
                            "severity": row["severity"],
                            "tenant_id": row["tenant_id"],
                            "payload": row["payload"],
                            "timestamp": row["timestamp"],
                            "received_at": row["received_at"],
                            "client_ip": row["client_ip"],
                        }
                        f.write(json.dumps(event_dict) + "\n")
                        archived_count += 1
                
                print(f"[event_store] 📦 Archived {archived_count} events to {archive_path}")
        
        except Exception as e:
            print(f"[event_store] ⚠️  Archive failed: {e}")
            # Continue with deletion even if archive fails
    
    # Delete old events
    conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_iso,))
    conn.commit()
    conn.close()
    
    print(f"[event_store] 🗑️  Pruned {prune_count} events older than {cutoff.date()}")
    
    return {
        "status": "ok",
        "cutoff": cutoff_iso,
        "retention_days": RETENTION_DAYS,
        "pruned_count": prune_count,
        "archived": ARCHIVE_ENABLED,
        "archived_count": archived_count if ARCHIVE_ENABLED else None,
        "archive_dir": ARCHIVE_DIR if ARCHIVE_ENABLED else None,
    }


def get_retention_settings() -> dict[str, Any]:
    """
    Get current retention configuration.
    
    Phase VII M2: Returns retention settings for ops visibility.
    
    Returns:
        Retention configuration dictionary
    """
    return {
        "retention_days": RETENTION_DAYS,
        "interval_seconds": int(os.getenv("EVENT_RETENTION_CRON_SECONDS", "3600")),
        "archive_enabled": ARCHIVE_ENABLED,
        "archive_dir": ARCHIVE_DIR,
    }
