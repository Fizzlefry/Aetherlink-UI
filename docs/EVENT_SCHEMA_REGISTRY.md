# AetherLink Event Schema Registry

**Status:** Draft  
**Topic prefix:** `aetherlink.*`

## Event-Driven Architecture

AetherLink services communicate via:
1. **Synchronous HTTP** - for immediate responses (protocols)
2. **Asynchronous Events** - for decoupled workflows (this registry)

All events flow through the event spine (Kafka/Redis/queue).

## Event Structure

All events MUST follow this envelope:

```json
{
  "event_type": "domain.entity.action",
  "event_version": 1,
  "event_id": "evt_unique_id",
  "occurred_at": "2025-11-04T15:32:00Z",
  "tenant_id": "tenant-001",
  "payload": { ... },
  "metadata": { ... }
}
```

## Registered Event Types

### 1. Lead Created

- **topic**: `aetherlink.crm.lead.created`
- **version**: 1
- **producer**: UI → ApexFlow → events sink
- **consumers**: notifications, AI summarizer (optional), audit

**Schema:**

```json
{
  "event_type": "lead.created",
  "event_version": 1,
  "event_id": "evt_lead_123",
  "occurred_at": "2025-11-04T15:32:00Z",
  "tenant_id": "tenant-001",
  "lead": {
    "id": "lead_123",
    "email": "sarah.chen@techstart.io",
    "name": "Sarah Chen",
    "company": "TechStart Inc",
    "source": "ai-extract"
  },
  "metadata": {
    "ui_version": "v1.1.0",
    "actor": "agent:crmuser"
  }
}
```

### 2. AI Summary Created

- **topic**: `aetherlink.ai.summary.created`
- **version**: 1
- **producer**: AI Orchestrator
- **consumers**: UI, notifications, activity log

**Schema:**

```json
{
  "event_type": "ai.summary.created",
  "event_version": 1,
  "event_id": "evt_sum_993",
  "occurred_at": "2025-11-04T15:35:00Z",
  "tenant_id": "tenant-001",
  "summary": {
    "id": "sum_993",
    "lead_id": "lead_123",
    "text": "Customer is happy but budget constrained...",
    "model": "claude-sonnet",
    "latency_ms": 842
  },
  "metadata": {
    "orchestrator": "aetherlink-ai-orchestrator",
    "provider": "claude",
    "provider_used": "claude"
  }
}
```

### 3. Auto-Heal Performed

- **topic**: `aetherlink.ops.autoheal.performed`
- **version**: 1
- **producer**: Auto-Heal
- **consumers**: Command Center, audit, alerting

**Schema:**

```json
{
  "event_type": "ops.autoheal.performed",
  "event_version": 1,
  "event_id": "evt_ah_4493",
  "occurred_at": "2025-11-04T15:40:11Z",
  "service": "aether-crm-ui",
  "action": "restart_container",
  "success": true,
  "attempt_id": "ah_4493",
  "metadata": {
    "reason": "healthcheck failed 3 times",
    "docker_container": "aether-crm-ui",
    "interval_seconds": 30
  }
}
```

### 4. Service Registered

- **topic**: `aetherlink.ops.service.registered`
- **version**: 1
- **producer**: Command Center (service registry)
- **consumers**: Auto-Heal, monitoring, audit

**Schema:**

```json
{
  "event_type": "ops.service.registered",
  "event_version": 1,
  "event_id": "evt_reg_001",
  "occurred_at": "2025-11-04T16:00:00Z",
  "service": {
    "name": "aether-ai-orchestrator",
    "url": "http://aether-ai-orchestrator:8011",
    "health_url": "http://aether-ai-orchestrator:8011/ping",
    "version": "v1.10.0",
    "tags": ["ai", "routing"]
  },
  "metadata": {
    "registered_by": "operator:admin",
    "registry_version": "v1.13.0"
  }
}
```

### 5. RBAC Violation

- **topic**: `aetherlink.security.rbac.violation`
- **version**: 1
- **producer**: Any service with RBAC
- **consumers**: Security audit, alerting

**Schema:**

```json
{
  "event_type": "security.rbac.violation",
  "event_version": 1,
  "event_id": "evt_rbac_401",
  "occurred_at": "2025-11-04T16:05:00Z",
  "violation": {
    "service": "aether-command-center",
    "path": "/ops/health",
    "method": "GET",
    "required_roles": ["operator", "admin"],
    "provided_roles": [],
    "status": 401,
    "client_ip": "172.18.0.5"
  },
  "metadata": {
    "audit_version": "v1.11.0"
  }
}
```

## Versioning Rules

**Golden Rule:** Never break existing consumers.

1. **Adding fields:** OK - bump `event_version`, old consumers ignore
2. **Removing fields:** NEVER - create new event type
3. **Changing types:** NEVER - create new event type
4. **Renaming fields:** NEVER - add new field, deprecate old

**Example Evolution:**

```json
// v1
{
  "event_version": 1,
  "summary": { "text": "..." }
}

// v2 - added confidence score
{
  "event_version": 2,
  "summary": { 
    "text": "...",
    "confidence": 0.92  // NEW - old consumers ignore
  }
}
```

## Topic Naming Convention

**Format:** `aetherlink.<domain>.<entity>.<action>`

**Examples:**
- `aetherlink.crm.lead.created`
- `aetherlink.crm.lead.updated`
- `aetherlink.ai.summary.created`
- `aetherlink.ops.autoheal.performed`
- `aetherlink.ops.service.registered`
- `aetherlink.security.rbac.violation`

## Consumer Contract

Consumers MUST:
1. Accept any `event_version` >= their minimum supported version
2. Ignore unknown fields (forward compatibility)
3. Log schema validation errors but not crash
4. Use idempotency keys (`event_id`) to deduplicate

## Producer Contract

Producers MUST:
1. Include all required envelope fields
2. Use ISO8601 timestamps (`occurred_at`)
3. Generate unique `event_id` (UUID or snowflake)
4. Never send null for required fields
5. Emit events **after** database commit (if applicable)

## Testing Events

For testing, use topic prefix: `aetherlink.test.*`

These topics are auto-cleaned every 24h.

## Future Enhancements

- Schema validation at producer (JSON Schema)
- Dead-letter queue for failed consumers
- Event replay capability
- Cross-tenant event filtering
- Event archival to S3/cold storage

---

**Next:** See `AETHERLINK_PROTOCOLS.md` for HTTP service protocols.
