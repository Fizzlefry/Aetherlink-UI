# AetherLink Event Control Plane (Phase VI)

## Goals
- Single, authenticated endpoint to accept platform events
- Validate events against a shared schema list
- Make events available to future consumers (storage, UI, anomaly detection)
- Keep it consistent with existing AetherLink protocol (RBAC, audit, health)

## Standard Event Envelope

All events published to Command Center must follow this structure:

```json
{
  "event_type": "service.registered",
  "source": "aether-ai-orchestrator",
  "tenant_id": "default",
  "severity": "info",
  "timestamp": "2025-11-04T22:45:12Z",
  "payload": { "any": "json" }
}
```

### Required Fields

- **event_type** (string): Type of event from schema registry
- **source** (string): Service name emitting the event
- **timestamp** (ISO 8601): Producer time (auto-generated if omitted)
- **payload** (object): Event-specific data

### Optional Fields

- **tenant_id** (string): Tenant identifier for multi-tenant filtering (default: "default")
- **severity** (string): info | warning | error | critical (default: "info")
- **event_id** (UUID): Unique event identifier (auto-generated if omitted)

## RBAC Requirements

### Reading Schemas
- `X-User-Roles: operator` or `admin` to read schemas via GET `/events/schema`

### Publishing Events
- `X-User-Roles: agent`, `operator`, or `admin` to publish via POST `/events/publish`
- Services use their existing role-based authentication

## Event Types Registry

### `service.registered`
**Emitted when**: A service registers with Command Center
**Source**: Command Center
**Payload**:
```json
{
  "name": "aether-ai-orchestrator",
  "url": "http://aether-ai-orchestrator:8011",
  "version": "v1.10.0",
  "tags": ["ai", "orchestrator"]
}
```

### `service.health.failed`
**Emitted when**: A monitored service fails health check
**Source**: Auto-Heal or Command Center
**Payload**:
```json
{
  "service": "aether-crm-ui",
  "health_url": "http://aether-crm-ui:3000/health",
  "status_code": 503,
  "reason": "connection_timeout"
}
```

### `autoheal.attempted`
**Emitted when**: Auto-Heal attempts to restart a container
**Source**: Auto-Heal
**Payload**:
```json
{
  "service": "aether-crm-ui",
  "reason": "healthcheck_failed",
  "restart_count": 1
}
```

### `autoheal.succeeded`
**Emitted when**: Auto-Heal successfully restarts a container
**Source**: Auto-Heal
**Payload**:
```json
{
  "service": "aether-crm-ui",
  "duration_ms": 2340
}
```

### `autoheal.failed`
**Emitted when**: Auto-Heal fails to restart a container
**Source**: Auto-Heal
**Payload**:
```json
{
  "service": "aether-crm-ui",
  "reason": "docker_api_error",
  "error": "Container not found"
}
```

### `ai.fallback.used`
**Emitted when**: AI Orchestrator uses a fallback provider
**Source**: AI Orchestrator
**Payload**:
```json
{
  "original_provider": "claude",
  "fallback_provider": "ollama",
  "intent": "summarize-activity",
  "reason": "provider_unavailable"
}
```

## API Endpoints

### GET `/events/schema`
List all registered event schemas.

**Request**:
```bash
curl -H "X-User-Roles: operator" http://localhost:8010/events/schema
```

**Response**:
```json
{
  "status": "ok",
  "schemas": [
    {
      "event_type": "service.registered",
      "required": ["event_type", "source", "timestamp", "payload"],
      "description": "Emitted when a service registers with Command Center"
    }
  ]
}
```

### GET `/events/schema/{event_type}`
Get schema for specific event type.

**Request**:
```bash
curl -H "X-User-Roles: operator" http://localhost:8010/events/schema/autoheal.attempted
```

**Response**:
```json
{
  "status": "ok",
  "event_type": "autoheal.attempted",
  "schema": {
    "required": ["event_type", "source", "timestamp", "payload"],
    "description": "Emitted by auto-heal when it restarts a container"
  }
}
```

### POST `/events/publish`
Publish an event to Command Center.

**Request**:
```bash
curl -X POST http://localhost:8010/events/publish \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "autoheal.attempted",
    "source": "aether-auto-heal",
    "timestamp": "2025-11-04T22:45:12Z",
    "payload": {
      "service": "aether-crm-ui",
      "reason": "healthcheck_failed"
    }
  }'
```

**Response**:
```json
{
  "status": "ok",
  "stored": true,
  "event_type": "autoheal.attempted",
  "received_at": "2025-11-04T22:45:13.123456+00:00"
}
```

### GET `/events/recent`
Retrieve recent events (M2+).

**Request**:
```bash
curl -H "X-User-Roles: operator" http://localhost:8010/events/recent?limit=10
```

**Response**:
```json
{
  "status": "ok",
  "count": 2,
  "events": [
    {
      "id": 42,
      "event_type": "autoheal.attempted",
      "source": "aether-auto-heal",
      "timestamp": "2025-11-04T22:45:12Z",
      "payload": { "service": "aether-crm-ui" },
      "received_at": "2025-11-04T22:45:13.123456+00:00"
    }
  ]
}
```

### GET `/events/stream` (SSE)
Real-time event stream for UI (M2+).

**Request**:
```bash
curl -H "X-User-Roles: operator" -N http://localhost:8010/events/stream
```

**Response** (Server-Sent Events):
```
data: {"event_type":"autoheal.attempted","source":"aether-auto-heal",...}

data: {"event_type":"ai.fallback.used","source":"aether-ai-orchestrator",...}
```

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Event Control Plane (Phase VI)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Service (Auto-Heal, AI Orchestrator, etc.)                      │
│         ↓                                                        │
│  POST /events/publish                                            │
│         ↓                                                        │
│  Command Center:                                                 │
│    1. Validate against schema                                    │
│    2. Normalize (timestamp, metadata)                            │
│    3. Store (SQLite/DB)                                          │
│    4. Fan-out (SSE subscribers)                                  │
│         ↓                                                        │
│  Consumers:                                                      │
│    - UI Event Viewer (SSE /events/stream)                        │
│    - Historical analytics (GET /events/recent)                   │
│    - Anomaly detection (future)                                  │
│    - Audit trail (future)                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Phase VI Milestones

### M1: Event Publish + Schema ✅
- Event schema registry (in-memory)
- POST `/events/publish` endpoint
- GET `/events/schema` endpoints
- In-memory event buffer
- Service integration (Auto-Heal, AI Orchestrator)

### M2: Event Ingest + Live Stream 🔄
- Persistent event storage (SQLite)
- GET `/events/recent` from storage
- SSE endpoint GET `/events/stream`
- React EventStream component
- Real-time UI visibility

### M3: Tenant-Aware Events (Future)
- X-Tenant-ID header propagation
- Tenant-based event filtering
- Multi-tenant isolation
- Per-tenant analytics

### M4: Historical Analytics (Future)
- Time-range queries
- Event aggregation
- Trend analysis
- Anomaly detection hooks

## Benefits

**Operational:**
- Single pane of glass for platform events
- Real-time visibility into service behavior
- Historical event timeline for debugging
- Faster incident diagnosis (MTTR reduction)

**Technical:**
- Unified event pipeline (replaces scattered logging)
- Schema-enforced consistency
- Protocol-compliant (RBAC, audit)
- Extensible for ML/anomaly detection

**Strategic:**
- Command Center becomes true control plane
- Foundation for event-driven workflows
- Multi-tenant SaaS readiness
- Compliance-ready audit trail
