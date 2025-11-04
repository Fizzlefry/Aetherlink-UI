# AetherLink Protocols v1.0

**Status:** Draft  
**Target versions:** v1.12.0+  
**Scope:** Internal services only

## 1. Service Identity

Every HTTP service MUST expose:

- `GET /ping` → `{ "status": "ok", "service": "<name>" }`
- `GET /health` or domain equivalent (Command Center is `/ops/health`, Auto-Heal is `/autoheal/status`)

Services SHOULD identify themselves with:

```json
{
  "service": "aetherlink-command-center",
  "version": "1.12.0",
  "uptime_seconds": 1234
}
```

## 2. Auth / RBAC Header

All protected endpoints MUST accept the unified header:

```
X-User-Roles: operator,admin
```

or JSON:

```
X-User-Roles: ["operator","admin"]
```

and return:

- **401** if header missing
- **403** if roles present but insufficient

**Roles (canonical):**
- `viewer`
- `agent`
- `operator`
- `admin`

## 3. Audit Logging

All sensitive services MUST log:

- timestamp (ISO8601)
- service name
- path
- method
- roles (if present)
- status code
- client ip (best-effort)

**Minimum shape:**

```json
{
  "ts": "2025-11-04T15:22:01Z",
  "service": "aetherlink-ai-orchestrator",
  "path": "/orchestrate",
  "method": "POST",
  "roles": "agent",
  "status": 200,
  "client_ip": "172.18.0.5"
}
```

MUST provide: `GET /audit/stats` protected by `operator|admin`.

## 4. Health Model

Service health is 1 of:

- `ok`
- `degraded`
- `down`

Command Center will normalize to these values.

## 5. Auto-Heal Integration

Any service that wants self-heal MUST:

- expose a stable health URL
- be named in `AUTOHEAL_SERVICES`
- be mapped in `AUTOHEAL_HEALTH_ENDPOINTS`

**Example:**

```bash
AUTOHEAL_SERVICES=["aether-crm-ui","aether-command-center","aether-ai-orchestrator"]
AUTOHEAL_HEALTH_ENDPOINTS={
  "aether-crm-ui": "http://aether-crm-ui:5173/health.json",
  "aether-command-center": "http://aether-command-center:8010/ops/ping",
  "aether-ai-orchestrator": "http://aether-ai-orchestrator:8011/ping"
}
```

## 6. Service Registration (soft)

Until we add a registry, services MUST announce themselves via `/ops/health` or `/ping` so Command Center can poll on a known list from config.

**Future:** `POST /ops/register` to Command Center for dynamic discovery.

## 7. Protocol Compliance Checklist

When adding a new AetherLink service:

1. **Expose health**
   - `GET /ping` → `{ "status": "ok", "service": "<name>" }`
   - (optional) `GET /health` → detailed health info

2. **Add to config**
   - Add service URL to `config/.env.*`
   - If healable, add to `AUTOHEAL_SERVICES` and `AUTOHEAL_HEALTH_ENDPOINTS`

3. **Protect endpoints**
   - Require `X-User-Roles` header
   - Return 401 / 403 per AetherLink Protocols

4. **Audit**
   - Add middleware from `services/common/audit.py`
   - Expose `GET /audit/stats`
   - Make it operator-only

5. **Observability**
   - Ensure Command Center can poll it
   - (optional) emit events to Kafka/event-sink using registry

6. **Tests**
   - Add Playwright/API test: ping, health, rbac, audit
   - Add to CI matrix

## 8. Versioning

Services MUST include version in `/ping` response.

**Format:** `vX.Y.Z` (semver)

**Example:**
```json
{
  "status": "ok",
  "service": "aetherlink-ai-orchestrator",
  "version": "v1.10.0"
}
```

## 9. Error Response Format

All services SHOULD return errors in consistent format:

```json
{
  "error": "insufficient_permissions",
  "message": "Operator role required",
  "status": 403
}
```

## 10. Timeouts

- Health checks: 5s timeout
- API calls between services: 10s default
- AI operations: 30s max
- Long-running tasks: use async with status polling

---

**Next:** See `EVENT_SCHEMA_REGISTRY.md` for event-driven messaging protocol.
