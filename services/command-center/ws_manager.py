"""
WebSocket connection managers for Command Center live updates.

Supports multiple channels:
- Remediation events (alerts being auto-healed)
- Operator activity (audit trail of operator actions)

Phase XX M8: Added Prometheus metrics for timeline WS event observability
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket
from prometheus_client import Counter

# Prometheus metric for timeline WS events
timeline_ws_events_total = Counter(
    "aetherlink_timeline_ws_events_total",
    "Total WebSocket timeline events broadcast",
    ["tenant"],
)


class BaseWSManager:
    """Base WebSocket connection manager with broadcast capability."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all active connections, removing stale ones."""
        to_remove: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)


# Global manager instances
remediation_ws_manager = BaseWSManager()
operator_activity_ws_manager = BaseWSManager()
