"""
WebSocket connection managers for Command Center live updates.

Supports multiple channels:
- Remediation events (alerts being auto-healed)
- Operator activity (audit trail of operator actions)

Phase XX M8: Added Prometheus metrics for timeline WS event observability
Phase XX M9: Added heartbeat tracking and stale connection detection
"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import WebSocket
from prometheus_client import Counter, Gauge

# Prometheus metric for timeline WS events
timeline_ws_events_total = Counter(
    "aetherlink_timeline_ws_events_total",
    "Total WebSocket timeline events broadcast",
    ["tenant"],
)

# Phase XX M9: Heartbeat and stale connection metrics
timeline_ws_heartbeat_total = Counter(
    "aetherlink_timeline_ws_heartbeat_total",
    "Total timeline WebSocket heartbeat pings observed",
    ["tenant"],
)

timeline_ws_stale_connections = Gauge(
    "aetherlink_timeline_ws_stale_connections",
    "Number of timeline WebSocket connections considered stale",
    ["tenant"],
)

# Phase XX M11: frontend telemetry events
frontend_timeline_events_total = Counter(
    "aetherlink_frontend_timeline_events_total",
    "Frontend-reported timeline UI events (stale, degraded, recovered)",
    ["tenant", "event", "component"],
)


class BaseWSManager:
    """Base WebSocket connection manager with broadcast capability.

    Phase XX M9: Added heartbeat tracking and stale connection detection.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        # Track last heartbeat timestamp per connection
        self.last_heartbeat: dict[WebSocket, float] = {}
        # Connections without heartbeat for this many seconds are considered stale
        self.stale_after_seconds: float = 35.0

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        # Initialize heartbeat timestamp
        self.last_heartbeat[websocket] = time.time()

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Clean up heartbeat tracking
        self.last_heartbeat.pop(websocket, None)

    def record_heartbeat(self, websocket: WebSocket, tenant: str = "unknown") -> None:
        """Record a heartbeat from a client connection.

        Args:
            websocket: The WebSocket connection that sent the heartbeat
            tenant: Tenant identifier for metrics (default: "unknown")
        """
        self.last_heartbeat[websocket] = time.time()
        timeline_ws_heartbeat_total.labels(tenant=tenant).inc()

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all active connections, removing stale ones.

        Phase XX M9: Also tracks stale connections (no heartbeat for 35+ seconds)
        and updates Prometheus gauge.
        """
        to_remove: list[WebSocket] = []
        now = time.time()
        stale_count = 0

        for ws in self.active_connections:
            try:
                # Check if connection is stale
                last_hb = self.last_heartbeat.get(ws, 0)
                if now - last_hb > self.stale_after_seconds:
                    stale_count += 1

                await ws.send_text(json.dumps(message))
            except Exception:
                to_remove.append(ws)

        # Update stale connections gauge
        timeline_ws_stale_connections.labels(tenant="all").set(stale_count)

        for ws in to_remove:
            self.disconnect(ws)


# Global manager instances
remediation_ws_manager = BaseWSManager()
operator_activity_ws_manager = BaseWSManager()
