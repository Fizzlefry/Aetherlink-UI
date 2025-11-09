# services/command-center/event_store.py
"""
Event storage layer for Command Center.
Phase VI M2: Persistent event storage using SQLite.
"""

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
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

    # Phase VII M4: Per-tenant retention policies
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_retention (
            tenant_id TEXT PRIMARY KEY,
            retention_days INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # Phase VII M5: Reliable alert delivery queue
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_delivery_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_event_id TEXT NOT NULL,
            alert_payload TEXT NOT NULL,
            webhook_url TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_attempt_at TEXT NOT NULL,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_next_attempt ON alert_delivery_queue(next_attempt_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_alert_event ON alert_delivery_queue(alert_event_id)"
    )

    # Phase VII M5: Alert delivery deduplication
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_delivery_history (
            rule_name TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            last_sent_at TEXT NOT NULL,
            PRIMARY KEY (rule_name, tenant_id)
        )
        """
    )

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
    last_24h_where = (
        " AND timestamp >= datetime('now', '-1 day')"
        if tenant_id
        else " WHERE timestamp >= datetime('now', '-1 day')"
    )
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

RETENTION_DAYS = int(os.getenv("EVENT_RETENTION_DAYS", "7"))
ARCHIVE_ENABLED = os.getenv("EVENT_ARCHIVE_ENABLED", "false").lower() == "true"
ARCHIVE_DIR = os.getenv("EVENT_ARCHIVE_DIR", "/app/data/archive")


# ============================================================================
# Phase VII M4: Per-Tenant Retention Policies
# ============================================================================


def get_tenant_retention_map() -> dict[str, int]:
    """
    Get per-tenant retention overrides.

    Phase VII M4: Returns map of tenant_id -> retention_days for tenants
    with custom retention policies. Tenants not in this map use global default.

    Returns:
        Dictionary mapping tenant_id to retention_days
    """
    conn = get_conn()
    try:
        cur = conn.execute("SELECT tenant_id, retention_days FROM tenant_retention")
        rows = cur.fetchall()
        return {row["tenant_id"]: row["retention_days"] for row in rows}
    finally:
        conn.close()


def set_tenant_retention(tenant_id: str, retention_days: int) -> dict[str, Any]:
    """
    Set or update tenant-specific retention policy.

    Args:
        tenant_id: Tenant identifier
        retention_days: Number of days to retain events for this tenant

    Returns:
        Summary with tenant_id and retention_days
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    try:
        # Upsert tenant retention policy
        conn.execute(
            """
            INSERT INTO tenant_retention (tenant_id, retention_days, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                retention_days = excluded.retention_days,
                updated_at = excluded.updated_at
            """,
            (tenant_id, retention_days, now, now),
        )
        conn.commit()
        return {"tenant_id": tenant_id, "retention_days": retention_days, "updated_at": now}
    finally:
        conn.close()


def delete_tenant_retention(tenant_id: str) -> dict[str, Any]:
    """
    Delete tenant-specific retention policy (reverts to global default).

    Args:
        tenant_id: Tenant identifier

    Returns:
        Summary with deleted tenant_id
    """
    conn = get_conn()
    try:
        conn.execute("DELETE FROM tenant_retention WHERE tenant_id = ?", (tenant_id,))
        conn.commit()
        return {"tenant_id": tenant_id, "reverted_to_global": True}
    finally:
        conn.close()


def prune_old_events_with_per_tenant() -> list[dict[str, Any]]:
    """
    Prune events with per-tenant retention policies.

    Phase VII M4: Prunes system events using global retention, then prunes
    each tenant's events using their custom retention policy (if set) or
    global default.

    Returns:
        List of pruning results, one per scope (global/system and per tenant)
    """
    results = []
    tenant_map = get_tenant_retention_map()
    now = datetime.now(UTC)
    conn = get_conn()

    try:
        # 1) Prune system/global events (tenant_id IS NULL) using global retention
        cutoff_global = now - timedelta(days=RETENTION_DAYS)
        cutoff_global_iso = cutoff_global.isoformat()

        cur = conn.execute(
            "DELETE FROM events WHERE (tenant_id IS NULL OR tenant_id = 'system') AND timestamp < ?",
            (cutoff_global_iso,),
        )
        conn.commit()
        global_pruned = cur.rowcount

        results.append(
            {
                "scope": "system",
                "retention_days": RETENTION_DAYS,
                "cutoff": cutoff_global_iso,
                "pruned_count": global_pruned,
            }
        )

        print(
            f"[event_store] 🗑️  Pruned {global_pruned} system events (retention: {RETENTION_DAYS}d)"
        )

        # 2) Get all distinct tenant_ids from events (excluding NULL/system)
        tenant_rows = conn.execute(
            "SELECT DISTINCT tenant_id FROM events WHERE tenant_id IS NOT NULL AND tenant_id != 'system'"
        ).fetchall()
        active_tenants = {row["tenant_id"] for row in tenant_rows}

        # 3) Prune per tenant (use override if exists, else global default)
        for tenant_id in active_tenants:
            retention_days = tenant_map.get(tenant_id, RETENTION_DAYS)
            cutoff_tenant = now - timedelta(days=retention_days)
            cutoff_tenant_iso = cutoff_tenant.isoformat()

            cur = conn.execute(
                "DELETE FROM events WHERE tenant_id = ? AND timestamp < ?",
                (tenant_id, cutoff_tenant_iso),
            )
            conn.commit()
            tenant_pruned = cur.rowcount

            results.append(
                {
                    "scope": tenant_id,
                    "retention_days": retention_days,
                    "cutoff": cutoff_tenant_iso,
                    "pruned_count": tenant_pruned,
                }
            )

            if tenant_pruned > 0:
                print(
                    f"[event_store] 🗑️  Pruned {tenant_pruned} events for {tenant_id} (retention: {retention_days}d)"
                )

        return results

    finally:
        conn.close()


def prune_old_events() -> dict[str, Any]:
    """
    Prune events older than retention window.

    Phase VII M2: Deletes events older than EVENT_RETENTION_DAYS.
    Optionally archives them to NDJSON before deletion.

    Returns:
        Pruning summary with cutoff timestamp and counts
    """
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    cutoff_iso = cutoff.isoformat()

    conn = get_conn()

    # Count events to be pruned
    count_result = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE timestamp < ?", (cutoff_iso,)
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
                (cutoff_iso,),
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


# ============================================================================
# Phase VII M5: Reliable Alert Delivery Queue
# ============================================================================

DEDUP_WINDOW_SECONDS = int(os.getenv("ALERT_DEDUP_WINDOW_SECONDS", "300"))  # 5 minutes default


def check_dedup_window(rule_name: str, tenant_id: str) -> bool:
    """
    Check if alert should be deduplicated (already sent recently).

    Phase VII M5: Prevents alert spam by checking if the same alert
    (rule + tenant) was sent within the dedup window.

    Args:
        rule_name: Alert rule name
        tenant_id: Tenant identifier

    Returns:
        True if alert should be sent (not a duplicate), False if should skip
    """
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT last_sent_at FROM alert_delivery_history WHERE rule_name = ? AND tenant_id = ?",
            (rule_name, tenant_id),
        )
        row = cur.fetchone()

        if not row:
            return True  # Never sent before, allow

        last_sent = datetime.fromisoformat(row["last_sent_at"])
        now = datetime.now(UTC)
        elapsed = (now - last_sent).total_seconds()

        return elapsed >= DEDUP_WINDOW_SECONDS

    finally:
        conn.close()


def update_dedup_history(rule_name: str, tenant_id: str):
    """
    Update dedup history after sending an alert.

    Args:
        rule_name: Alert rule name
        tenant_id: Tenant identifier
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    try:
        conn.execute(
            """
            INSERT INTO alert_delivery_history (rule_name, tenant_id, last_sent_at)
            VALUES (?, ?, ?)
            ON CONFLICT(rule_name, tenant_id) DO UPDATE SET
                last_sent_at = excluded.last_sent_at
            """,
            (rule_name, tenant_id, now),
        )
        conn.commit()
    finally:
        conn.close()


def enqueue_alert_delivery(
    alert_event_id: str, alert_payload: dict[str, Any], webhook_url: str, max_attempts: int = 5
) -> int:
    """
    Enqueue an alert for delivery to a webhook.

    Phase VII M5: Adds alert to delivery queue for reliable, retryable delivery.

    Args:
        alert_event_id: ID of the alert event
        alert_payload: Full alert event payload (for webhook POST)
        webhook_url: Destination webhook URL
        max_attempts: Maximum delivery attempts before giving up

    Returns:
        Queue entry ID
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    try:
        cur = conn.execute(
            """
            INSERT INTO alert_delivery_queue (
                alert_event_id, alert_payload, webhook_url,
                attempt_count, max_attempts, next_attempt_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                alert_event_id,
                json.dumps(alert_payload),
                webhook_url,
                max_attempts,
                now,  # next_attempt_at = now (immediate delivery)
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_pending_deliveries(limit: int = 50) -> list[dict[str, Any]]:
    """
    Get pending deliveries that are ready for attempt.

    Phase VII M5: Returns deliveries where next_attempt_at <= now
    and attempt_count < max_attempts.

    Args:
        limit: Maximum number of deliveries to return

    Returns:
        List of delivery queue entries
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    try:
        cur = conn.execute(
            """
            SELECT id, alert_event_id, alert_payload, webhook_url,
                   attempt_count, max_attempts, next_attempt_at,
                   last_error, created_at, updated_at
            FROM alert_delivery_queue
            WHERE next_attempt_at <= ? AND attempt_count < max_attempts
            ORDER BY next_attempt_at ASC
            LIMIT ?
            """,
            (now, limit),
        )
        rows = cur.fetchall()

        return [
            {
                "id": row["id"],
                "alert_event_id": row["alert_event_id"],
                "alert_payload": json.loads(row["alert_payload"]),
                "webhook_url": row["webhook_url"],
                "attempt_count": row["attempt_count"],
                "max_attempts": row["max_attempts"],
                "next_attempt_at": row["next_attempt_at"],
                "last_error": row["last_error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def update_delivery_attempt(delivery_id: int, success: bool, error_message: str | None = None):
    """
    Update delivery queue entry after an attempt.

    Phase VII M5: Increments attempt_count, schedules next retry with backoff,
    or marks complete if successful.

    Args:
        delivery_id: Queue entry ID
        success: Whether delivery succeeded
        error_message: Error message if delivery failed
    """
    conn = get_conn()
    now = datetime.now(UTC)

    try:
        if success:
            # Remove from queue on success
            conn.execute("DELETE FROM alert_delivery_queue WHERE id = ?", (delivery_id,))
        else:
            # Get current attempt count
            cur = conn.execute(
                "SELECT attempt_count, max_attempts FROM alert_delivery_queue WHERE id = ?",
                (delivery_id,),
            )
            row = cur.fetchone()

            if not row:
                return

            new_attempt_count = row["attempt_count"] + 1
            max_attempts = row["max_attempts"]

            if new_attempt_count >= max_attempts:
                # Max attempts reached, delete from queue (will emit failure event separately)
                conn.execute("DELETE FROM alert_delivery_queue WHERE id = ?", (delivery_id,))
            else:
                # Calculate backoff: 30s, 2m, 5m, 15m, 30m
                backoff_seconds = min(30 * (2**new_attempt_count), 1800)  # Cap at 30 minutes
                next_attempt = now + timedelta(seconds=backoff_seconds)

                conn.execute(
                    """
                    UPDATE alert_delivery_queue
                    SET attempt_count = ?,
                        next_attempt_at = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        new_attempt_count,
                        next_attempt.isoformat(),
                        error_message,
                        now.isoformat(),
                        delivery_id,
                    ),
                )

        conn.commit()
    finally:
        conn.close()


def get_delivery_stats() -> dict[str, Any]:
    """
    Get delivery queue statistics for ops visibility.

    Phase VII M5: Returns counts of pending, failed, and total deliveries.

    Returns:
        Statistics dictionary
    """
    conn = get_conn()
    now = datetime.now(UTC).isoformat()

    try:
        # Total queued
        total_result = conn.execute("SELECT COUNT(*) as cnt FROM alert_delivery_queue").fetchone()
        total = total_result["cnt"] if total_result else 0

        # Pending (ready for retry)
        pending_result = conn.execute(
            "SELECT COUNT(*) as cnt FROM alert_delivery_queue WHERE next_attempt_at <= ?", (now,)
        ).fetchone()
        pending = pending_result["cnt"] if pending_result else 0

        # Near max attempts (attempt_count >= max_attempts - 1)
        failing_result = conn.execute(
            "SELECT COUNT(*) as cnt FROM alert_delivery_queue WHERE attempt_count >= max_attempts - 1"
        ).fetchone()
        failing = failing_result["cnt"] if failing_result else 0

        return {
            "total_queued": total,
            "pending_now": pending,
            "near_failure": failing,
            "dedup_window_seconds": DEDUP_WINDOW_SECONDS,
        }

    finally:
        conn.close()


def get_delivery_queue(limit: int = 100) -> list[dict[str, Any]]:
    """
    Get all delivery queue entries for ops visibility.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of delivery queue entries
    """
    conn = get_conn()

    try:
        cur = conn.execute(
            """
            SELECT id, alert_event_id, webhook_url, attempt_count,
                   max_attempts, next_attempt_at, last_error,
                   created_at, updated_at
            FROM alert_delivery_queue
            ORDER BY next_attempt_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()

        return [
            {
                "id": row["id"],
                "alert_event_id": row["alert_event_id"],
                "webhook_url": row["webhook_url"],
                "attempt_count": row["attempt_count"],
                "max_attempts": row["max_attempts"],
                "next_attempt_at": row["next_attempt_at"],
                "last_error": row["last_error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()
