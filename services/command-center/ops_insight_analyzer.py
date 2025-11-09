from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

RECOVERY_DB = Path("monitoring/recovery_events.sqlite")


class OpsInsightAnalyzer:
    """Reads remediation events and produces operator-facing insights."""

    def __init__(self, db_path: Path | str = RECOVERY_DB) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            conn = sqlite3.connect(":memory:")
            self._create_schema(conn)
            return conn
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _create_schema(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS remediation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                alertname TEXT,
                tenant TEXT,
                action TEXT,
                status TEXT,
                details TEXT
            )
        """)
        conn.commit()

    def get_raw_events(self, limit: int = 500) -> list[sqlite3.Row]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, ts, alertname, tenant, action, status, details
               FROM remediation_events
               ORDER BY id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return rows

    def compute_summary(self, window_hours: int = 24) -> dict[str, Any]:
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=window_hours)
        prev_window_start = window_start - timedelta(hours=window_hours)
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        current = cur.execute(
            """
            SELECT ts, tenant, action, status, alertname
            FROM remediation_events
            WHERE datetime(ts) >= datetime(?)
        """,
            (window_start.isoformat().replace("+00:00", "Z"),),
        ).fetchall()

        previous = cur.execute(
            """
            SELECT ts, tenant, action, status, alertname
            FROM remediation_events
            WHERE datetime(ts) >= datetime(?) AND datetime(ts) < datetime(?)
        """,
            (
                prev_window_start.isoformat().replace("+00:00", "Z"),
                window_start.isoformat().replace("+00:00", "Z"),
            ),
        ).fetchall()
        conn.close()

        def agg(rows: list[sqlite3.Row]) -> dict[str, Any]:
            total = len(rows)
            success = sum(1 for r in rows if (r["status"] or "").lower() == "success")
            per_tenant, per_action, per_alert = defaultdict(int), defaultdict(int), defaultdict(int)
            for r in rows:
                per_tenant[r["tenant"] or "system"] += 1
                per_action[r["action"] or "unknown"] += 1
                per_alert[r["alertname"] or "unknown_alert"] += 1
            return {
                "total": total,
                "success": success,
                "success_rate": (success / total * 100) if total else 0.0,
                "per_tenant": dict(sorted(per_tenant.items(), key=lambda x: x[1], reverse=True)),
                "per_action": dict(sorted(per_action.items(), key=lambda x: x[1], reverse=True)),
                "per_alert": dict(sorted(per_alert.items(), key=lambda x: x[1], reverse=True)),
            }

        cur_stats = agg(current)
        prev_stats = agg(previous)
        return {
            "window_hours": window_hours,
            "current": cur_stats,
            "previous": prev_stats,
            "trend": {
                "total_delta": cur_stats["total"] - prev_stats["total"],
                "success_rate_delta": cur_stats["success_rate"] - prev_stats["success_rate"],
            },
        }

    def build_insight_payload(self) -> dict[str, Any]:
        s24 = self.compute_summary(24)
        s1 = self.compute_summary(1)
        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": {"last_1h": s1["current"], "last_24h": s24["current"]},
            "trends": {"last_24h": s24["trend"]},
            "top": {
                "tenants_24h": s24["current"]["per_tenant"],
                "actions_24h": s24["current"]["per_action"],
                "alerts_24h": s24["current"]["per_alert"],
            },
        }
