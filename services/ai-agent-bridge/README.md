# 🤖 AetherLink AI Agent Bridge

Lightweight HTTP server that exposes Command Center data in AI-friendly format. Your AI assistant (Claude, GPT, etc.) can query this to get real-time operator insights about the AetherLink platform.

## Features

- ✅ **AI-Optimized Format** - Returns data structured for LLM consumption
- ✅ **Actionable Recommendations** - Includes suggestions based on current state
- ✅ **Smart Filtering** - Only shows problematic items that need attention
- ✅ **CORS Enabled** - Works with browser-based agents
- ✅ **Zero Dependencies** - Uses Node.js built-in modules only

## Quick Start

```bash
# Start the bridge (from AetherLink root)
cd services/ai-agent-bridge
node server.js

# Or with custom port
AI_BRIDGE_PORT=3002 node server.js

# Or with custom Command Center URL
COMMAND_CENTER_API=http://command-center:8010 node server.js
```

The bridge will start on `http://localhost:3001` by default.

## API Endpoints

### `GET /health`
Bridge health check.

**Response:**
```json
{
  "status": "ok",
  "service": "ai-agent-bridge"
}
```

### `GET /ops/snapshot` ⭐
**Main endpoint** - Returns comprehensive ops state optimized for AI agents.

**Response:**
```json
{
  "timestamp": "2025-11-06T04:15:00.000Z",
  "health": "healthy",
  "anomalies": {
    "total": 2,
    "critical": 1,
    "warnings": 1,
    "incidents": [
      {
        "type": "spike",
        "severity": "critical",
        "metric_name": "error_rate",
        "baseline_value": 5,
        "current_value": 25,
        "delta_percent": 400,
        "message": "Error rate spike detected: 400% above baseline"
      }
    ]
  },
  "deliveries": {
    "total": 20,
    "problematic": 3,
    "failed": 2,
    "pending": 1,
    "dead_letter": 0,
    "items": [
      {
        "id": "abc-123",
        "status": "failed",
        "rule_name": "Alert Delivery Failures",
        "event_type": "ops.alert.delivery.failed",
        "tenant_id": "tenant-qa",
        "attempts": 3,
        "max_attempts": 5,
        "last_error": "HTTP 503: Service Unavailable from Slack"
      }
    ]
  },
  "recommendations": [
    {
      "priority": "high",
      "category": "anomaly",
      "message": "1 critical anomalies detected. Investigate immediately.",
      "action": "Review /anomalies/current endpoint for details"
    },
    {
      "priority": "medium",
      "category": "delivery",
      "message": "2 failed deliveries found. Consider replaying.",
      "action": "Use POST /alerts/deliveries/{id}/replay to retry"
    }
  ]
}
```

### `GET /ops/anomalies`
Returns current anomalies only (raw Command Center format).

### `GET /ops/deliveries?limit=20`
Returns recent delivery history (raw Command Center format).

### `POST /ops/replay/:deliveryId`
Replay a failed/pending delivery. Proxies to Command Center with admin role.

**Example:**
```bash
curl -X POST http://localhost:3001/ops/replay/abc-123
```

## Integration Examples

### Claude Code / VS Code Extension

```javascript
// In your extension or agent code
async function checkAetherLinkOps() {
  const res = await fetch('http://localhost:3001/ops/snapshot');
  const data = await res.json();

  if (data.anomalies.critical > 0) {
    console.log('⚠️ Critical anomalies detected:', data.anomalies.incidents);
  }

  if (data.deliveries.failed > 0) {
    console.log('📮 Failed deliveries:', data.deliveries.items);
  }

  return data.recommendations;
}
```

### AI Agent Prompt

```
You are an AetherLink operator assistant. Before answering, check the ops state:

1. Fetch http://localhost:3001/ops/snapshot
2. If anomalies.critical > 0, mention them first
3. If deliveries.problematic > 0, suggest replay
4. Follow the recommendations array for guidance

Example response:
"✅ All systems healthy. 0 anomalies, 0 failed deliveries."

or:

"⚠️ 2 critical anomalies detected in the last 5 minutes. 3 deliveries failed due to 'HTTP 503: Service Unavailable'. Recommend replaying deliveries abc-123, def-456, ghi-789."
```

### Shell Script

```bash
#!/bin/bash
# Quick ops check
STATUS=$(curl -s http://localhost:3001/ops/snapshot | jq -r '.recommendations[0].message')
echo "Ops Status: $STATUS"
```

### Python Agent

```python
import requests

def check_ops():
    response = requests.get('http://localhost:3001/ops/snapshot')
    data = response.json()

    # Check for issues
    if data['anomalies']['critical'] > 0:
        print(f"🚨 {data['anomalies']['critical']} critical anomalies!")
        for incident in data['anomalies']['incidents']:
            print(f"  - {incident['message']}")

    if data['deliveries']['failed'] > 0:
        print(f"📮 {data['deliveries']['failed']} failed deliveries")
        for delivery in data['deliveries']['items']:
            if delivery['status'] == 'failed':
                print(f"  - {delivery['id']}: {delivery['last_error']}")

    # Show recommendations
    for rec in data['recommendations']:
        print(f"[{rec['priority'].upper()}] {rec['message']}")
        print(f"   Action: {rec['action']}")

if __name__ == '__main__':
    check_ops()
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_BRIDGE_PORT` | `3001` | Port the bridge listens on |
| `COMMAND_CENTER_API` | `http://localhost:8010` | Command Center base URL |

## Architecture

```
┌─────────────────┐
│   AI Agent      │
│  (Claude/GPT)   │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  AI Bridge      │  ← This service
│  :3001          │
└────────┬────────┘
         │ HTTP + X-User-Roles
         ▼
┌─────────────────┐
│ Command Center  │
│  :8010          │
└─────────────────┘
```

## Data Flow

1. **AI Agent** calls `/ops/snapshot`
2. **Bridge** fetches from Command Center:
   - `/health` (public)
   - `/anomalies/current` (admin role)
   - `/alerts/deliveries/history` (operator role)
3. **Bridge** filters & formats data:
   - Only shows problematic deliveries
   - Generates actionable recommendations
   - Adds human-readable summaries
4. **AI Agent** receives optimized JSON

## Production Deployment

### Docker Compose

Add to `docker-compose.yml`:

```yaml
ai-agent-bridge:
  build:
    context: ./services/ai-agent-bridge
  container_name: aether-ai-bridge
  environment:
    - COMMAND_CENTER_API=http://command-center:8010
    - AI_BRIDGE_PORT=3001
  ports:
    - "3001:3001"
  depends_on:
    - command-center
  restart: unless-stopped
```

### Dockerfile

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json server.js ./
EXPOSE 3001
CMD ["node", "server.js"]
```

### Kubernetes

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ai-agent-bridge
spec:
  selector:
    app: ai-agent-bridge
  ports:
    - port: 3001
      targetPort: 3001
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-agent-bridge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-agent-bridge
  template:
    metadata:
      labels:
        app: ai-agent-bridge
    spec:
      containers:
      - name: bridge
        image: aetherlink/ai-agent-bridge:latest
        ports:
        - containerPort: 3001
        env:
        - name: COMMAND_CENTER_API
          value: "http://command-center:8010"
```

## Security Notes

- **Development Mode**: CORS is enabled (`*`) for easy testing
- **Production**: Restrict CORS to your agent's origin
- **Auth**: Bridge uses admin/operator roles internally - ensure Command Center is secured
- **Network**: Run on internal network only; do not expose publicly

## Troubleshooting

### Bridge won't start
```bash
# Check if port 3001 is available
lsof -i :3001

# Try a different port
AI_BRIDGE_PORT=3002 node server.js
```

### "Failed to fetch" errors
```bash
# Verify Command Center is running
curl http://localhost:8010/health

# Check COMMAND_CENTER_API env var
echo $COMMAND_CENTER_API
```

### Empty snapshot
```bash
# Verify Command Center has data
curl -H "X-User-Roles: admin" http://localhost:8010/anomalies/current
curl -H "X-User-Roles: operator" http://localhost:8010/alerts/deliveries/history
```

## License

MIT - Part of the AetherLink platform
