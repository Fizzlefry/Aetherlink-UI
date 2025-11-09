from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable


class SQLiteStore:
    def __init__(
        self,
        dsn_path: str,
        on_op: Callable[[str, str], None] | None = None,
        on_failure: Callable[[str, str], None] | None = None,
    ) -> None:
        self._dsn = dsn_path
        self._on_op = on_op
        self._on_failure = on_failure
        self._conn = sqlite3.connect(self._dsn, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    tenant TEXT PRIMARY KEY,
                    interval_sec INTEGER,
                    paused INTEGER,
                    last_run REAL,
                    last_status_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL,
                    tenant TEXT,
                    operation TEXT,
                    source TEXT,
                    metadata_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS local_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL,
                    tenant TEXT,
                    action TEXT,
                    ok INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    error_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    ts_iso TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    source TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_tenant_ts ON events(tenant, ts DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(type, ts DESC)
                """
            )
            self._conn.commit()
        except Exception:
            self._record_failure("schema", "init")
            raise

    def is_empty(self) -> bool:
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(1) FROM schedules")
            s_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(1) FROM audit")
            a_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(1) FROM local_runs")
            l_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(1) FROM events")
            e_cnt = cur.fetchone()[0]
            return (s_cnt == 0) and (a_cnt == 0) and (l_cnt == 0) and (e_cnt == 0)
        except Exception:
            self._record_failure("meta", "is_empty")
            return True

    def load_schedules(self) -> dict[str, dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT tenant, interval_sec, paused, last_run, last_status_json FROM schedules"
            )
            rows = cur.fetchall()
            out: dict[str, dict[str, Any]] = {}
            for r in rows:
                last_status = json.loads(r["last_status_json"]) if r["last_status_json"] else {}
                out[r["tenant"]] = {
                    "interval_sec": int(r["interval_sec"]) if r["interval_sec"] is not None else 300,
                    "paused": bool(r["paused"]),
                    "last_run": float(r["last_run"]) if r["last_run"] is not None else 0.0,
                    "last_status": last_status,
                }
            return out
        except Exception:
            self._record_failure("schedules", "select")
            return {}

    def save_schedule(self, tenant: str, data: dict[str, Any]) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO schedules(tenant, interval_sec, paused, last_run, last_status_json)
                VALUES(?,?,?,?,?)
                ON CONFLICT(tenant) DO UPDATE SET
                    interval_sec=excluded.interval_sec,
                    paused=excluded.paused,
                    last_run=excluded.last_run,
                    last_status_json=excluded.last_status_json
                """,
                (
                    tenant,
                    int(data.get("interval_sec", 300)),
                    1 if data.get("paused") else 0,
                    float(data.get("last_run", 0.0)),
                    json.dumps(data.get("last_status", {})),
                ),
            )
            self._conn.commit()
            self._record_op("schedules", "upsert")
        except Exception:
            self._record_failure("schedules", "upsert")

    def delete_schedule(self, tenant: str) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM schedules WHERE tenant=?", (tenant,))
            self._conn.commit()
            self._record_op("schedules", "delete")
        except Exception:
            self._record_failure("schedules", "delete")

    def list_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT ts, tenant, operation, source, metadata_json FROM audit ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "ts": float(r["ts"]) if r["ts"] is not None else 0.0,
                        "tenant": r["tenant"],
                        "operation": r["operation"],
                        "source": r["source"],
                        "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
                    }
                )
            return out
        except Exception:
            self._record_failure("audit", "select")
            return []

    def append_audit(self, record: dict[str, Any]) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO audit(ts, tenant, operation, source, metadata_json)
                VALUES(?,?,?,?,?)
                """,
                (
                    float(record.get("ts", 0.0)),
                    record.get("tenant"),
                    record.get("operation"),
                    record.get("source"),
                    json.dumps(record.get("metadata", {})),
                ),
            )
            self._conn.commit()
            self._record_op("audit", "insert")
        except Exception:
            self._record_failure("audit", "insert")

    def list_local_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT ts, tenant, action, ok, stdout, stderr, error_json FROM local_runs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "timestamp": float(r["ts"]) if r["ts"] is not None else 0.0,
                        "tenant": r["tenant"],
                        "action": r["action"],
                        "ok": bool(r["ok"]),
                        "stdout": r["stdout"],
                        "stderr": r["stderr"],
                        "error": json.loads(r["error_json"]) if r["error_json"] else None,
                    }
                )
            return out
        except Exception:
            self._record_failure("local_runs", "select")
            return []

    def append_local_run(self, record: dict[str, Any]) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO local_runs(ts, tenant, action, ok, stdout, stderr, error_json)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    float(record.get("timestamp", 0.0)),
                    record.get("tenant"),
                    record.get("action"),
                    1 if record.get("ok") else 0,
                    record.get("stdout"),
                    record.get("stderr"),
                    json.dumps(record.get("error")) if record.get("error") is not None else None,
                ),
            )
            self._conn.commit()
            self._record_op("local_runs", "insert")
        except Exception:
            self._record_failure("local_runs", "insert")

    def append_event(self, event: dict[str, Any]) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO events(ts, ts_iso, tenant, source, type, payload_json)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    float(event.get("ts", 0.0)),
                    event.get("ts_iso"),
                    event.get("tenant"),
                    event.get("source"),
                    event.get("type"),
                    json.dumps(event.get("payload", {})),
                ),
            )
            self._conn.commit()
            self._record_op("events", "insert")
        except Exception:
            self._record_failure("events", "insert")

    def list_events(
        self, tenant: str | None = None, type_prefix: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            query = "SELECT ts, ts_iso, tenant, source, type, payload_json FROM events"
            conditions = []
            params = []
            if tenant:
                conditions.append("tenant = ?")
                params.append(tenant)
            if type_prefix:
                conditions.append("type LIKE ?")
                params.append(f"{type_prefix}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            cur.execute(query, params)
            rows = cur.fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "ts": float(r["ts"]) if r["ts"] is not None else 0.0,
                        "ts_iso": r["ts_iso"],
                        "tenant": r["tenant"],
                        "source": r["source"],
                        "type": r["type"],
                        "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                    }
                )
            return out
        except Exception:
            self._record_failure("events", "select")
            return []

    # instrumentation helpers
    def _record_op(self, table: str, op: str) -> None:
        if self._on_op:
            try:
                self._on_op(table, op)
            except Exception:
                pass

    def _record_failure(self, table: str, op: str) -> None:
        if self._on_failure:
            try:
                self._on_failure(table, op)
            except Exception:
                pass

