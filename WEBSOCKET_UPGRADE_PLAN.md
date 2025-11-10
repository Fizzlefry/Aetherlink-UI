# WebSocket Upgrade for Real-Time Remediation Updates

## Current State
- Component polls `/ops/remediate/history` every 15 seconds
- Up to 15-second delay before new events appear
- Works reliably but not instant

## Proposed Enhancement
Replace HTTP polling with WebSocket push for instant updates when remediation events occur.

## Architecture

### Backend Changes

#### 1. Add WebSocket Support to FastAPI
```python
# services/command-center/main.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import asyncio

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast to all connected clients"""
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection)

ws_manager = ConnectionManager()

@app.websocket("/ws/remediation")
async def remediation_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time remediation updates"""
    await ws_manager.connect(websocket)
    try:
        # Keep connection alive and handle pings
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

#### 2. Broadcast on Event Creation
```python
# Modify record_remediation_event() to broadcast

def record_remediation_event(
    alertname: str,
    tenant: str,
    action: str,
    status: str,
    details: str = "",
) -> None:
    """Record a remediation event to SQLite and broadcast via WebSocket."""
    RECOVERY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RECOVERY_DB)
    try:
        cur = conn.cursor()
        cur.execute("""
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
        ts = datetime.utcnow().isoformat() + "Z"
        cur.execute("""
            INSERT INTO remediation_events (ts, alertname, tenant, action, status, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, alertname, tenant, action, status, details[:500]))
        conn.commit()

        # Get the inserted ID
        event_id = cur.lastrowid

        # Broadcast to WebSocket clients
        event_data = {
            "type": "remediation_event",
            "event": {
                "id": event_id,
                "ts": ts,
                "alertname": alertname,
                "tenant": tenant,
                "action": action,
                "status": status,
                "details": details[:500]
            }
        }

        # Schedule broadcast (non-blocking)
        asyncio.create_task(ws_manager.broadcast(event_data))

    finally:
        conn.close()
```

### Frontend Changes

#### 1. WebSocket Hook
```typescript
// services/ui/src/hooks/useRemediationWebSocket.ts

import { useEffect, useRef, useState } from 'react';

type RemediationEvent = {
    id: number;
    ts: string;
    alertname: string;
    tenant: string;
    action: string;
    status: string;
    details: string;
};

type WebSocketMessage = {
    type: string;
    event: RemediationEvent;
};

export const useRemediationWebSocket = (url: string) => {
    const [lastEvent, setLastEvent] = useState<RemediationEvent | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<number>();

    useEffect(() => {
        const connect = () => {
            try {
                const ws = new WebSocket(url);
                wsRef.current = ws;

                ws.onopen = () => {
                    console.log('[WS] Connected to remediation stream');
                    setIsConnected(true);

                    // Start heartbeat
                    const heartbeat = setInterval(() => {
                        if (ws.readyState === WebSocket.OPEN) {
                            ws.send('ping');
                        }
                    }, 30000); // ping every 30s

                    ws.addEventListener('close', () => {
                        clearInterval(heartbeat);
                    });
                };

                ws.onmessage = (event) => {
                    if (event.data === 'pong') return; // heartbeat response

                    try {
                        const message: WebSocketMessage = JSON.parse(event.data);
                        if (message.type === 'remediation_event') {
                            console.log('[WS] New remediation event:', message.event);
                            setLastEvent(message.event);
                        }
                    } catch (err) {
                        console.error('[WS] Failed to parse message:', err);
                    }
                };

                ws.onerror = (error) => {
                    console.error('[WS] Error:', error);
                };

                ws.onclose = () => {
                    console.log('[WS] Disconnected, reconnecting in 5s...');
                    setIsConnected(false);

                    // Auto-reconnect after 5 seconds
                    reconnectTimeoutRef.current = window.setTimeout(() => {
                        connect();
                    }, 5000);
                };

            } catch (err) {
                console.error('[WS] Connection failed:', err);
                // Retry connection
                reconnectTimeoutRef.current = window.setTimeout(() => {
                    connect();
                }, 5000);
            }
        };

        connect();

        // Cleanup on unmount
        return () => {
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [url]);

    return { lastEvent, isConnected };
};
```

#### 2. Update Component to Use WebSocket
```typescript
// services/ui/src/components/RecentRemediations.tsx

import React, { useEffect, useState } from "react";
import { useRemediationWebSocket } from "../hooks/useRemediationWebSocket";

export const RecentRemediations: React.FC<RecentRemediationsProps> = ({ userRoles }) => {
    const [data, setData] = useState<RemediationHistory | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // WebSocket for real-time updates
    const { lastEvent, isConnected } = useRemediationWebSocket("ws://localhost:8010/ws/remediation");

    // Initial fetch
    const fetchHistory = async () => {
        try {
            const res = await fetch("http://localhost:8010/ops/remediate/history?limit=10", {
                headers: { "X-User-Roles": userRoles }
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (err) {
            console.error("Failed to load remediation history", err);
            setError(err instanceof Error ? err.message : "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    // Load initial data
    useEffect(() => {
        fetchHistory();
    }, [userRoles]);

    // Handle new events from WebSocket
    useEffect(() => {
        if (lastEvent && data) {
            // Prepend new event to list
            const newItems = [lastEvent, ...data.items].slice(0, 10); // keep last 10
            setData({
                items: newItems,
                total: data.total + 1
            });
        }
    }, [lastEvent]);

    // Fallback polling if WebSocket disconnected (every 30s instead of 15s)
    useEffect(() => {
        if (!isConnected) {
            const interval = setInterval(fetchHistory, 30000);
            return () => clearInterval(interval);
        }
    }, [isConnected, userRoles]);

    // ... rest of component (render logic stays the same)

    // Add connection status indicator
    return (
        <div style={{ marginTop: "3rem" }}>
            <div style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <h2 style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#111827" }}>
                    🔄 Recent Remediations
                </h2>
                {/* Connection indicator */}
                <span style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: isConnected ? "#10b981" : "#9ca3af",
                    display: "inline-block"
                }} title={isConnected ? "Live updates active" : "Using polling"} />
            </div>
            {/* ... rest of render */}
        </div>
    );
};
```

## Benefits

### Instant Updates
- **Before:** Up to 15 seconds delay
- **After:** <100ms from event creation to UI update

### Reduced Server Load
- **Before:** HTTP request every 15s per client (4 req/min)
- **After:** Single persistent WebSocket connection + fallback polling (2 req/min)

### Better UX
- **Live indicator** shows connection status
- **Smooth animations** possible (fade-in new events)
- **Network efficient** (only sends data when events occur)

## Implementation Steps

### Phase 1: Backend (30 minutes)
1. Add `ConnectionManager` class to main.py
2. Create `/ws/remediation` WebSocket endpoint
3. Modify `record_remediation_event()` to broadcast
4. Test with WebSocket client (wscat or browser DevTools)

### Phase 2: Frontend (30 minutes)
1. Create `useRemediationWebSocket.ts` hook
2. Update `RecentRemediations.tsx` to use hook
3. Add connection status indicator
4. Test reconnection logic

### Phase 3: Testing (15 minutes)
1. Verify instant updates work
2. Test reconnection after server restart
3. Test fallback to polling if WebSocket unavailable
4. Test with multiple browser tabs

### Phase 4: Polish (15 minutes)
1. Add fade-in animation for new events
2. Add visual notification flash
3. Optional: Add sound/desktop notification

## Testing WebSocket

### Manual Test with DevTools
```javascript
// Browser console
const ws = new WebSocket('ws://localhost:8010/ws/remediation');
ws.onmessage = (e) => console.log('Received:', JSON.parse(e.data));
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error:', e);
```

### Trigger Test Event
```bash
# Add test remediation event
python -c "
from services.command_center.main import record_remediation_event
record_remediation_event('TestAlert', 'test-tenant', 'auto_ack', 'success', 'WebSocket test')
"
```

### Expected Result
Browser console shows:
```
Connected
Received: {
  "type": "remediation_event",
  "event": {
    "id": 103,
    "ts": "2025-11-09T20:15:42.123456Z",
    "alertname": "TestAlert",
    "tenant": "test-tenant",
    "action": "auto_ack",
    "status": "success",
    "details": "WebSocket test"
  }
}
```

## Fallback Strategy

WebSocket connection can fail for various reasons:
- Firewall blocks WebSocket
- Proxy doesn't support WebSocket
- Network issues

**Solution:** Hybrid approach
1. Try WebSocket first
2. If disconnected, fall back to HTTP polling (30s interval)
3. Show connection status indicator
4. Auto-reconnect when possible

## Security Considerations

### Authentication
Add WebSocket authentication:
```python
@app.websocket("/ws/remediation")
async def remediation_websocket(
    websocket: WebSocket,
    token: str = Query(...)
):
    # Verify token
    user = verify_token(token)
    if not user:
        await websocket.close(code=1008)  # Policy Violation
        return

    await ws_manager.connect(websocket, user)
    # ...
```

### Rate Limiting
Limit connections per IP:
```python
connection_counts: dict[str, int] = {}
MAX_CONNECTIONS_PER_IP = 5

async def connect(self, websocket: WebSocket, client_ip: str):
    if connection_counts.get(client_ip, 0) >= MAX_CONNECTIONS_PER_IP:
        await websocket.close(code=1008)
        return
    # ...
```

## Migration Path

### Week 1: Add WebSocket (Non-Breaking)
- Deploy backend with WebSocket endpoint
- Keep existing HTTP polling in UI
- Verify WebSocket works in production

### Week 2: Enable Hybrid Mode
- Update UI to use WebSocket + fallback
- Monitor connection success rate
- Keep both endpoints active

### Week 3: Production
- Enable for all users
- Monitor metrics
- Keep HTTP endpoint as backup

## Metrics to Track

### Backend
- `ws_connections_active` - Current WebSocket connections
- `ws_messages_sent_total` - Total broadcasts
- `ws_connection_errors_total` - Connection failures

### Frontend
- WebSocket connection success rate
- Average time to first event
- Fallback polling frequency

## Alternative: Server-Sent Events (SSE)

If WebSocket is too complex, consider SSE:
```python
@app.get("/sse/remediation")
async def remediation_sse(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            # Wait for new events
            event = await event_queue.get()
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

**Pros:** Simpler, auto-reconnects, HTTP-friendly
**Cons:** One-way only (server → client)

## Recommendation

**Start with WebSocket** for full duplex capability, but include SSE fallback if issues arise.

**Implementation order:**
1. Backend WebSocket endpoint (30 min)
2. Frontend hook (30 min)
3. Integration + testing (30 min)
4. Polish + monitoring (30 min)

**Total effort:** ~2 hours for production-ready instant updates

---

**Status:** 📋 Design Complete, Ready for Implementation
**Impact:** High (instant updates vs 15s delay)
**Complexity:** Medium (well-documented WebSocket patterns)
**Risk:** Low (graceful fallback to polling)
