"""
JSON Fallback Persistence Backend

Phase XVII-B: JSON file-based implementation for backward compatibility.
Used when SQLite is not available or during migration.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from .base import PersistenceBackend


def load_json_self_heal(file_path: Path, default: Any) -> Any:
    """Load JSON file with self-healing for corrupted files."""
    try:
        if not file_path.exists():
            return default
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to load {file_path}, using default: {e}")
        # Backup corrupted file
        if file_path.exists():
            backup_path = file_path.with_suffix(".bak")
            file_path.rename(backup_path)
            print(f"Backed up corrupted file to {backup_path}")
        return default


def save_json_atomic(file_path: Path, data: Any) -> None:
    """Save JSON file atomically to prevent corruption."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(".tmp")

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(file_path)  # Atomic move
    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise


class JSONBackend(PersistenceBackend):
    """JSON file-based persistence backend for backward compatibility."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.schedules_file = self.data_dir / "acculynx_schedules.json"
        self.audit_file = self.data_dir / "acculynx_audit.json"
        self.local_runs_file = self.data_dir / "local_action_runs.json"
        self.imports_file = self.data_dir / "import_history.json"
        self.events_file = self.data_dir / "events.json"
        self.alerts_file = self.data_dir / "alerts.json"
        self.tenants_file = self.data_dir / "tenants.json"

    async def initialize(self) -> None:
        """Initialize JSON backend - no-op since files are created on demand."""
        pass

    async def close(self) -> None:
        """Close JSON backend - no-op."""
        pass

    async def save_schedules(self, schedules: dict[str, Any]) -> None:
        """Save tenant import schedules."""
        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.schedules_file, schedules
        )

    async def load_schedules(self) -> dict[str, Any]:
        """Load tenant import schedules."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.schedules_file, {}
        )

    async def save_audit_entries(self, entries: list[dict[str, Any]]) -> None:
        """Save audit log entries."""
        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.audit_file, entries
        )

    async def load_audit_entries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load audit log entries."""
        entries = await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.audit_file, []
        )
        if limit:
            entries = entries[-limit:]  # Get most recent
        return entries

    async def save_local_action_runs(self, runs: list[dict[str, Any]]) -> None:
        """Save local action execution runs."""
        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.local_runs_file, runs
        )

    async def load_local_action_runs(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load local action execution runs."""
        runs = await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.local_runs_file, []
        )
        if limit:
            runs = runs[-limit:]  # Get most recent
        return runs

    async def save_import_record(self, tenant: str, import_data: dict[str, Any]) -> None:
        """Save a completed import record."""
        # Load existing imports
        imports = await self._load_imports()
        if tenant not in imports:
            imports[tenant] = []

        # Add new record
        imports[tenant].append(import_data)

        # Keep only last 100 per tenant
        imports[tenant] = imports[tenant][-100:]

        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.imports_file, imports
        )

    async def get_import_history(self, tenant: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get import history for a tenant."""
        imports = await self._load_imports()
        tenant_imports = imports.get(tenant, [])
        return tenant_imports[-limit:]  # Most recent first

    async def _load_imports(self) -> dict[str, list[dict[str, Any]]]:
        """Load import history."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.imports_file, {}
        )

    async def save_event(self, event: dict[str, Any]) -> None:
        """Save an event record."""
        events = await self._load_events()
        events.append(event)

        # Keep only last 1000 events
        events = events[-1000:]

        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.events_file, events
        )

    async def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events."""
        events = await self._load_events()
        return events[-limit:]  # Most recent

    async def _load_events(self) -> list[dict[str, Any]]:
        """Load events."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.events_file, []
        )

    async def save_alert(self, alert: dict[str, Any]) -> None:
        """Save an alert record."""
        alerts = await self._load_alerts()
        alerts.append(alert)

        # Keep only last 500 alerts
        alerts = alerts[-500:]

        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.alerts_file, alerts
        )

    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get currently active alerts."""
        alerts = await self._load_alerts()
        return [alert for alert in alerts if alert.get("resolved_at") is None]

    async def _load_alerts(self) -> list[dict[str, Any]]:
        """Load alerts."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.alerts_file, []
        )

    async def update_tenant_config(self, tenant: str, config: dict[str, Any]) -> None:
        """Update tenant configuration."""
        tenants = await self._load_tenants()
        tenants[tenant] = config
        await asyncio.get_event_loop().run_in_executor(
            None, save_json_atomic, self.tenants_file, tenants
        )

    async def get_tenant_config(self, tenant: str) -> dict[str, Any] | None:
        """Get tenant configuration."""
        tenants = await self._load_tenants()
        return tenants.get(tenant)

    async def get_all_tenant_configs(self) -> dict[str, Any]:
        """Get all tenant configurations."""
        return await self._load_tenants()

    async def _load_tenants(self) -> dict[str, Any]:
        """Load tenant configurations."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_json_self_heal, self.tenants_file, {}
        )
