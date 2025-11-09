# Vertical Apps Quick Start Guide

Three standalone vertical applications that optionally integrate with AetherLink.

## Quick Start

### Start All Services

```bash
# PeakPro CRM
cd services/peakpro-crm && python main.py &

# RoofWonder
cd services/roofwonder && python main.py &

# PolicyPal AI
cd services/policypal-ai && python main.py &

# AI Agent Bridge (integrates all)
cd services/ai-agent-bridge && node server.js &
```

### Verify Health

```bash
curl http://localhost:8021/health  # PeakPro CRM
curl http://localhost:8022/health  # RoofWonder
curl http://localhost:8023/health  # PolicyPal AI
curl http://localhost:3001/health  # AI Bridge
```

## PeakPro CRM (Port 8021)

**Contacts, Deals, and Notes Management**

### Create Contact
```bash
curl -X POST http://localhost:8021/crm/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "phone": "555-0101",
    "company": "Tech Corp"
  }'
```

### Create Deal
```bash
curl -X POST http://localhost:8021/crm/deals \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 1,
    "title": "Q4 Enterprise Deal",
    "value": 50000,
    "stage": "negotiation"
  }'
```

### Add Note
```bash
curl -X POST http://localhost:8021/crm/contacts/1/notes \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Follow up next week about pricing"
  }'
```

### Get AI Snapshot
```bash
curl http://localhost:8021/ai/snapshot
```

## RoofWonder (Port 8022)

**Roofing Jobs and Properties**

### Create Property
```bash
curl -X POST http://localhost:8022/rw/properties \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St",
    "owner_name": "Jane Doe",
    "property_type": "residential"
  }'
```

### Create Job
```bash
curl -X POST http://localhost:8022/rw/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": 1,
    "customer_name": "Jane Doe",
    "address": "123 Main St",
    "job_type": "full_replacement",
    "status": "scheduled",
    "scheduled_date": "2025-11-10T09:00:00"
  }'
```

### Create Estimate
```bash
curl -X POST http://localhost:8022/rw/estimates \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": 1,
    "job_type": "full_replacement",
    "estimated_cost": 8500,
    "notes": "3-tab shingles, 2,000 sq ft"
  }'
```

### Get AI Snapshot
```bash
curl http://localhost:8022/ai/snapshot
```

## PolicyPal AI (Port 8023)

**Insurance Policy Management with AI**

### Create Policy
```bash
curl -X POST http://localhost:8023/pp/policies \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-12345",
    "policyholder": "Bob Smith",
    "policy_type": "auto",
    "carrier": "StateFarm",
    "coverage_amount": 500000,
    "effective_date": "2025-01-01",
    "expiration_date": "2025-12-31"
  }'
```

### Search Policies
```bash
curl "http://localhost:8023/pp/policies/search?q=Bob%20Smith"
```

### AI Action: Summarize Policy
```bash
curl -X POST http://localhost:8023/ai/action \
  -H "Content-Type: application/json" \
  -d '{
    "action": "summarize_policy",
    "policy_id": 1
  }'
```

### AI Action: Extract Coverage
```bash
curl -X POST http://localhost:8023/ai/action \
  -H "Content-Type: application/json" \
  -d '{
    "action": "extract_coverage",
    "policy_id": 1
  }'
```

### Get AI Snapshot
```bash
curl http://localhost:8023/ai/snapshot
```

## AI Agent Bridge (Port 3001)

**Unified API for All Services**

### Get Unified Snapshot
```bash
# Includes AetherLink + all vertical apps
curl http://localhost:3001/ops/snapshot | python -m json.tool
```

### Filter by Severity
```bash
curl "http://localhost:3001/ops/snapshot?min_severity=warning"
```

### Just Anomalies
```bash
curl http://localhost:3001/ops/anomalies
```

### Just Deliveries
```bash
curl "http://localhost:3001/ops/deliveries?limit=10"
```

## MCP Tools (AI Assistants)

### List Available Tools
```bash
cd services/mcp-server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node server.js
```

### Call PeakPro Tool
```bash
echo '{
  "jsonrpc":"2.0",
  "id":1,
  "method":"tools/call",
  "params":{
    "name":"peakpro.get_snapshot",
    "arguments":{}
  }
}' | node server.js
```

### Call RoofWonder Tool
```bash
echo '{
  "jsonrpc":"2.0",
  "id":1,
  "method":"tools/call",
  "params":{
    "name":"roofwonder.get_snapshot",
    "arguments":{}
  }
}' | node server.js
```

### Call PolicyPal Tool
```bash
echo '{
  "jsonrpc":"2.0",
  "id":1,
  "method":"tools/call",
  "params":{
    "name":"policypal.get_snapshot",
    "arguments":{}
  }
}' | node server.js
```

### Call Unified Snapshot
```bash
echo '{
  "jsonrpc":"2.0",
  "id":1,
  "method":"tools/call",
  "params":{
    "name":"aetherlink.get_ops_snapshot",
    "arguments":{}
  }
}' | node server.js
```

## API Documentation

### PeakPro CRM
- API Docs: http://localhost:8021/docs
- OpenAPI JSON: http://localhost:8021/openapi.json

### RoofWonder
- API Docs: http://localhost:8022/docs
- OpenAPI JSON: http://localhost:8022/openapi.json

### PolicyPal AI
- API Docs: http://localhost:8023/docs
- OpenAPI JSON: http://localhost:8023/openapi.json

## Environment Variables

### PeakPro CRM
```bash
APP_NAME=peakpro-crm
PORT=8021
STORAGE=memory  # or 'postgres' for production
AI_PROVIDER=local
DISABLE_EXTERNAL_CALLS=true
```

### RoofWonder
```bash
APP_NAME=roofwonder
PORT=8022
STORAGE=memory  # or 'postgres' for production
AI_PROVIDER=local
DISABLE_EXTERNAL_CALLS=true
```

### PolicyPal AI
```bash
APP_NAME=policypal-ai
PORT=8023
STORAGE=memory  # or 'postgres' for production
AI_PROVIDER=local
DISABLE_EXTERNAL_CALLS=true
```

### AI Agent Bridge
```bash
COMMAND_CENTER_API=http://localhost:8010
PEAKPRO_URL=http://localhost:8021
ROOFWONDER_URL=http://localhost:8022
POLICYPAL_URL=http://localhost:8023
AI_BRIDGE_PORT=3001
CORS_ORIGINS=*
MIN_SEVERITY=info
DEBUG=false
```

## Standalone vs Integrated

### Standalone Mode
Each app works independently:
```bash
cd services/peakpro-crm
python main.py
# Now available at http://localhost:8021
```

### Integrated Mode
AI Bridge aggregates all apps:
```bash
# Start all services
# AI Bridge automatically discovers and aggregates them
curl http://localhost:3001/ops/snapshot
# Returns: { ..., apps: { peakpro: {...}, roofwonder: {...}, policypal: {...} } }
```

## Dependencies

### Python Apps (PeakPro, RoofWonder, PolicyPal)
```bash
pip install fastapi uvicorn pydantic python-dotenv
```

### Node.js Apps (AI Bridge, MCP Server)
```bash
# No npm install needed - uses built-in fetch
```

## Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8021
taskkill //F //PID <PID>

# Linux/Mac
lsof -ti:8021 | xargs kill -9
```

### Service Not Responding
```bash
# Check if service is running
curl http://localhost:8021/health

# Check logs (if running in background)
# Look for error messages in terminal output
```

### AI Bridge Shows null for Apps
```bash
# Verify vertical apps are running
curl http://localhost:8021/health
curl http://localhost:8022/health
curl http://localhost:8023/health

# If any fail, start the missing service
```

## Next Steps

1. Add real data to apps
2. Try MCP tools with Claude Code or other AI assistants
3. Build UI components (see `docs/PHASE_XI_VERTICAL_APPS_IMPLEMENTATION.md`)
4. Set up production databases
5. Deploy to production

## Documentation

- Full implementation: `docs/PHASE_XI_VERTICAL_APPS_IMPLEMENTATION.md`
- API references: http://localhost:8021/docs (and 8022, 8023)
- MCP tools: `services/mcp-server/TOOLS_REFERENCE.md`
