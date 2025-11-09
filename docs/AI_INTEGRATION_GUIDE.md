# 🤖 AetherLink AI Integration Guide

Complete guide for integrating AetherLink operator data with AI assistants.

## Overview

AetherLink provides three layers of AI integration:

1. **Command Center API** (port 8010) - Raw backend data with RBAC
2. **AI Agent Bridge** (port 3001) - AI-friendly HTTP API with filtering and recommendations
3. **MCP Server** (stdio) - Model Context Protocol tools for AI assistants

```
┌─────────────────────────────────────────────────────────┐
│                  AI Assistant Layer                     │
│  (Claude Desktop, GPT, Custom Agents)                   │
└────────────┬───────────────────────┬────────────────────┘
             │                       │
             │ MCP (stdio)           │ HTTP
             │                       │
┌────────────▼────────┐   ┌──────────▼─────────┐
│   MCP Server        │   │  Direct HTTP       │
│   (stdio)           │   │  Integration       │
└────────────┬────────┘   └──────────┬─────────┘
             │                       │
             └───────────┬───────────┘
                         │ HTTP
              ┌──────────▼──────────┐
              │  AI Agent Bridge    │
              │  :3001              │
              └──────────┬──────────┘
                         │ HTTP + RBAC headers
              ┌──────────▼──────────┐
              │  Command Center     │
              │  :8010              │
              └─────────────────────┘
```

## Quick Start

### 1. Start the Services

```bash
# Terminal 1: Command Center
cd services/command-center
python -m uvicorn main:app --host 0.0.0.0 --port 8010

# Terminal 2: AI Agent Bridge
cd services/ai-agent-bridge
node server.js

# Terminal 3 (optional): MCP Server for Claude Desktop
cd services/mcp-server
# Configure in Claude Desktop instead of running manually
```

### 2. Verify Stack

```bash
# Check Command Center
curl http://localhost:8010/health
# → {"status":"healthy"}

# Check AI Agent Bridge
curl http://localhost:3001/health
# → {"status":"ok","service":"ai-agent-bridge"}

# Check ops snapshot
curl http://localhost:3001/ops/snapshot
# → { "timestamp": "...", "anomalies": {...}, "deliveries": {...} }
```

## Integration Options

### Option 1: MCP Server (Recommended for Claude Desktop)

Best for: Interactive conversations with Claude Desktop

**Setup:**

1. Edit your Claude Desktop config:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%/Claude/claude_desktop_config.json`

2. Add the MCP server:

```json
{
  "mcpServers": {
    "aetherlink": {
      "command": "node",
      "args": [
        "c:\\Users\\jonmi\\OneDrive\\Documents\\AetherLink\\services\\mcp-server\\server.js"
      ],
      "env": {
        "AI_BRIDGE_URL": "http://localhost:3001"
      }
    }
  }
}
```

3. Restart Claude Desktop

**Available Tools:**
- `aetherlink.get_ops_snapshot` - Full ops state with recommendations
- `aetherlink.get_anomalies` - Current anomalies only
- `aetherlink.get_deliveries` - Recent delivery history
- `aetherlink.replay_delivery` - Replay a failed/pending delivery by ID

**Example Conversation:**

```
User: What's the current AetherLink ops status?

Claude: [Uses aetherlink.get_ops_snapshot]

Claude: ✅ All systems healthy. No critical anomalies detected.
However, there are 2 failed deliveries that might need attention:
- Alert Delivery Failures (tenant-qa): HTTP 503 from Slack
- Alert Delivery Failures (tenant-qa): Max attempts reached

I recommend replaying the first delivery or investigating the Slack
webhook endpoint.

User: Go ahead and replay the first one

Claude: [Uses aetherlink.replay_delivery with delivery_id]

Claude: ✅ Delivery 4a142c00-aa0e-43cb-aac7-f85bf5aef14f has been
queued for replay. It will be retried shortly with exponential backoff.
```

### Option 2: Direct HTTP (Recommended for Custom Agents)

Best for: Custom automation, scheduled checks, integration with other tools

**Node.js Example:**

```javascript
// example-integration.js
async function checkOps() {
  const res = await fetch('http://localhost:3001/ops/snapshot');
  const data = await res.json();

  if (data.anomalies.critical > 0) {
    console.log('🚨 CRITICAL ALERT');
    data.anomalies.incidents
      .filter(i => i.severity === 'critical')
      .forEach(incident => {
        console.log(`- ${incident.message}`);
        console.log(`  Affected: ${incident.affected_tenant || 'system'}`);
      });
  }

  if (data.deliveries.failed > 0) {
    console.log(`⚠️  ${data.deliveries.failed} failed deliveries`);
  }

  data.recommendations.forEach(rec => {
    console.log(`[${rec.priority}] ${rec.message}`);
    console.log(`→ ${rec.action}`);
  });
}

// Run every 5 minutes
setInterval(checkOps, 5 * 60 * 1000);
```

**Python Example:**

```python
# ops_monitor.py
import requests
import time

def check_ops():
    response = requests.get('http://localhost:3001/ops/snapshot')
    data = response.json()

    # Check for critical anomalies
    if data['anomalies']['critical'] > 0:
        print('🚨 CRITICAL ALERT')
        for incident in data['anomalies']['incidents']:
            if incident['severity'] == 'critical':
                print(f"- {incident['message']}")
                print(f"  Tenant: {incident.get('affected_tenant', 'N/A')}")

    # Check for failed deliveries
    if data['deliveries']['failed'] > 0:
        print(f"⚠️  {data['deliveries']['failed']} failed deliveries")
        for delivery in data['deliveries']['items']:
            if delivery['status'] == 'failed':
                print(f"- {delivery['rule_name']}: {delivery['last_error']}")

    # Show recommendations
    for rec in data['recommendations']:
        print(f"[{rec['priority'].upper()}] {rec['message']}")
        print(f"→ {rec['action']}")

# Run every 5 minutes
while True:
    check_ops()
    time.sleep(300)
```

**Shell Script Example:**

```bash
#!/bin/bash
# ops-check.sh

# Get ops snapshot
SNAPSHOT=$(curl -s http://localhost:3001/ops/snapshot)

# Extract key metrics
CRITICAL=$(echo $SNAPSHOT | jq -r '.anomalies.critical')
FAILED=$(echo $SNAPSHOT | jq -r '.deliveries.failed')
HEALTH=$(echo $SNAPSHOT | jq -r '.health')

echo "Health: $HEALTH"
echo "Critical Anomalies: $CRITICAL"
echo "Failed Deliveries: $FAILED"

# Alert if critical
if [ "$CRITICAL" -gt 0 ]; then
  echo "🚨 CRITICAL ALERT - Check anomalies!"
  echo $SNAPSHOT | jq '.anomalies.incidents[] | select(.severity=="critical")'
fi
```

### Option 3: Direct Command Center API

Best for: When you need raw data without filtering

**Requires RBAC Headers:**

```bash
# Health check (no auth required)
curl http://localhost:8010/health

# Anomalies (requires admin role)
curl -H "X-User-Roles: admin" http://localhost:8010/anomalies/current

# Deliveries (requires operator role)
curl -H "X-User-Roles: operator" http://localhost:8010/alerts/deliveries/history?limit=20

# Replay delivery (requires admin role)
curl -X POST -H "X-User-Roles: admin" \
  http://localhost:8010/alerts/deliveries/{id}/replay
```

## API Reference

### AI Agent Bridge Endpoints

#### `GET /health`
Bridge health check (no auth required).

```json
{
  "status": "ok",
  "service": "ai-agent-bridge"
}
```

#### `GET /ops/snapshot?min_severity=info`
Main AI-friendly endpoint with filtered data and recommendations.

**Query Parameters:**
- `min_severity` (optional): Filter anomalies by severity (`info`, `warning`, `critical`)

**Response:**
```json
{
  "timestamp": "2025-11-06T04:30:00.000Z",
  "health": "healthy",
  "filters": {
    "min_severity": "info",
    "total_incidents_before_filter": 5
  },
  "anomalies": {
    "total": 2,
    "critical": 1,
    "warnings": 1,
    "incidents": [...]
  },
  "deliveries": {
    "total": 20,
    "problematic": 3,
    "failed": 2,
    "pending": 1,
    "dead_letter": 0,
    "items": [...]
  },
  "recommendations": [
    {
      "priority": "high|medium|low",
      "category": "anomaly|delivery|status",
      "message": "Human-readable recommendation",
      "action": "Specific action to take"
    }
  ]
}
```

#### `GET /ops/anomalies`
Current anomalies only (raw Command Center format).

#### `GET /ops/deliveries?limit=20`
Recent delivery history (raw Command Center format).

#### `POST /ops/replay/:deliveryId`
Replay a failed/pending delivery. Proxies to Command Center with admin role.

## Configuration

### AI Agent Bridge

Create `services/ai-agent-bridge/.env`:

```bash
# Port the bridge listens on
AI_BRIDGE_PORT=3001

# Command Center API base URL
COMMAND_CENTER_API=http://localhost:8010

# CORS configuration (comma-separated origins, or * for all)
# Production: Set to your agent's origin only
CORS_ORIGINS=*

# Minimum severity to include in snapshots (info, warning, critical)
MIN_SEVERITY=info

# Enable verbose logging for debugging
DEBUG=false
```

### MCP Server

Create `services/mcp-server/.env`:

```bash
# AI Agent Bridge base URL
AI_BRIDGE_URL=http://localhost:3001
```

## Use Cases

### 1. Automated Ops Monitoring

Run a scheduled job that checks ops status and sends alerts:

```javascript
// Auto-escalate critical anomalies to PagerDuty
async function autoEscalate() {
  const snapshot = await fetch('http://localhost:3001/ops/snapshot?min_severity=critical');
  const data = await snapshot.json();

  if (data.anomalies.critical > 0) {
    await notifyPagerDuty({
      severity: 'critical',
      summary: `${data.anomalies.critical} critical anomalies detected`,
      details: data.anomalies.incidents
    });
  }
}
```

### 2. Smart Delivery Replay

Automatically replay failed deliveries based on error type:

```javascript
async function smartReplay() {
  const snapshot = await fetch('http://localhost:3001/ops/snapshot');
  const data = await snapshot.json();

  for (const delivery of data.deliveries.items) {
    if (delivery.status === 'failed' &&
        delivery.last_error.includes('503') &&
        delivery.attempts < 3) {
      // Transient error, safe to replay
      await fetch(`http://localhost:3001/ops/replay/${delivery.id}`, {
        method: 'POST'
      });
      console.log(`Replayed delivery ${delivery.id}`);
    }
  }
}
```

### 3. Conversational Ops with Claude Desktop

```
User: Show me the ops status

Claude: [Uses aetherlink.get_ops_snapshot]
✅ All systems healthy. 2 failed deliveries detected.

User: What went wrong with those deliveries?

Claude: Both failures are from the same Slack webhook:
- HTTP 503: Service Unavailable
- This is likely a transient issue with Slack's API
- Delivery has been retried 3/5 times

User: Should we replay them?

Claude: Yes, I'd recommend replaying the first one since it's a
transient 503 error. The second has reached max attempts and needs
investigation first. Would you like me to show you how to replay it?
```

### 4. Multi-Tenant Health Dashboard

Build a custom dashboard that shows per-tenant health:

```javascript
async function getTenantHealth() {
  const snapshot = await fetch('http://localhost:3001/ops/snapshot');
  const data = await snapshot.json();

  // Group anomalies by tenant
  const tenantIssues = {};
  data.anomalies.incidents.forEach(incident => {
    const tenant = incident.affected_tenant || 'system';
    if (!tenantIssues[tenant]) tenantIssues[tenant] = [];
    tenantIssues[tenant].push(incident);
  });

  // Group deliveries by tenant
  data.deliveries.items.forEach(delivery => {
    const tenant = delivery.tenant_id;
    if (!tenantIssues[tenant]) tenantIssues[tenant] = [];
    tenantIssues[tenant].push(delivery);
  });

  return tenantIssues;
}
```

## Troubleshooting

### Bridge not responding

```bash
# Check if bridge is running
curl http://localhost:3001/health

# Check logs
cd services/ai-agent-bridge
node server.js  # Run in foreground to see logs
```

### Empty data in snapshot

```bash
# Verify Command Center is running and has data
curl -H "X-User-Roles: admin" http://localhost:8010/anomalies/current
curl -H "X-User-Roles: operator" http://localhost:8010/alerts/deliveries/history
```

### MCP tools not showing in Claude Desktop

1. Verify config file path
2. Check JSON syntax in config
3. Restart Claude Desktop completely
4. Check Claude Desktop logs (Help → Show Logs)

### CORS errors in browser

Set `CORS_ORIGINS` in bridge `.env`:

```bash
# Allow specific origin
CORS_ORIGINS=http://localhost:5173

# Allow multiple origins
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Security Best Practices

### Production Deployment

1. **Lock down CORS:**
   ```bash
   CORS_ORIGINS=https://your-agent-origin.com
   ```

2. **Use internal network:**
   - Don't expose bridge publicly
   - Run on private network only
   - Use VPN or private subnets

3. **Secure Command Center:**
   - Enable proper authentication
   - Use HTTPS in production
   - Implement rate limiting

4. **Monitor access:**
   - Log all bridge requests
   - Set up alerts for unusual patterns
   - Review access logs regularly

### Development

```bash
# Development mode (permissive CORS)
CORS_ORIGINS=*
DEBUG=true
MIN_SEVERITY=info
```

## Performance Considerations

- **Bridge caching:** Consider adding short-lived cache (5-10s) for `/ops/snapshot` if called frequently
- **Rate limiting:** Implement rate limits if bridge is publicly accessible
- **Parallel requests:** Bridge makes parallel requests to Command Center for better performance
- **Filtering:** Use `min_severity` parameter to reduce data transfer

## Next Steps

1. **Custom MCP tools:** Add more specialized tools (bulk replay, tenant filtering, etc.)
2. **Webhooks:** Add webhook support for push-based notifications
3. **AI-powered insights:** Use LLMs to analyze trends and predict issues
4. **Integration with incident management:** Connect to PagerDuty, Opsgenie, etc.

## License

MIT - Part of the AetherLink platform
