from __future__ import annotations

from typing import Any


class Store:
    def load_schedules(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    def save_schedule(self, tenant: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete_schedule(self, tenant: str) -> None:
        raise NotImplementedError

    def list_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        raise NotImplementedError

    def append_audit(self, record: dict[str, Any]) -> None:
        raise NotImplementedError

    def list_local_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        raise NotImplementedError

    def append_local_run(self, record: dict[str, Any]) -> None:
        raise NotImplementedError
