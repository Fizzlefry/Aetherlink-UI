"""
Persistence Layer Base Interface

Phase XVII-B: Abstract persistence interface for data storage.
Supports both JSON (current) and SQLite (future) backends.
"""

from abc import ABC, abstractmethod
from typing import Any


class PersistenceBackend(ABC):
    """Abstract base class for persistence backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the persistence backend."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the persistence backend."""
        pass

    @abstractmethod
    async def save_schedules(self, schedules: dict[str, Any]) -> None:
        """Save tenant import schedules."""
        pass

    @abstractmethod
    async def load_schedules(self) -> dict[str, Any]:
        """Load tenant import schedules."""
        pass

    @abstractmethod
    async def save_audit_entries(self, entries: list[dict[str, Any]]) -> None:
        """Save audit log entries."""
        pass

    @abstractmethod
    async def load_audit_entries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load audit log entries, optionally limited."""
        pass

    @abstractmethod
    async def save_local_action_runs(self, runs: list[dict[str, Any]]) -> None:
        """Save local action execution runs."""
        pass

    @abstractmethod
    async def load_local_action_runs(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Load local action execution runs, optionally limited."""
        pass

    @abstractmethod
    async def save_import_record(self, tenant: str, import_data: dict[str, Any]) -> None:
        """Save a completed import record."""
        pass

    @abstractmethod
    async def get_import_history(self, tenant: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get import history for a tenant."""
        pass

    @abstractmethod
    async def save_event(self, event: dict[str, Any]) -> None:
        """Save an event record."""
        pass

    @abstractmethod
    async def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events."""
        pass

    @abstractmethod
    async def save_alert(self, alert: dict[str, Any]) -> None:
        """Save an alert record."""
        pass

    @abstractmethod
    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get currently active alerts."""
        pass

    @abstractmethod
    async def update_tenant_config(self, tenant: str, config: dict[str, Any]) -> None:
        """Update tenant configuration."""
        pass

    @abstractmethod
    async def get_tenant_config(self, tenant: str) -> dict[str, Any] | None:
        """Get tenant configuration."""
        pass

    @abstractmethod
    async def get_all_tenant_configs(self) -> dict[str, Any]:
        """Get all tenant configurations."""
        pass
