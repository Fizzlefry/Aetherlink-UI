# 🤖 AetherLink MCP Server

Model Context Protocol (MCP) server that exposes AetherLink operator data as tools for AI assistants like Claude Desktop.

## Architecture

```
MCP Client (Claude Desktop)
    ↓ stdio
MCP Server (:stdio)  ← This service
    ↓ HTTP
AI Agent Bridge (:3001)
    ↓ HTTP + X-User-Roles
Command Center (:8010)
```

The MCP server is a thin wrapper over the AI Agent Bridge, converting HTTP endpoints into MCP tool calls.

## Features

- ✅ **Zero HTTP exposure** - Uses stdio transport (secure by default)
- ✅ **Declarative tools** - AI assistants see available operations automatically
- ✅ **Proxies to bridge** - No duplicate business logic
- ✅ **Severity filtering** - Supports same filtering as the bridge

## Available Tools

### `aetherlink.get_ops_snapshot`
Get comprehensive ops snapshot with anomalies, deliveries, and recommendations.

**Parameters:**
- `min_severity` (optional): Filter by severity (`info`, `warning`, `critical`)

**Returns:** AI-friendly JSON with:
- Current anomalies (filtered by severity)
- Problematic deliveries (failed/pending/dead_letter)
- Actionable recommendations
- Summary statistics

### `aetherlink.get_anomalies`
Get current anomalies only (raw Command Center format).

**Returns:** Anomaly detection results with incidents and summary.

### `aetherlink.get_deliveries`
Get recent delivery history.

**Parameters:**
- `limit` (optional): Max number of deliveries to return (default: 20)

**Returns:** Delivery history with status, attempts, errors.

### `aetherlink.replay_delivery`
Replay a failed or pending delivery.

**Parameters:**
- `delivery_id` (required): The UUID of the delivery to replay

**Returns:** Replay confirmation with new status.

**Example:**
```json
{
  "delivery_id": "4a142c00-aa0e-43cb-aac7-f85bf5aef14f"
}
```

## Quick Start

### Prerequisites
1. **Command Center** must be running on port 8010
2. **AI Agent Bridge** must be running on port 3001

```bash
# From AetherLink root
cd services/ai-agent-bridge
node server.js &

cd ../mcp-server
node server.js
```

The MCP server reads from stdin and writes to stdout (JSON-RPC over stdio).

## Claude Desktop Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "aetherlink": {
      "command": "node",
      "args": [
        "/path/to/AetherLink/services/mcp-server/server.js"
      ],
      "env": {
        "AI_BRIDGE_URL": "http://localhost:3001"
      }
    }
  }
}
```

On Windows, update path accordingly:

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

After restarting Claude Desktop, you'll see the AetherLink tools available in the tool picker.

## Example Usage in Claude Desktop

**User:** "What's the current ops status?"

**Claude:** *Uses `aetherlink.get_ops_snapshot` tool*

```json
{
  "timestamp": "2025-11-06T04:30:00.000Z",
  "health": "healthy",
  "anomalies": {
    "total": 1,
    "critical": 1,
    "incidents": [
      {
        "severity": "critical",
        "message": "Error rate spike: 400% above baseline",
        "affected_tenant": "tenant-qa"
      }
    ]
  },
  "deliveries": {
    "problematic": 2,
    "failed": 2,
    "items": [
      {
        "id": "4a142c00-aa0e-43cb-aac7-f85bf5aef14f",
        "status": "failed",
        "last_error": "HTTP 503: Service Unavailable"
      }
    ]
  },
  "recommendations": [
    {
      "priority": "high",
      "message": "1 critical anomalies detected. Investigate immediately."
    }
  ]
}
```

**Claude:** "⚠️ Critical alert: Error rate spike detected (400% above baseline) affecting tenant-qa. 2 delivery failures also detected. I recommend investigating the spike immediately and considering replay for failed deliveries."

**User:** "Can you replay that failed delivery?"

**Claude:** *Uses `aetherlink.replay_delivery` tool with delivery_id*

**Claude:** "✅ Delivery 4a142c00-aa0e-43cb-aac7-f85bf5aef14f has been queued for replay. It will be retried shortly."

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_BRIDGE_URL` | `http://localhost:3001` | AI Agent Bridge base URL |

## Testing Locally

You can test the MCP server manually using stdio:

```bash
# Start the server
node server.js

# Send JSON-RPC messages (one per line)
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"aetherlink.get_ops_snapshot","arguments":{}}}
```

Press Ctrl+D to end stdin when done.

## Protocol Details

This server implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) stdio transport.

**Supported methods:**
- `initialize` - Server handshake
- `tools/list` - List available tools
- `tools/call` - Execute a tool

**Transport:** JSON-RPC 2.0 over stdio (one message per line)

## Troubleshooting

### "Bridge error 500"
```bash
# Verify AI Agent Bridge is running
curl http://localhost:3001/health
```

### "Connection refused"
```bash
# Verify Command Center is running
curl http://localhost:8010/health
```

### Tools not appearing in Claude Desktop
1. Check config file path is correct
2. Restart Claude Desktop completely
3. Check Claude Desktop logs for MCP errors
4. Verify `node` is in PATH

### Testing the full stack
```bash
# Terminal 1: Command Center
cd services/command-center
python -m uvicorn main:app --host 0.0.0.0 --port 8010

# Terminal 2: AI Agent Bridge
cd services/ai-agent-bridge
node server.js

# Terminal 3: MCP Server (for manual testing)
cd services/mcp-server
node server.js
```

## Production Deployment

For production, you may want to:

1. **Use process manager** - PM2, systemd, or Docker
2. **Configure bridge URL** - Point to production bridge endpoint
3. **Add health monitoring** - The MCP server itself has no health endpoint (stdio-only)
4. **Secure the bridge** - Lock down CORS, use internal network only

## License

MIT - Part of the AetherLink platform
