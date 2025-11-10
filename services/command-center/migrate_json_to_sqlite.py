#!/usr/bin/env python
"""
JSON -> SQLite migration for AetherLink Command Center

- Reads existing JSON persistence files:
    data/acculynx_schedules.json
    data/acculynx_audit.json
    data/local_action_runs.json

- Writes them into SQLite using the same schema your new persistence
  layer is expecting (Phase XVII-B).

Run once before switching to:
    COMMAND_CENTER_STORE=sqlite
Optionally keep JSON around as backup.
"""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = os.environ.get(
    "COMMAND_CENTER_SQLITE_PATH",
    str(DATA_DIR / "command_center.db"),
)

SCHEDULES_FILE = DATA_DIR / "acculynx_schedules.json"
AUDIT_FILE = DATA_DIR / "acculynx_audit.json"
LOCAL_RUNS_FILE = DATA_DIR / "local_action_runs.json"


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] failed to load {path}: {e}")
        return None


def ensure_db(conn: sqlite3.Connection):
    cur = conn.cursor()

    # tables matching the actual SQLiteBackend schema
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS import_schedules (
            tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
            schedule_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
            import_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            records_processed INTEGER DEFAULT 0,
            error_message TEXT,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, import_id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            details_json TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            tenant_id TEXT,
            payload_json TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            tenant_id TEXT,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            resolved_at TIMESTAMP,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS local_action_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_name TEXT NOT NULL,
            tenant_id TEXT,
            status TEXT NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            output_json TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # WAL is nice for concurrent reads
    cur.execute("PRAGMA journal_mode=WAL;")
    conn.commit()


def upsert_tenant(conn: sqlite3.Connection, tenant_id: str):
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM tenants WHERE tenant_id = ?",
        (tenant_id,),
    )
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO tenants (tenant_id, config_json) VALUES (?, ?)",
            (tenant_id, json.dumps({"tenant_id": tenant_id})),
        )
        conn.commit()


def migrate_schedules(conn: sqlite3.Connection, schedules: dict):
    if not schedules:
        print("[info] no schedules to migrate")
        return

    print(f"[info] migrating {len(schedules)} schedules...")
    cur = conn.cursor()
    for tenant, sched in schedules.items():
        upsert_tenant(conn, tenant)
        cur.execute(
            """
            INSERT INTO import_schedules (tenant_id, schedule_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                schedule_json=excluded.schedule_json,
                updated_at=excluded.updated_at
            """,
            (
                tenant,
                json.dumps(sched),
                datetime.now(UTC).isoformat(),
            ),
        )
    conn.commit()
    print("[info] schedules migrated")


def migrate_audit(conn: sqlite3.Connection, audit_entries: list):
    if not audit_entries:
        print("[info] no audit entries to migrate")
        return

    print(f"[info] migrating {len(audit_entries)} audit entries...")
    cur = conn.cursor()
    for entry in audit_entries:
        ts = entry.get("ts", 0.0)
        tenant = entry.get("tenant")
        operation = entry.get("operation", "unknown")
        source = entry.get("source", "unknown")
        metadata = entry.get("metadata") or {}

        # Convert ts (float) to datetime string for SQLite
        ts_datetime = (
            datetime.fromtimestamp(ts, tz=UTC).isoformat()
            if ts > 0
            else datetime.now(UTC).isoformat()
        )

        cur.execute(
            """
            INSERT INTO audit_log (tenant_id, action, resource, details_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                tenant,
                operation,
                source,
                json.dumps(metadata),
                ts_datetime,
            ),
        )
    conn.commit()
    print("[info] audit migrated")


def migrate_local_runs(conn: sqlite3.Connection, runs: list):
    if not runs:
        print("[info] no local runs to migrate")
        return

    print(f"[info] migrating {len(runs)} local action runs...")
    cur = conn.cursor()
    for run in runs:
        ts = run.get("timestamp", run.get("ts", 0.0))
        ts_datetime = datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts > 0 else None
        action_name = run.get("action")
        tenant_id = run.get("tenant")
        status = "completed" if run.get("ok") else "failed"
        output_json = json.dumps({"stdout": run.get("stdout", ""), "stderr": run.get("stderr", "")})
        error_message = run.get("error")

        cur.execute(
            """
            INSERT INTO local_action_runs (action_name, tenant_id, status, started_at, completed_at, output_json, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_name,
                tenant_id,
                status,
                ts_datetime,
                ts_datetime,
                output_json,
                error_message,
            ),
        )
    conn.commit()
    print("[info] local runs migrated")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)

    schedules = load_json(SCHEDULES_FILE) or {}
    audit_entries = load_json(AUDIT_FILE) or []
    local_runs = load_json(LOCAL_RUNS_FILE) or []

    migrate_schedules(conn, schedules)
    migrate_audit(conn, audit_entries)
    migrate_local_runs(conn, local_runs)

    conn.close()
    print(f"[done] migration complete → {DB_PATH}")


if __name__ == "__main__":
    main()
