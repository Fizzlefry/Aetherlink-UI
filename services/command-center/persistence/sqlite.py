"""
SQLite Persistence Backend

Phase XVII-B: SQLite implementation of the persistence interface.
Provides relational storage with proper indexing and transactions.
"""

import asyncio
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base import PersistenceBackend


class SQLiteBackend(PersistenceBackend):
    """SQLite-based persistence backend with proper schema and indexing."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Initialize SQLite database and create tables."""
        # SQLite is not async, so we run in thread pool
        await asyncio.get_event_loop().run_in_executor(None, self._init_db_sync)

    def _init_db_sync(self) -> None:
        """Synchronous database initialization."""
        self._connection = sqlite3.connect(str(self.db_path))
        self._connection.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        self._connection.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        self._connection.execute("PRAGMA foreign_keys=ON")  # Enable FK constraints

        # Create tables
        self._create_tables()

        # Create indexes for performance
        self._create_indexes()

    def _create_tables(self) -> None:
        """Create database tables."""
        assert self._connection is not None

        # Tenants table
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Import schedules (replaces JSON schedules)
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS import_schedules (
                tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id),
                schedule_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Import history
        self._connection.execute("""
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
            )
        """)

        # Audit log
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                details_json TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Events
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                tenant_id TEXT,
                payload_json TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Alerts
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                tenant_id TEXT,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                resolved_at TIMESTAMP,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Local action runs
        self._connection.execute("""
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
            )
        """)

        # Phase XXXV: Anomaly events
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_name TEXT NOT NULL,
                tenant_id TEXT,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                anomaly_type TEXT,
                metric_name TEXT,
                threshold_value REAL,
                actual_value REAL,
                detection_time TIMESTAMP,
                metadata_json TEXT,
                resolved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Phase XXXV: Remediation actions
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS remediation_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anomaly_event_id INTEGER REFERENCES anomaly_events(id),
                tenant_id TEXT,
                action_type TEXT NOT NULL,
                action_params TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                executed_at TIMESTAMP,
                completed_at TIMESTAMP,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._connection.commit()

    def _create_indexes(self) -> None:
        """Create database indexes for query performance."""
        assert self._connection is not None

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_import_history_tenant ON import_history(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_import_history_status ON import_history(status)",
            "CREATE INDEX IF NOT EXISTS idx_import_history_started ON import_history(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved_at)",
            "CREATE INDEX IF NOT EXISTS idx_local_runs_tenant ON local_action_runs(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_local_runs_status ON local_action_runs(status)",
            # Phase XXXV: Anomaly and remediation indexes
            "CREATE INDEX IF NOT EXISTS idx_anomaly_events_tenant ON anomaly_events(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_anomaly_events_alert ON anomaly_events(alert_name)",
            "CREATE INDEX IF NOT EXISTS idx_anomaly_events_created ON anomaly_events(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_anomaly_events_resolved ON anomaly_events(resolved_at)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_actions_anomaly ON remediation_actions(anomaly_id)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_actions_tenant ON remediation_actions(tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_actions_status ON remediation_actions(status)",
            "CREATE INDEX IF NOT EXISTS idx_remediation_actions_created ON remediation_actions(created_at)",
        ]

        for index_sql in indexes:
            self._connection.execute(index_sql)

        self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await asyncio.get_event_loop().run_in_executor(None, self._connection.close)
            self._connection = None

    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursors."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

    async def save_schedules(self, schedules: dict[str, Any]) -> None:
        """Save tenant import schedules."""
        await asyncio.get_event_loop().run_in_executor(None, self._save_schedules_sync, schedules)

    def _save_schedules_sync(self, schedules: dict[str, Any]) -> None:
        """Synchronous schedule saving."""
        with self._get_cursor() as cursor:
            # Clear existing schedules
            cursor.execute("DELETE FROM import_schedules")

            # Insert new schedules
            for tenant_id, schedule in schedules.items():
                # Ensure tenant exists
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO tenants (tenant_id, config_json)
                    VALUES (?, ?)
                """,
                    (tenant_id, json.dumps({"tenant_id": tenant_id})),
                )

                cursor.execute(
                    """
                    INSERT INTO import_schedules (tenant_id, schedule_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (tenant_id, json.dumps(schedule)),
                )

    async def load_schedules(self) -> dict[str, Any]:
        """Load tenant import schedules."""
        return await asyncio.get_event_loop().run_in_executor(None, self._load_schedules_sync)

    def _load_schedules_sync(self) -> dict[str, Any]:
        """Synchronous schedule loading."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT tenant_id, schedule_json FROM import_schedules")
            rows = cursor.fetchall()
            return {row[0]: json.loads(row[1]) for row in rows}

    async def save_audit_entries(self, entries: list[dict[str, Any]]) -> None:
        """Save audit log entries."""
        await asyncio.get_event_loop().run_in_executor(None, self._save_audit_sync, entries)

    def _save_audit_sync(self, entries: list[dict[str, Any]]) -> None:
        """Synchronous audit saving."""
        with self._get_cursor() as cursor:
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO audit_log (tenant_id, action, resource, details_json, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry.get("tenant_id"),
                        entry.get("action", "unknown"),
                        entry.get("resource", "unknown"),
                        json.dumps(entry.get("details", {})),
                        entry.get("ip_address"),
                        entry.get("user_agent"),
                    ),
                )

    async def load_audit_entries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load audit log entries."""
        return await asyncio.get_event_loop().run_in_executor(None, self._load_audit_sync, limit)

    def _load_audit_sync(self, limit: int | None) -> list[dict[str, Any]]:
        """Synchronous audit loading."""
        with self._get_cursor() as cursor:
            query = """
                SELECT tenant_id, action, resource, details_json, ip_address, user_agent, timestamp
                FROM audit_log
                ORDER BY timestamp DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            return [
                {
                    "tenant_id": row[0],
                    "action": row[1],
                    "resource": row[2],
                    "details": json.loads(row[3]) if row[3] else {},
                    "ip_address": row[4],
                    "user_agent": row[5],
                    "timestamp": row[6],
                }
                for row in rows
            ]

    async def save_local_action_runs(self, runs: list[dict[str, Any]]) -> None:
        """Save local action execution runs."""
        await asyncio.get_event_loop().run_in_executor(None, self._save_runs_sync, runs)

    def _save_runs_sync(self, runs: list[dict[str, Any]]) -> None:
        """Synchronous runs saving."""
        with self._get_cursor() as cursor:
            for run in runs:
                cursor.execute(
                    """
                    INSERT INTO local_action_runs
                    (action_name, tenant_id, status, started_at, completed_at, output_json, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        run.get("action_name", "unknown"),
                        run.get("tenant_id"),
                        run.get("status", "unknown"),
                        run.get("started_at"),
                        run.get("completed_at"),
                        json.dumps(run.get("output", {})),
                        run.get("error_message"),
                    ),
                )

    async def load_local_action_runs(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load local action execution runs."""
        return await asyncio.get_event_loop().run_in_executor(None, self._load_runs_sync, limit)

    def _load_runs_sync(self, limit: int | None) -> list[dict[str, Any]]:
        """Synchronous runs loading."""
        with self._get_cursor() as cursor:
            query = """
                SELECT action_name, tenant_id, status, started_at, completed_at, output_json, error_message, created_at
                FROM local_action_runs
                ORDER BY created_at DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            return [
                {
                    "action_name": row[0],
                    "tenant_id": row[1],
                    "status": row[2],
                    "started_at": row[3],
                    "completed_at": row[4],
                    "output": json.loads(row[5]) if row[5] else {},
                    "error_message": row[6],
                    "created_at": row[7],
                }
                for row in rows
            ]

    async def save_import_record(self, tenant: str, import_data: dict[str, Any]) -> None:
        """Save a completed import record."""
        await asyncio.get_event_loop().run_in_executor(
            None, self._save_import_sync, tenant, import_data
        )

    def _save_import_sync(self, tenant: str, import_data: dict[str, Any]) -> None:
        """Synchronous import record saving."""
        with self._get_cursor() as cursor:
            # Ensure tenant exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO tenants (tenant_id, config_json)
                VALUES (?, ?)
            """,
                (tenant, json.dumps({"tenant_id": tenant})),
            )

            cursor.execute(
                """
                INSERT OR REPLACE INTO import_history
                (tenant_id, import_id, status, started_at, completed_at, records_processed, error_message, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tenant,
                    import_data.get("import_id", "unknown"),
                    import_data.get("status", "unknown"),
                    import_data.get("started_at"),
                    import_data.get("completed_at"),
                    import_data.get("records_processed", 0),
                    import_data.get("error_message"),
                    json.dumps(import_data.get("metadata", {})),
                ),
            )

    async def get_import_history(self, tenant: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get import history for a tenant."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_import_history_sync, tenant, limit
        )

    def _get_import_history_sync(self, tenant: str, limit: int) -> list[dict[str, Any]]:
        """Synchronous import history retrieval."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT import_id, status, started_at, completed_at, records_processed, error_message, metadata_json, created_at
                FROM import_history
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (tenant, limit),
            )

            rows = cursor.fetchall()
            return [
                {
                    "import_id": row[0],
                    "status": row[1],
                    "started_at": row[2],
                    "completed_at": row[3],
                    "records_processed": row[4],
                    "error_message": row[5],
                    "metadata": json.loads(row[6]) if row[6] else {},
                    "created_at": row[7],
                }
                for row in rows
            ]

    async def save_event(self, event: dict[str, Any]) -> None:
        """Save an event record."""
        await asyncio.get_event_loop().run_in_executor(None, self._save_event_sync, event)

    def _save_event_sync(self, event: dict[str, Any]) -> None:
        """Synchronous event saving."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO events (event_type, tenant_id, payload_json)
                VALUES (?, ?, ?)
            """,
                (
                    event.get("event_type", "unknown"),
                    event.get("tenant_id"),
                    json.dumps(event.get("payload", {})),
                ),
            )

    async def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events."""
        return await asyncio.get_event_loop().run_in_executor(None, self._get_events_sync, limit)

    def _get_events_sync(self, limit: int) -> list[dict[str, Any]]:
        """Synchronous events retrieval."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT event_type, tenant_id, payload_json, timestamp
                FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            return [
                {
                    "event_type": row[0],
                    "tenant_id": row[1],
                    "payload": json.loads(row[2]) if row[2] else {},
                    "timestamp": row[3],
                }
                for row in rows
            ]

    async def save_alert(self, alert: dict[str, Any]) -> None:
        """Save an alert record."""
        await asyncio.get_event_loop().run_in_executor(None, self._save_alert_sync, alert)

    def _save_alert_sync(self, alert: dict[str, Any]) -> None:
        """Synchronous alert saving."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO alerts (alert_type, tenant_id, severity, message, resolved_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    alert.get("alert_type", "unknown"),
                    alert.get("tenant_id"),
                    alert.get("severity", "info"),
                    alert.get("message", ""),
                    alert.get("resolved_at"),
                    json.dumps(alert.get("metadata", {})),
                ),
            )

    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get currently active alerts."""
        return await asyncio.get_event_loop().run_in_executor(None, self._get_alerts_sync)

    def _get_alerts_sync(self) -> list[dict[str, Any]]:
        """Synchronous active alerts retrieval."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT alert_type, tenant_id, severity, message, resolved_at, metadata_json, created_at
                FROM alerts
                WHERE resolved_at IS NULL
                ORDER BY created_at DESC
            """)

            rows = cursor.fetchall()
            return [
                {
                    "alert_type": row[0],
                    "tenant_id": row[1],
                    "severity": row[2],
                    "message": row[3],
                    "resolved_at": row[4],
                    "metadata": json.loads(row[5]) if row[5] else {},
                    "created_at": row[6],
                }
                for row in rows
            ]

    async def update_tenant_config(self, tenant: str, config: dict[str, Any]) -> None:
        """Update tenant configuration."""
        await asyncio.get_event_loop().run_in_executor(
            None, self._update_tenant_sync, tenant, config
        )

    def _update_tenant_sync(self, tenant: str, config: dict[str, Any]) -> None:
        """Synchronous tenant config update."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO tenants (tenant_id, config_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
                (tenant, json.dumps(config)),
            )

    async def get_tenant_config(self, tenant: str) -> dict[str, Any] | None:
        """Get tenant configuration."""
        return await asyncio.get_event_loop().run_in_executor(None, self._get_tenant_sync, tenant)

    def _get_tenant_sync(self, tenant: str) -> dict[str, Any] | None:
        """Synchronous tenant config retrieval."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT config_json FROM tenants WHERE tenant_id = ?", (tenant,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    async def get_all_tenant_configs(self) -> dict[str, Any]:
        """Get all tenant configurations."""
        return await asyncio.get_event_loop().run_in_executor(None, self._get_all_tenants_sync)

    def _get_all_tenants_sync(self) -> dict[str, Any]:
        """Synchronous all tenant configs retrieval."""
        with self._get_cursor() as cursor:
            cursor.execute("SELECT tenant_id, config_json FROM tenants")
            rows = cursor.fetchall()
            return {row[0]: json.loads(row[1]) for row in rows}

    async def save_anomaly_event(self, anomaly: dict[str, Any]) -> int:
        """Save an anomaly event and return the event ID."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._save_anomaly_sync, anomaly
        )

    def _save_anomaly_sync(self, anomaly: dict[str, Any]) -> int:
        """Synchronous anomaly event saving."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anomaly_events (
                    alert_name, tenant_id, severity, message, anomaly_type,
                    metric_name, threshold_value, actual_value, detection_time,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    anomaly.get("alert_name", ""),
                    anomaly.get("tenant_id", ""),
                    anomaly.get("severity", "warning"),
                    anomaly.get("message", ""),
                    anomaly.get("anomaly_type", "unknown"),
                    anomaly.get("metric_name", ""),
                    anomaly.get("threshold_value"),
                    anomaly.get("actual_value"),
                    anomaly.get("detection_time"),
                    json.dumps(anomaly.get("metadata", {})),
                ),
            )
            return cursor.lastrowid or 0

    async def save_remediation_action(self, remediation: dict[str, Any]) -> int:
        """Save a remediation action and return the action ID."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._save_remediation_sync, remediation
        )

    def _save_remediation_sync(self, remediation: dict[str, Any]) -> int:
        """Synchronous remediation action saving."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO remediation_actions (
                    anomaly_event_id, tenant_id, action_type, action_params,
                    status, error_message, executed_at, completed_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    remediation.get("anomaly_event_id"),
                    remediation.get("tenant_id", ""),
                    remediation.get("action_type", ""),
                    json.dumps(remediation.get("action_params", {})),
                    remediation.get("status", "pending"),
                    remediation.get("error_message"),
                    remediation.get("executed_at"),
                    remediation.get("completed_at"),
                    json.dumps(remediation.get("metadata", {})),
                ),
            )
            return cursor.lastrowid or 0

    async def get_anomaly_history(
        self, tenant_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get historical anomaly events."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_anomaly_history_sync, tenant_id, limit, offset
        )

    def _get_anomaly_history_sync(
        self, tenant_id: str | None, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        """Synchronous anomaly history retrieval."""
        with self._get_cursor() as cursor:
            if tenant_id:
                cursor.execute(
                    """
                    SELECT id, alert_name, tenant_id, severity, message, anomaly_type,
                           metric_name, threshold_value, actual_value, detection_time,
                           metadata_json, created_at
                    FROM anomaly_events
                    WHERE tenant_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (tenant_id, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, alert_name, tenant_id, severity, message, anomaly_type,
                           metric_name, threshold_value, actual_value, detection_time,
                           metadata_json, created_at
                    FROM anomaly_events
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "alert_name": row[1],
                    "tenant_id": row[2],
                    "severity": row[3],
                    "message": row[4],
                    "anomaly_type": row[5],
                    "metric_name": row[6],
                    "threshold_value": row[7],
                    "actual_value": row[8],
                    "detection_time": row[9],
                    "metadata": json.loads(row[10]) if row[10] else {},
                    "created_at": row[11],
                }
                for row in rows
            ]

    async def get_remediation_history(
        self, tenant_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get historical remediation actions."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_remediation_history_sync, tenant_id, limit, offset
        )

    def _get_remediation_history_sync(
        self, tenant_id: str | None, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        """Synchronous remediation history retrieval."""
        with self._get_cursor() as cursor:
            if tenant_id:
                cursor.execute(
                    """
                    SELECT ra.id, ra.anomaly_event_id, ra.tenant_id, ra.action_type,
                           ra.action_params, ra.status, ra.error_message, ra.executed_at,
                           ra.completed_at, ra.metadata_json, ra.created_at,
                           ae.alert_name, ae.severity, ae.message
                    FROM remediation_actions ra
                    LEFT JOIN anomaly_events ae ON ra.anomaly_event_id = ae.id
                    WHERE ra.tenant_id = ?
                    ORDER BY ra.created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (tenant_id, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT ra.id, ra.anomaly_event_id, ra.tenant_id, ra.action_type,
                           ra.action_params, ra.status, ra.error_message, ra.executed_at,
                           ra.completed_at, ra.metadata_json, ra.created_at,
                           ae.alert_name, ae.severity, ae.message
                    FROM remediation_actions ra
                    LEFT JOIN anomaly_events ae ON ra.anomaly_event_id = ae.id
                    ORDER BY ra.created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "anomaly_event_id": row[1],
                    "tenant_id": row[2],
                    "action_type": row[3],
                    "action_params": json.loads(row[4]) if row[4] else {},
                    "status": row[5],
                    "error_message": row[6],
                    "executed_at": row[7],
                    "completed_at": row[8],
                    "metadata": json.loads(row[9]) if row[9] else {},
                    "created_at": row[10],
                    "anomaly_alert_name": row[11],
                    "anomaly_severity": row[12],
                    "anomaly_message": row[13],
                }
                for row in rows
            ]

    async def get_anomaly_stats(
        self, tenant_id: str | None = None, days: int = 30
    ) -> dict[str, Any]:
        """Get anomaly statistics for the specified period."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_anomaly_stats_sync, tenant_id, days
        )

    def _get_anomaly_stats_sync(self, tenant_id: str | None, days: int) -> dict[str, Any]:
        """Synchronous anomaly statistics retrieval."""
        with self._get_cursor() as cursor:
            # Calculate date threshold
            threshold_date = (datetime.now() - timedelta(days=days)).isoformat()

            if tenant_id:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_anomalies,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_count,
                        COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_count,
                        COUNT(CASE WHEN severity = 'info' THEN 1 END) as info_count,
                        COUNT(DISTINCT anomaly_type) as unique_types,
                        AVG(CASE WHEN threshold_value IS NOT NULL AND actual_value IS NOT NULL
                                 THEN ABS(actual_value - threshold_value) END) as avg_deviation
                    FROM anomaly_events
                    WHERE tenant_id = ? AND created_at >= ?
                """,
                    (tenant_id, threshold_date),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_anomalies,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_count,
                        COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_count,
                        COUNT(CASE WHEN severity = 'info' THEN 1 END) as info_count,
                        COUNT(DISTINCT anomaly_type) as unique_types,
                        AVG(CASE WHEN threshold_value IS NOT NULL AND actual_value IS NOT NULL
                                 THEN ABS(actual_value - threshold_value) END) as avg_deviation
                    FROM anomaly_events
                    WHERE created_at >= ?
                """,
                    (threshold_date,),
                )

            row = cursor.fetchone()
            return {
                "total_anomalies": row[0] or 0,
                "critical_count": row[1] or 0,
                "warning_count": row[2] or 0,
                "info_count": row[3] or 0,
                "unique_types": row[4] or 0,
                "avg_deviation": row[5] or 0.0,
                "period_days": days,
            }

    async def get_remediation_effectiveness(
        self, tenant_id: str | None = None, days: int = 30
    ) -> dict[str, Any]:
        """Get remediation effectiveness statistics."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_remediation_effectiveness_sync, tenant_id, days
        )

    def _get_remediation_effectiveness_sync(
        self, tenant_id: str | None, days: int
    ) -> dict[str, Any]:
        """Synchronous remediation effectiveness retrieval."""
        with self._get_cursor() as cursor:
            # Calculate date threshold
            threshold_date = (datetime.now() - timedelta(days=days)).isoformat()

            if tenant_id:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_actions,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_actions,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_actions,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_actions,
                        AVG(CASE WHEN executed_at IS NOT NULL AND completed_at IS NOT NULL
                                 THEN (julianday(completed_at) - julianday(executed_at)) * 86400 END) as avg_resolution_time
                    FROM remediation_actions
                    WHERE tenant_id = ? AND created_at >= ?
                """,
                    (tenant_id, threshold_date),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_actions,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_actions,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_actions,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_actions,
                        AVG(CASE WHEN executed_at IS NOT NULL AND completed_at IS NOT NULL
                                 THEN (julianday(completed_at) - julianday(executed_at)) * 86400 END) as avg_resolution_time
                    FROM remediation_actions
                    WHERE created_at >= ?
                """,
                    (threshold_date,),
                )

            row = cursor.fetchone()
            total = row[0] or 0
            successful = row[1] or 0

            return {
                "total_actions": total,
                "successful_actions": successful,
                "failed_actions": row[2] or 0,
                "pending_actions": row[3] or 0,
                "success_rate": (successful / total * 100) if total > 0 else 0.0,
                "avg_resolution_time_seconds": row[4] or 0.0,
                "period_days": days,
            }
