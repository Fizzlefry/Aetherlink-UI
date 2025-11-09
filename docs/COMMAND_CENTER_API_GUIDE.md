# Command Center API Developer Guide 📖

**Complete REST + Event API reference for AetherLink Command Center integration**

This guide provides comprehensive documentation for integrating with the Command Center API, including authentication, endpoints, request/response formats, and testing examples.

## 📋 Overview

The Command Center provides a **REST API + Server-Sent Events (SSE)** architecture for:

- **Event Publishing & Streaming**: Real-time event ingestion and distribution
- **Alert Management**: Rule-based alerting with delivery tracking
- **Auto-Healing**: Automated remediation with cooldown management
- **Operational Monitoring**: Health checks, metrics, and audit trails
- **Multi-Tenant Support**: Isolated operations per tenant

### Base URL
```
http://localhost:8010  # Development
https://command-center.yourdomain.com  # Production
```

### Authentication
All endpoints require the `X-User-Roles` header:
```
X-User-Roles: admin,operator,manager
```

### API Versioning
- **Current Version**: v1 (implicit in all endpoints)
- **Deprecation Policy**: 6 months notice for breaking changes
- **Backwards Compatibility**: Maintained within major versions

---

## 🔐 Authentication & RBAC

### Required Header
```
X-User-Roles: admin,operator,manager
```

### Role Permissions Matrix

| Role      | Description | Permissions |
|-----------|-------------|-------------|
| **admin** | Full system access | All endpoints, configuration changes, destructive operations |
| **operator** | Operational monitoring | Read/write alerts, events, auto-heal, monitoring data |
| **manager** | Business oversight | Read-only dashboards, reports, analytics |

### Authentication Examples

**Admin Access:**
```bash
curl -H "X-User-Roles: admin" http://localhost:8010/healthz
```

**Operator Access:**
```bash
curl -H "X-User-Roles: operator" http://localhost:8010/events/recent
```

**Multiple Roles:**
```bash
curl -H "X-User-Roles: admin,operator" http://localhost:8010/autoheal/run
```

### Error Response (403 Forbidden)
```json
{
  "detail": "Not enough permissions"
}
```

---

## 📊 Endpoints Reference

### Health & Meta

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/healthz` | All | Kubernetes-ready health check |
| `GET` | `/meta` | All | Service metadata and version info |
| `GET` | `/` | All | API root with links |
| `GET` | `/ops/ping` | All | Simple ping/pong connectivity test |
| `GET` | `/ops/health` | operator+ | Detailed health status |

**Health Check Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-05T10:30:00Z",
  "service": "command-center",
  "version": "1.0.0"
}
```

**Meta Response:**
```json
{
  "service": "command-center",
  "version": "1.0.0",
  "build": "abc123def",
  "endpoints": {
    "docs": "/docs",
    "health": "/healthz",
    "metrics": "/metrics"
  }
}
```

### Events

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `POST` | `/events/publish` | All | Publish event to Command Center |
| `GET` | `/events/schema` | operator+ | List available event schemas |
| `GET` | `/events/schema/{type}` | operator+ | Get schema for specific event type |
| `GET` | `/events/stream` | operator+ | SSE stream of real-time events |
| `GET` | `/events/recent` | operator+ | Recent events with filtering |
| `GET` | `/events/audit` | operator+ | Event audit trail |
| `GET` | `/events/stats` | operator+ | Event statistics and metrics |
| `POST` | `/events/prune` | operator+ | Manually prune old events |
| `GET` | `/events/retention` | operator+ | Current retention settings |
| `GET` | `/events/retention/tenants` | operator+ | Per-tenant retention config |
| `PUT` | `/events/retention/tenants/{id}` | operator+ | Update tenant retention |
| `DELETE` | `/events/retention/tenants/{id}` | operator+ | Reset tenant retention |

**Publish Event:**
```bash
curl -X POST http://localhost:8010/events/publish \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "service.health.failed",
    "source": "my-service",
    "severity": "error",
    "timestamp": "2025-11-05T10:30:00Z",
    "tenant_id": "tenant-123",
    "payload": {
      "service_name": "api-gateway",
      "error": "connection_timeout"
    }
  }'
```

**Event Schema Response:**
```json
{
  "event_type": "service.health.failed",
  "required": ["event_type", "source", "timestamp", "payload"],
  "description": "Emitted when a monitored service fails health check"
}
```

### Alerts & Rules

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `POST` | `/alerts/rules` | operator+ | Create alert rule |
| `GET` | `/alerts/rules` | operator+ | List alert rules |
| `GET` | `/alerts/rules/{id}` | operator+ | Get specific rule |
| `PATCH` | `/alerts/rules/{id}` | operator+ | Update rule |
| `DELETE` | `/alerts/rules/{id}` | operator+ | Delete rule |
| `POST` | `/alerts/evaluate` | operator+ | Manually evaluate rules |
| `GET` | `/alerts/deliveries` | operator+ | List alert deliveries |
| `GET` | `/alerts/deliveries/stats` | operator+ | Delivery statistics |

**Create Alert Rule:**
```bash
curl -X POST http://localhost:8010/alerts/rules \
  -H "X-User-Roles: admin" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Error Rate",
    "description": "Alert when service error rate exceeds 5%",
    "condition": "error_rate > 0.05",
    "severity": "warning",
    "channels": ["email", "slack"],
    "enabled": true
  }'
```

### Delivery History

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/alerts/deliveries/history` | operator+ | Delivery history with filtering |
| `GET` | `/alerts/deliveries/{id}` | operator+ | Get specific delivery |
| `POST` | `/alerts/deliveries/{id}/replay` | operator+ | Replay failed delivery |

**Delivery History Query:**
```bash
curl -H "X-User-Roles: operator" \
  "http://localhost:8010/alerts/deliveries/history?status=failed&limit=10"
```

### Auto-Healing

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/autoheal/rules` | admin | List auto-heal rules |
| `POST` | `/autoheal/clear_endpoint_cooldown` | admin | Clear cooldown for endpoint |
| `POST` | `/autoheal/run` | admin | Manually trigger auto-heal |
| `GET` | `/autoheal/last` | admin | Last auto-heal execution |
| `GET` | `/autoheal/history` | admin | Auto-heal execution history |
| `DELETE` | `/autoheal/cooldown/{endpoint}` | admin | Clear specific endpoint cooldown |
| `GET` | `/autoheal/config` | admin | Auto-heal configuration |

**Trigger Auto-Heal:**
```bash
curl -X POST http://localhost:8010/autoheal/run \
  -H "X-User-Roles: admin" \
  -H "Content-Type: application/json" \
  -d '{
    "target_service": "api-gateway",
    "reason": "manual_trigger"
  }'
```

### Metrics & Monitoring

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/metrics` | All | Prometheus-compatible metrics |

**Key Metrics:**
```
# HELP command_center_uptime_seconds Time since Command Center service started
# TYPE command_center_uptime_seconds gauge
command_center_uptime_seconds 3600.5

# HELP command_center_health Service health status (1=healthy, 0=unhealthy)
# TYPE command_center_health gauge
command_center_health 1

# HELP command_center_api_requests_total Total API requests to Command Center
# TYPE command_center_api_requests_total counter
command_center_api_requests_total{method="GET",endpoint="/healthz",status="200"} 150

# HELP command_center_events_total Total events published by Command Center
# TYPE command_center_events_total counter
command_center_events_total{event_type="service.registered",severity="info"} 25
```

### Operational Endpoints

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/ops/services` | operator+ | List registered services |
| `POST` | `/ops/register` | operator+ | Register a service |
| `DELETE` | `/ops/services/{name}` | operator+ | Unregister service |
| `GET` | `/audit/stats` | operator+ | Audit statistics |

---

## 📡 Sample Requests

### Python (requests)

```python
import requests

# Health check
response = requests.get(
    "http://localhost:8010/healthz",
    headers={"X-User-Roles": "admin"}
)
print(response.json())

# Publish event
event = {
    "event_type": "service.health.failed",
    "source": "my-app",
    "severity": "error",
    "timestamp": "2025-11-05T10:30:00Z",
    "payload": {"error": "database_connection_failed"}
}

response = requests.post(
    "http://localhost:8010/events/publish",
    json=event
)
print(f"Event published: {response.status_code}")
```

### JavaScript (fetch)

```javascript
// Health check
const healthResponse = await fetch('http://localhost:8010/healthz', {
  headers: { 'X-User-Roles': 'operator' }
});
const health = await healthResponse.json();
console.log('Health:', health);

// Publish event
const event = {
  event_type: 'deployment.started',
  source: 'ci-cd',
  severity: 'info',
  timestamp: new Date().toISOString(),
  payload: { version: '1.2.3' }
};

const publishResponse = await fetch('http://localhost:8010/events/publish', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(event)
});
console.log('Published:', publishResponse.status);
```

### cURL Examples

```bash
# Check health
curl -H "X-User-Roles: admin" http://localhost:8010/healthz

# List recent events
curl -H "X-User-Roles: operator" "http://localhost:8010/events/recent?limit=5"

# Create alert rule
curl -X POST http://localhost:8010/alerts/rules \
  -H "X-User-Roles: admin" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Alert","condition":"true","severity":"info"}'

# Get metrics
curl http://localhost:8010/metrics
```

---

## 🌊 Webhooks & Events

### Server-Sent Events (SSE) Stream

**Endpoint:** `GET /events/stream`

**Headers Required:**
```
X-User-Roles: operator
Accept: text/event-stream
```

**Stream Format:**
```
event: event
data: {"event_type":"service.health.failed","source":"api-gateway",...}

event: event
data: {"event_type":"autoheal.succeeded","source":"command-center",...}
```

**JavaScript Client:**
```javascript
const eventSource = new EventSource('http://localhost:8010/events/stream', {
  headers: { 'X-User-Roles': 'operator' }
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received event:', data.event_type);
  // Handle event based on type
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
};
```

### Event Types

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `service.registered` | Service registration | `{service_name, endpoints}` |
| `service.health.failed` | Health check failure | `{service_name, error}` |
| `autoheal.attempted` | Auto-heal triggered | `{target_service, action}` |
| `autoheal.succeeded` | Auto-heal success | `{target_service, action}` |
| `autoheal.failed` | Auto-heal failure | `{target_service, error}` |
| `alert.triggered` | Alert condition met | `{rule_name, severity, details}` |
| `delivery.replayed` | Delivery replayed | `{delivery_id, original_status}` |

---

## ⚠️ Error Handling

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Normal API responses |
| `400` | Bad Request | Invalid JSON, missing fields |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Endpoint or resource doesn't exist |
| `422` | Validation Error | Schema validation failed |
| `500` | Internal Error | Server-side error |

### Error Response Format

```json
{
  "detail": "Not enough permissions"
}
```

```json
{
  "detail": [
    {
      "loc": ["body", "event_type"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Common Error Scenarios

**Authentication Issues:**
```bash
# Missing header
curl http://localhost:8010/healthz
# Returns: 403 Forbidden

# Invalid role
curl -H "X-User-Roles: invalid" http://localhost:8010/healthz
# Returns: 403 Forbidden
```

**Validation Errors:**
```bash
# Missing required field
curl -X POST http://localhost:8010/events/publish \
  -H "Content-Type: application/json" \
  -d '{"source":"test"}'
# Returns: 422 with validation details
```

---

## 🔄 Versioning & Compatibility

### API Versioning Strategy

- **URL Path Versioning**: `/v1/events/publish` (future major versions)
- **Header Versioning**: `X-API-Version: 1.0` (minor/patch versions)
- **Deprecation Headers**: `X-Deprecation-Notice` in responses

### Compatibility Guarantees

- **Major Version (v1, v2)**: Breaking changes allowed
- **Minor Version (1.1, 1.2)**: New features, backwards compatible
- **Patch Version (1.0.1)**: Bug fixes only

### Migration Guide

**Upgrading from v0.x to v1.0:**
1. Update `X-User-Roles` header format (comma-separated)
2. Use new event schema validation
3. Update SSE stream handling for new event types

---

## 🧪 Testing

### pytest Integration

```python
# tests/test_api_integration.py
import pytest
import requests

BASE_URL = "http://localhost:8010"

def test_health_check():
    response = requests.get(f"{BASE_URL}/healthz",
                          headers={"X-User-Roles": "admin"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_event_publish():
    event = {
        "event_type": "test.event",
        "source": "pytest",
        "severity": "info",
        "timestamp": "2025-11-05T10:30:00Z",
        "payload": {"test": True}
    }

    response = requests.post(f"{BASE_URL}/events/publish", json=event)
    assert response.status_code == 200

def test_unauthorized_access():
    response = requests.get(f"{BASE_URL}/events/recent")
    assert response.status_code == 403
```

### Load Testing

```bash
# Install hey for load testing
go install github.com/rakyll/hey@latest

# Test health endpoint
hey -n 1000 -c 10 http://localhost:8010/healthz

# Test event publishing
hey -n 500 -c 5 -m POST \
  -H "Content-Type: application/json" \
  -d '{"event_type":"load.test","source":"hey","severity":"info","timestamp":"2025-11-05T10:30:00Z","payload":{}}' \
  http://localhost:8010/events/publish
```

### Integration Test Suite

```bash
# Run full API test suite
cd services/command-center
python -m pytest tests/ -v --tb=short

# Run specific endpoint tests
python -m pytest tests/test_events.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

---

## 📚 Related Documentation

### Core Documentation
- **[Command Center Ops Runbook](COMMAND_CENTER_OPS_RUNBOOK.md)** - Complete operations guide
- **[Quick Start Guide](COMMAND_CENTER_QUICKSTART.md)** - 5-minute setup checklist
- **[Root README](../README.md)** - Executive overview and architecture

### Service Documentation
- **[Command Center API](../services/command-center/README.md)** - Backend service details
- **[Operator Dashboard](../services/ui/README.md)** - Frontend application guide
- **[Monitoring & Observability](../observability/README.md)** - Metrics and dashboards

### Development Resources
- **[Event Schema Registry](../docs/EVENT_SCHEMA_REGISTRY.md)** - Complete event type reference
- **[CI/CD Pipeline](../.github/workflows/command-center-ci.yml)** - Build and release automation
- **[Docker Deployment](../deploy/README.md)** - Container setup and configuration

---

## 🎯 Quick Reference

### Most Common Endpoints

```bash
# Health & status
curl -H "X-User-Roles: admin" http://localhost:8010/healthz
curl -H "X-User-Roles: operator" http://localhost:8010/meta

# Events
curl -X POST http://localhost:8010/events/publish -d '{"event_type":"test"}'
curl -H "X-User-Roles: operator" http://localhost:8010/events/recent

# Alerts
curl -H "X-User-Roles: operator" http://localhost:8010/alerts/deliveries/history

# Auto-heal
curl -H "X-User-Roles: admin" http://localhost:8010/autoheal/rules

# Metrics
curl http://localhost:8010/metrics
```

### Development Workflow

1. **Start local instance** (see Quick Start Guide)
2. **Test authentication** with health endpoint
3. **Publish test events** to verify ingestion
4. **Monitor SSE stream** for real-time updates
5. **Check metrics** for observability
6. **Run integration tests** before deployment

---

**Built with ❤️ for reliable AI operations at scale.**
---

## Related Services

- Media Service statistics for storage/ingest dashboards: see services/media-service/README.md (endpoint: GET http://localhost:9109/uploads/stats).
