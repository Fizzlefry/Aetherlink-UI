"""
Alert Rules Storage and Management

Phase VI M6: Alert threshold definitions and rule evaluation.
Stores alert rules in SQLite alongside events.
"""

import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

DB_PATH = os.getenv("ALERT_DB_PATH", "/app/data/alerts.db")


def get_conn():
    """Get SQLite connection with dict cursor."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize alert rules database.

    Creates tables for alert rules if they don't exist.
    Called on Command Center startup.

    Phase VII M3: Added tenant_id column for multi-tenant alert scoping.
    """
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            severity TEXT,
            event_type TEXT,
            source TEXT,
            window_seconds INTEGER NOT NULL,
            threshold INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            tenant_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """
    )

    # Phase VII M3: Migration - add tenant_id column if not exists
    try:
        conn.execute("ALTER TABLE alert_rules ADD COLUMN tenant_id TEXT")
        conn.commit()
        print("[alert_store] ✅ Added tenant_id column to alert_rules")
    except sqlite3.OperationalError as e:
        # Column already exists, ignore
        if "duplicate column" not in str(e).lower():
            print(f"[alert_store] ⚠️  Migration warning: {e}")

    conn.commit()
    conn.close()
    print("[alert_store] ✅ Alert rules database initialized")


def create_rule(
    name: str,
    window_seconds: int,
    threshold: int,
    severity: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    enabled: bool = True,
    tenant_id: str | None = None,
) -> int:
    """
    Create a new alert rule.

    Phase VII M3: Added tenant_id for multi-tenant alert scoping.

    Args:
        name: Human-readable rule name
        window_seconds: Time window to look back
        threshold: Number of events to trigger alert
        severity: Filter by severity (optional)
        event_type: Filter by event type (optional)
        source: Filter by source service (optional)
        enabled: Whether rule is active
        tenant_id: Bind rule to tenant (optional, NULL = global/admin rule)

    Returns:
        Rule ID
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    cur = conn.execute(
        """
        INSERT INTO alert_rules
        (name, severity, event_type, source, window_seconds, threshold, enabled, tenant_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            severity.lower() if severity else None,
            event_type,
            source,
            window_seconds,
            threshold,
            1 if enabled else 0,
            tenant_id,
            now,
            now,
        ),
    )

    rule_id = cur.lastrowid
    conn.commit()
    conn.close()

    return rule_id


def list_rules() -> list[dict[str, Any]]:
    """
    List all alert rules.

    Returns:
        List of rule dictionaries
    """
    conn = get_conn()
    cur = conn.execute(
        """
        SELECT id, name, severity, event_type, source, window_seconds,
               threshold, enabled, created_at, updated_at
        FROM alert_rules
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "severity": r["severity"],
            "event_type": r["event_type"],
            "source": r["source"],
            "window_seconds": r["window_seconds"],
            "threshold": r["threshold"],
            "enabled": bool(r["enabled"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def get_rule(rule_id: int) -> dict[str, Any] | None:
    """
    Get a specific alert rule.

    Args:
        rule_id: Rule ID

    Returns:
        Rule dictionary or None if not found
    """
    conn = get_conn()
    cur = conn.execute(
        """
        SELECT id, name, severity, event_type, source, window_seconds,
               threshold, enabled, created_at, updated_at
        FROM alert_rules
        WHERE id = ?
        """,
        (rule_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "severity": row["severity"],
        "event_type": row["event_type"],
        "source": row["source"],
        "window_seconds": row["window_seconds"],
        "threshold": row["threshold"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def delete_rule(rule_id: int) -> bool:
    """
    Delete an alert rule.

    Args:
        rule_id: Rule ID

    Returns:
        True if deleted, False if not found
    """
    conn = get_conn()
    cur = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()

    return deleted


def update_rule_enabled(rule_id: int, enabled: bool) -> bool:
    """
    Enable or disable an alert rule.

    Args:
        rule_id: Rule ID
        enabled: New enabled state

    Returns:
        True if updated, False if not found
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    cur = conn.execute(
        """
        UPDATE alert_rules
        SET enabled = ?, updated_at = ?
        WHERE id = ?
        """,
        (1 if enabled else 0, now, rule_id),
    )

    updated = cur.rowcount > 0
    conn.commit()
    conn.close()

    return updated
