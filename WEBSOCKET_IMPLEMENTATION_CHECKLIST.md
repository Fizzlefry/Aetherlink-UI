# WebSocket Implementation Checklist

## Quick Reference
Transform polling (15s delay) → instant push updates (~100ms)

## Step-by-Step Implementation

### 🔧 Backend Changes (30 min)

#### 1. Add Connection Manager
**File:** `services/command-center/main.py`

Add after imports:
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for connection in dead_connections:
            self.disconnect(connection)

ws_manager = ConnectionManager()
```

**✓ Checkpoint:** No errors when restarting server

#### 2. Add WebSocket Endpoint
Add after existing routes:
```python
@app.websocket("/ws/remediation")
async def remediation_websocket(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

**✓ Checkpoint:** Test with browser DevTools
```javascript
const ws = new WebSocket('ws://localhost:8010/ws/remediation');
ws.onopen = () => console.log('Connected!');
```

#### 3. Modify Event Writer to Broadcast
Update `record_remediation_event()`:
```python
def record_remediation_event(...):
    # ... existing SQLite write code ...

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
```

**✓ Checkpoint:** Generate test event, see broadcast in browser console

---

### 🎨 Frontend Changes (30 min)

#### 4. Create WebSocket Hook
**File:** `services/ui/src/hooks/useRemediationWebSocket.ts`

```typescript
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
                    setIsConnected(true);
                    const heartbeat = setInterval(() => {
                        if (ws.readyState === WebSocket.OPEN) {
                            ws.send('ping');
                        }
                    }, 30000);
                    ws.addEventListener('close', () => clearInterval(heartbeat));
                };

                ws.onmessage = (event) => {
                    if (event.data === 'pong') return;
                    try {
                        const message: WebSocketMessage = JSON.parse(event.data);
                        if (message.type === 'remediation_event') {
                            setLastEvent(message.event);
                        }
                    } catch (err) {
                        console.error('[WS] Parse error:', err);
                    }
                };

                ws.onclose = () => {
                    setIsConnected(false);
                    reconnectTimeoutRef.current = window.setTimeout(connect, 5000);
                };

            } catch (err) {
                reconnectTimeoutRef.current = window.setTimeout(connect, 5000);
            }
        };

        connect();

        return () => {
            if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
            if (wsRef.current) wsRef.current.close();
        };
    }, [url]);

    return { lastEvent, isConnected };
};
```

**✓ Checkpoint:** No TypeScript errors

#### 5. Update Component
**File:** `services/ui/src/components/RecentRemediations.tsx`

Add at top:
```typescript
import { useRemediationWebSocket } from "../hooks/useRemediationWebSocket";
```

Add in component:
```typescript
const { lastEvent, isConnected } = useRemediationWebSocket("ws://localhost:8010/ws/remediation");

// Handle new events from WebSocket
useEffect(() => {
    if (lastEvent && data) {
        const newItems = [lastEvent, ...data.items].slice(0, 10);
        setData({
            items: newItems,
            total: data.total + 1
        });
    }
}, [lastEvent]);

// Fallback polling only if disconnected
useEffect(() => {
    if (!isConnected) {
        const interval = setInterval(fetchHistory, 30000);
        return () => clearInterval(interval);
    }
}, [isConnected, userRoles]);
```

Add connection indicator in header:
```typescript
<div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
    <h2>🔄 Recent Remediations</h2>
    <span style={{
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: isConnected ? "#10b981" : "#9ca3af"
    }} title={isConnected ? "Live" : "Polling"} />
</div>
```

**✓ Checkpoint:** Green dot appears when connected

---

### 🧪 Testing (15 min)

#### 6. Test Instant Updates
```bash
# Terminal 1: Command Center
python services/command-center/main.py

# Terminal 2: UI
cd services/ui && npm run dev

# Terminal 3: Generate event
python -c "
from services.command_center.main import record_remediation_event
record_remediation_event('LiveTest', 'test', 'auto_ack', 'success', 'WebSocket works!')
"
```

**✓ Expected:** Event appears in UI within 100ms

#### 7. Test Reconnection
1. Stop Command Center
2. Wait 5 seconds
3. **✓ Expected:** Dot turns gray, falls back to polling
4. Restart Command Center
5. **✓ Expected:** Reconnects automatically, dot turns green

#### 8. Test Multiple Tabs
1. Open Command Center in 3 browser tabs
2. Generate test event
3. **✓ Expected:** All tabs update instantly

---

### ✨ Polish (Optional, 15 min)

#### 9. Add Fade-In Animation
```typescript
const [newEventId, setNewEventId] = useState<number | null>(null);

useEffect(() => {
    if (lastEvent && data) {
        setNewEventId(lastEvent.id);
        setTimeout(() => setNewEventId(null), 2000); // clear after 2s
        // ... prepend logic
    }
}, [lastEvent]);

// In render
<div
    key={event.id}
    style={{
        ...existingStyles,
        animation: event.id === newEventId ? "fadeIn 0.5s ease-in" : undefined
    }}
>
```

Add CSS:
```typescript
<style>{`
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
`}</style>
```

#### 10. Add Flash Notification
```typescript
useEffect(() => {
    if (lastEvent && document.hidden) {
        // Show desktop notification if tab not active
        if (Notification.permission === "granted") {
            new Notification("New Remediation", {
                body: `${lastEvent.alertname} - ${lastEvent.action}`,
                icon: "/favicon.ico"
            });
        }
    }
}, [lastEvent]);
```

---

## Quick Commands

### Start Everything
```bash
# Terminal 1
cd services/command-center && python main.py

# Terminal 2
cd services/ui && npm run dev

# Terminal 3 (for testing)
python generate_test_recovery_events.py 1
```

### Test WebSocket Connection
```javascript
// Browser DevTools Console
const ws = new WebSocket('ws://localhost:8010/ws/remediation');
ws.onopen = () => console.log('✓ Connected');
ws.onmessage = (e) => console.log('📨', JSON.parse(e.data));
ws.onerror = (e) => console.error('❌', e);
```

### Monitor Backend
```bash
# Watch logs for WebSocket connections
tail -f services/command-center/logs/app.log | grep -i websocket
```

---

## Troubleshooting

### WebSocket won't connect
**Check:**
- Command Center running on port 8010
- No firewall blocking WebSocket
- Browser DevTools Network tab shows WS connection

**Fix:**
```bash
# Test endpoint directly
curl --include \
     --no-buffer \
     --header "Connection: Upgrade" \
     --header "Upgrade: websocket" \
     --header "Sec-WebSocket-Version: 13" \
     --header "Sec-WebSocket-Key: test" \
     http://localhost:8010/ws/remediation
```

### Events not broadcasting
**Check:**
- `ws_manager.broadcast()` is being called
- No errors in server console
- Active connections exist

**Debug:**
```python
# Add logging to broadcast()
async def broadcast(self, message: dict):
    print(f"Broadcasting to {len(self.active_connections)} clients")
    # ... rest of code
```

### UI not updating
**Check:**
- `lastEvent` dependency in useEffect
- No console errors
- Event data structure matches type

**Debug:**
```typescript
useEffect(() => {
    console.log('New event received:', lastEvent);
    // ... rest of code
}, [lastEvent]);
```

---

## Success Criteria

- [x] Backend WebSocket endpoint responds
- [x] Frontend connects automatically
- [x] New events appear within 100ms
- [x] Reconnects after disconnect
- [x] Falls back to polling if WebSocket unavailable
- [x] Green dot shows live status
- [x] No errors in console
- [x] Works across multiple tabs

---

## Rollback Plan

If issues arise:

1. **Comment out WebSocket code in component:**
   ```typescript
   // const { lastEvent, isConnected } = useRemediationWebSocket(...);
   ```

2. **Re-enable old polling:**
   ```typescript
   useEffect(() => {
       fetchHistory();
       const interval = setInterval(fetchHistory, 15000);
       return () => clearInterval(interval);
   }, [userRoles]);
   ```

3. **System back to original polling behavior**

---

**Total Time:** ~90 minutes
**Complexity:** Medium
**Impact:** High (instant updates!)
**Risk:** Low (graceful fallback)

Ready to implement? Start with **Step 1** and work through each checkpoint! ✨
