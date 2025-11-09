# AetherLink Command Center – Operations Runbook

**Version:** 1.0.0
**Last Updated:** 2025-11-05
**Service Owner:** Platform Team

---

## Overview

The **Command Center** is AetherLink's centralized operations hub providing:

- Real-time webhook delivery monitoring & replay
- Auto-healing engine with smart rules & cooldowns
- Tenant analytics & anomaly detection
- Operator audit trail & insights
- Role-based access control (RBAC)

**Production Status:** ✅ Ship-ready

---

## Service Architecture

```
┌─────────────────────────────────────────────────┐
│           Command Center (FastAPI)              │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ REST API │  │ SSE      │  │ Prometheus   │ │
│  │ (8010)   │  │ /events  │  │ /metrics     │ │
│  └──────────┘  └──────────┘  └──────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │  RBAC Middleware (X-User-Roles)          │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────┬──────────┬──────────────────┐   │
│  │ Delivery │ Autoheal │ Event Store      │   │
│  │ History  │ Rules    │ (JSONLines)      │   │
│  └──────────┴──────────┴──────────────────┘   │
└─────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
    PostgreSQL          Filesystem Store
    (optional)          /app/data/
```

---

## API Endpoints

### Health & Discovery

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/healthz` | GET | None | Kubernetes health probe |
| `/meta` | GET | None | Feature flags & API version |
| `/metrics` | GET | None | Prometheus metrics |

**Example:**
```bash
curl http://command-center:8010/healthz
# {"status": "healthy"}

curl http://command-center:8010/meta
# {"features": ["delivery_history", "autoheal", "anomaly_detection", ...]}
```

---

### Delivery History & Replay

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/alerts/deliveries/history` | GET | `operator` | Filter/paginate delivery attempts |
| `/alerts/deliveries/{id}/replay` | POST | `operator` | Replay failed delivery |

**Query Parameters:**
- `tenant_id` – Filter by tenant
- `status` – `failed` \| `pending` \| `success`
- `start_time` / `end_time` – ISO 8601
- `skip` / `limit` – Pagination

**Example:**
```bash
curl -H "X-User-Roles: operator" \
  "http://command-center:8010/alerts/deliveries/history?status=failed&limit=20"

curl -X POST -H "X-User-Roles: operator" \
  "http://command-center:8010/alerts/deliveries/abc123/replay"
```

---

### Auto-Healing Rules

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/autoheal/rules` | GET | `operator` | List active autoheal rules |
| `/autoheal/clear_endpoint_cooldown` | POST | `admin` | Reset endpoint cooldown |

**Example:**
```bash
# View rules
curl -H "X-User-Roles: operator" \
  "http://command-center:8010/autoheal/rules"

# Clear cooldown for endpoint
curl -X POST -H "X-User-Roles: admin" \
  -H "Content-Type: application/json" \
  -d '{"endpoint_url": "https://api.example.com/webhooks"}' \
  "http://command-center:8010/autoheal/clear_endpoint_cooldown"
```

---

### Event Streaming (SSE)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/events/stream` | GET | `operator` | Server-Sent Events stream |
| `/events/audit` | GET | `operator` | 7-day event history |

**Example:**
```bash
# Stream real-time events
curl -N -H "X-User-Roles: operator" \
  "http://command-center:8010/events/stream"

# Get audit trail
curl -H "X-User-Roles: operator" \
  "http://command-center:8010/events/audit?limit=100"
```

---

### Anomaly Detection (Phase IX)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/anomalies/current` | GET | `operator` | Active anomalies |
| `/anomalies/{id}/triage` | POST | `operator` | Mark anomaly as triaged |

---

### Tenant Analytics (Phase IX)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/tenant_analytics/summary` | GET | `operator` | Per-tenant health scores |

---

## RBAC Model

Command Center enforces role-based access via the `X-User-Roles` header.

| Role | Permissions |
|------|-------------|
| **operator** | View deliveries, replay, view autoheal rules, view events |
| **admin** | All operator permissions + clear cooldowns, create autoheal rules |

**Swagger UI**: All endpoints now document the `X-User-Roles` header requirement.

**Example Denied:**
```bash
curl http://command-center:8010/alerts/deliveries/history
# {"detail": "Missing or invalid X-User-Roles header"}
```

---

## Deployment

### Docker (Standalone)

```bash
docker pull ghcr.io/your-org/aetherlink/command-center:main

docker run -d \
  --name command-center \
  -p 8010:8010 \
  -v $(pwd)/data:/app/data \
  -e LOG_LEVEL=info \
  ghcr.io/your-org/aetherlink/command-center:main
```

### Docker Compose

```yaml
version: '3.8'
services:
  command-center:
    image: ghcr.io/your-org/aetherlink/command-center:main
    ports:
      - "8010:8010"
    volumes:
      - ./data:/app/data
    environment:
      LOG_LEVEL: info
    healthcheck:
      test: ["CMD", "curl", "-f", "-H", "X-User-Roles: admin", "http://localhost:8010/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### Kubernetes (Helm)

```bash
# Add Helm chart repository (if hosted)
helm repo add aetherlink https://charts.aetherlink.io
helm repo update

# Install
helm install command-center ./helm/command-center \
  --set image.repository=ghcr.io/your-org/aetherlink/command-center \
  --set image.tag=main-abc1234 \
  --set ingress.enabled=true \
  --set ingress.host=command-center.yourdomain.com \
  --namespace production

# Upgrade
helm upgrade command-center ./helm/command-center \
  --set image.tag=main-def5678 \
  --reuse-values

# Rollback
helm rollback command-center 1
```

**Key Helm Values:**
```yaml
image:
  repository: ghcr.io/your-org/aetherlink/command-center
  tag: main-abc1234
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8010

ingress:
  enabled: true
  host: command-center.example.com
  tls: true

resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

persistence:
  enabled: true
  storageClass: standard
  size: 10Gi
```

---

## CI/CD Pipeline

**Workflow:** [`.github/workflows/command-center-ci.yml`](../.github/workflows/command-center-ci.yml)

### Triggers
- Push to `main` → Build, test, push image
- Pull requests → Build, test (no push)
- Path filter: `services/command-center/**`

### Pipeline Stages

1. **Build** – Multi-stage Docker build
2. **Test (API)** – `pytest services/command-center/tests/`
3. **Test (E2E)** – Playwright UI tests
4. **Push** – Tag & push to GHCR
5. **Manifest Update** – Update Helm values with new SHA

**Image Tags:**
- `main` – Latest main branch
- `main-<short-sha>` – Specific commit (used in prod)
- `pr-<number>` – PR builds

**Example:**
```bash
# View CI-built images
docker pull ghcr.io/your-org/aetherlink/command-center:main-a42af86
```

---

## Observability

### Prometheus Metrics

Command Center exposes metrics at `/metrics`:

**Gauges:**
- `command_center_health` – Health status (1=healthy)
- `command_center_uptime_seconds` – Service uptime

**Counters:**
- `command_center_events_total{event_type, severity}` – Events published
- `command_center_api_requests_total{method, endpoint, status}` – API requests

**Example Queries:**
```promql
# Uptime in hours
command_center_uptime_seconds / 3600

# Total events
sum(command_center_events_total)

# API request rate (5m)
sum(rate(command_center_api_requests_total[5m]))

# Error rate
sum(rate(command_center_api_requests_total{status=~"5.."}[5m]))
  / sum(rate(command_center_api_requests_total[5m]))
```

### Prometheus Scrape Config

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'command-center'
    static_configs:
      - targets: ['command-center.default.svc.cluster.local:8010']
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 5s
```

**Environment-specific targets:**
- **Kubernetes:** `command-center.default.svc.cluster.local:8010`
- **Docker Compose:** `host.docker.internal:8010`
- **Local:** `localhost:8010`

### Grafana Dashboard

**Import:** [`observability/grafana/command-center-dashboard.json`](../observability/grafana/command-center-dashboard.json)

**Panels:**
1. Service Health (gauge)
2. Uptime (hours)
3. Total Events
4. API Request Rate (5m)
5. Events by Type (graph)
6. HTTP Status Codes (pie)
7. Prometheus Scrape Status

**Quick Start:**
1. Grafana → Dashboards → Import
2. Upload `command-center-dashboard.json`
3. Select Prometheus datasource

**Dashboard URL:** `http://grafana:3000/d/command-center`

### Logging

**Format:** Structured JSON to stdout

**Example Log Entry:**
```json
{
  "timestamp": "2025-11-05T14:32:01.234Z",
  "level": "INFO",
  "service": "command-center",
  "endpoint": "/alerts/deliveries/history",
  "method": "GET",
  "status": 200,
  "duration_ms": 42,
  "user_roles": ["operator"],
  "tenant_id": "acme-corp"
}
```

**Log Levels:**
- `DEBUG` – Verbose diagnostics
- `INFO` – Normal operations (default)
- `WARNING` – Recoverable issues
- `ERROR` – Failures requiring attention

**Set via environment:**
```bash
docker run -e LOG_LEVEL=debug command-center
```

---

## Testing

### API Tests (pytest)

```bash
cd services/command-center
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

**Test Coverage:**
- Health & meta endpoints
- RBAC enforcement
- Delivery history filtering
- Autoheal rule CRUD
- Event streaming

### E2E Tests (Playwright)

```bash
cd services/ui
npm install
npx playwright test

# Interactive mode
npx playwright test --ui

# Specific test
npx playwright test operator-dashboard
```

**Test Scenarios:**
- Role-based dashboard rendering
- Delivery history table & filters
- Event stream presence
- Replay button functionality
- Admin-only features hidden for operators

### CI Test Execution

Both test suites run automatically on:
- Every push to `main`
- Every pull request
- Manually via GitHub Actions

---

## Troubleshooting

### Service Won't Start

**Symptom:** Container exits immediately

**Check:**
```bash
# View logs
docker logs command-center

# Common issues:
# 1. Port 8010 already in use
docker ps | grep 8010

# 2. Permission error on /app/data
docker run --rm -it command-center ls -la /app/data

# 3. Missing dependencies
docker run --rm -it command-center pip list
```

**Solution:**
```bash
# Change port
docker run -p 8011:8010 command-center

# Fix volume permissions
chmod -R 755 ./data
```

---

### RBAC Errors (403)

**Symptom:** `{"detail": "Missing or invalid X-User-Roles header"}`

**Check:**
```bash
# Missing header
curl http://command-center:8010/alerts/deliveries/history
# ❌ 403

# Correct usage
curl -H "X-User-Roles: operator" \
  http://command-center:8010/alerts/deliveries/history
# ✅ 200
```

**Swagger UI:**
- Click "Authorize" button
- Enter role: `operator` or `admin`
- All requests will include header

---

### No Metrics in Prometheus

**Symptom:** Dashboard panels show "No Data"

**Check:**
```bash
# 1. Verify metrics endpoint
curl http://command-center:8010/metrics
# Should return Prometheus-formatted metrics

# 2. Check Prometheus targets
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="command-center")'
# Should show "up": true

# 3. Verify Prometheus can reach service
kubectl exec -it prometheus-pod -- wget -O- http://command-center:8010/metrics
```

**Solution:**
```bash
# Update Prometheus config
kubectl edit configmap prometheus-config
# Add/fix scrape_configs

# Reload Prometheus
curl -X POST http://prometheus:9090/-/reload
```

---

### Event Stream Disconnects

**Symptom:** SSE clients disconnect after 60 seconds

**Check:**
```bash
# Test SSE connection
curl -N -H "X-User-Roles: operator" \
  http://command-center:8010/events/stream

# Common causes:
# 1. Reverse proxy timeout (Nginx, ALB)
# 2. Kubernetes ingress timeout
# 3. Client timeout
```

**Solution (Nginx):**
```nginx
location /events/stream {
    proxy_pass http://command-center:8010;
    proxy_read_timeout 3600s;  # 1 hour
    proxy_buffering off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

**Solution (Kubernetes Ingress):**
```yaml
annotations:
  nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

---

### High Memory Usage

**Symptom:** Container OOMKilled or memory >512MB

**Check:**
```bash
# Current usage
docker stats command-center

# Event store size
du -sh ./data/autoheal/audit.jsonl
```

**Solution:**
```bash
# Rotate audit logs
docker exec command-center python -c "
from pathlib import Path
import shutil
audit = Path('/app/data/autoheal/audit.jsonl')
if audit.exists() and audit.stat().st_size > 100_000_000:  # 100MB
    shutil.move(audit, audit.with_suffix('.jsonl.old'))
    audit.touch()
"

# Increase memory limits
helm upgrade command-center ./helm/command-center \
  --set resources.limits.memory=1Gi
```

---

## Security Hardening (Future)

Current gaps for production hardening:

### 1. Secrets Management

**Current:** Environment variables in plain text
**Recommended:**
- Kubernetes Secrets
- HashiCorp Vault
- AWS Secrets Manager

**Example (Kubernetes):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: command-center-secrets
type: Opaque
data:
  database-password: <base64>
  api-key: <base64>
---
# In Deployment
envFrom:
  - secretRef:
      name: command-center-secrets
```

---

### 2. Per-Tenant RBAC

**Current:** Roles only (`operator`, `admin`)
**Recommended:** Add tenant isolation

**Example:**
```python
# Header: X-User-Roles: operator
# Header: X-User-Tenant: acme-corp

# Filter deliveries by tenant automatically
@router.get("/alerts/deliveries/history")
async def get_deliveries(
    tenant_id: str = Header(None, alias="X-User-Tenant"),
    user_roles: str = Header(..., alias="X-User-Roles")
):
    # Force filter to user's tenant unless admin
    if "admin" not in user_roles.split(","):
        # Override query tenant_id with user's tenant
        pass
```

---

### 3. Rate Limiting

**Current:** None
**Recommended:** Protect public endpoints

**Example (FastAPI Limiter):**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/events/stream")
@limiter.limit("10/minute")
async def stream_events():
    ...
```

---

## Runbook Checklist

### Daily Operations

- [ ] Check Grafana dashboard for anomalies
- [ ] Review failed deliveries: `/alerts/deliveries/history?status=failed`
- [ ] Verify event stream is active
- [ ] Check Prometheus alerts

### Weekly Maintenance

- [ ] Rotate audit logs if >100MB
- [ ] Review autoheal rule effectiveness
- [ ] Update Helm chart to latest image tag
- [ ] Run `kubectl top pod` to check resource usage

### Incident Response

1. **Service Down**
   - Check `/healthz` endpoint
   - Review pod logs: `kubectl logs -l app=command-center --tail=100`
   - Check Prometheus target health
   - Restart pod: `kubectl rollout restart deployment/command-center`

2. **High Error Rate**
   - Query Prometheus: `rate(command_center_api_requests_total{status=~"5.."}[5m])`
   - Check logs for stack traces
   - Review recent deployments: `helm history command-center`
   - Rollback if needed: `helm rollback command-center`

3. **Event Stream Issues**
   - Test SSE endpoint: `curl -N -H "X-User-Roles: operator" /events/stream`
   - Check ingress timeout settings
   - Review client-side reconnection logic

---

## Reference Links

- **API Docs (Swagger):** `http://command-center:8010/docs`
- **Grafana Dashboard:** `http://grafana:3000/d/command-center`
- **Prometheus Metrics:** `http://command-center:8010/metrics`
- **GitHub Repo:** `https://github.com/your-org/AetherLink`
- **CI/CD Workflow:** `.github/workflows/command-center-ci.yml`
- **Helm Chart:** `helm/command-center/`
- **Observability Guide:** [`observability/README.md`](../observability/README.md)

---

## Support

**Escalation Path:**
1. Check runbook troubleshooting section
2. Review Grafana dashboard & Prometheus alerts
3. Check `#command-center-ops` Slack channel
4. Page on-call engineer (PagerDuty)

**On-Call Rotation:** See PagerDuty schedule

---

**Document Version:** 1.0.0
**Last Review:** 2025-11-05
**Next Review:** 2025-12-05
