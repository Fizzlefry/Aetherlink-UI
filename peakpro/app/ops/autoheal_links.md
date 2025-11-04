# Autoheal Ops – Aetherlink Platform

**Auto-remediation monitoring and control for PeakPro CRM**

---

## 🔗 Quick Links

### Live Monitoring
- **Live Events Console**: [http://localhost:9009/console](http://localhost:9009/console)
  Real-time SSE stream with filtering (kind, alertname)

- **Grafana Dashboard**: [http://localhost:3000/d/autoheal](http://localhost:3000/d/autoheal)
  Autoheal metrics, heartbeat, action rates, failure trends

### API Endpoints
- **Health Check**: [http://localhost:9009/](http://localhost:9009/)
  Current status (enabled, dry_run, registered actions)

- **Audit Trail** (last 200): [http://localhost:9009/audit?n=200](http://localhost:9009/audit?n=200)
  JSON audit log with filtering capabilities

- **Metrics**: [http://localhost:9009/metrics](http://localhost:9009/metrics)
  Prometheus metrics endpoint

- **SSE Stream**: [http://localhost:9009/events](http://localhost:9009/events)
  Server-Sent Events stream (text/event-stream)

### Alertmanager
- **Alertmanager UI**: [http://localhost:9093](http://localhost:9093)
  Active alerts, silences, configuration

---

## 🛠️ Quick Commands

### PowerShell Helpers

```powershell
# Open all autoheal interfaces
.\monitoring\scripts\open-autoheal.ps1

# Full provision (setup + start services)
.\monitoring\scripts\autoheal-provision.ps1

# View formatted audit trail
.\monitoring\scripts\autoheal-audit.ps1

# Run smoke tests
.\monitoring\scripts\event-stream-smoke.ps1
```

---

## 📊 API Examples

### Audit Trail (Filtering)

```powershell
# Last 100 events
Invoke-RestMethod 'http://localhost:9009/audit?n=100'

# Filter by kind
Invoke-RestMethod 'http://localhost:9009/audit?kind=action_dry_run'
Invoke-RestMethod 'http://localhost:9009/audit?kind=action_fail'

# Filter by alert name
Invoke-RestMethod 'http://localhost:9009/audit?alertname=TcpEndpointDownFast'

# Filter by time (last 30 minutes)
$since = [DateTimeOffset]::Now.AddMinutes(-30).ToUnixTimeSeconds()
Invoke-RestMethod "http://localhost:9009/audit?since=$since"

# Text search (contains)
Invoke-RestMethod 'http://localhost:9009/audit?contains=cooldown'

# Combined filters
Invoke-RestMethod 'http://localhost:9009/audit?kind=decision_skip&contains=cooldown&n=50'
```

### Create Silence (Ack)

```powershell
# 30-minute silence
$labels = @{alertname="TcpEndpointDownFast"} | ConvertTo-Json -Compress
$encoded = [System.Uri]::EscapeDataString($labels)
Invoke-RestMethod "http://localhost:9009/ack?labels=$encoded&duration=30m"

# 2-hour silence
Invoke-RestMethod "http://localhost:9009/ack?labels=$encoded&duration=2h"

# 24-hour silence
Invoke-RestMethod "http://localhost:9009/ack?labels=$encoded&duration=24h"
```

### Health & Status

```powershell
# Check health
Invoke-RestMethod 'http://localhost:9009/' | ConvertTo-Json -Depth 3

# Check metrics
(Invoke-WebRequest 'http://localhost:9009/metrics').Content

# Prometheus query (heartbeat age)
Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=autoheal:heartbeat:age_seconds'

# Prometheus query (action fail rate)
Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=autoheal:action_fail_rate_15m'
```

---

## 📈 Key Metrics

### Prometheus Series (9 total)

| Metric | Type | Description |
|--------|------|-------------|
| `autoheal_enabled` | Gauge | Master kill switch (0=disabled, 1=enabled) |
| `autoheal_actions_total{alertname, result}` | Counter | Total actions by alert and result (ok, fail, skip) |
| `autoheal_action_last_timestamp{alertname}` | Gauge | Unix timestamp of last action per alert |
| `autoheal_cooldown_remaining_seconds{alertname}` | Gauge | Seconds remaining in cooldown (0=ready) |
| `autoheal_event_total{kind}` | Counter | Total events by kind (webhook_received, action_ok, etc.) |
| `autoheal_action_failures_total{alertname}` | Counter | Total failures per alert |
| `autoheal_last_event_timestamp` | Gauge | Unix timestamp of last event |

### Recording Rules (4 autoheal rules)

| Rule | Expression | Description |
|------|------------|-------------|
| `autoheal:cooldown_active` | `count(...) > 0` | Alerts currently in cooldown |
| `autoheal:actions:rate_5m` | `sum(rate(...[5m]))` | Actions per second (5m window) |
| `autoheal:heartbeat:age_seconds` | `time() - max(...)` | Seconds since last event |
| `autoheal:action_fail_rate_15m` | `sum(rate(...[15m]))` | Failure rate (15m window) |

### Alert Rules

| Alert | Condition | Description |
|-------|-----------|-------------|
| `AutohealNoEvents15m` | Heartbeat age > 900s for 10m | No events received (autoheal likely down) |
| `AutohealActionFailureSpike` | Fail rate > 0.2/s for 10m | Action failures spiking (investigate logs) |

---

## 🎯 Event Types

| Kind | Description | Example Fields |
|------|-------------|----------------|
| `webhook_received` | Alert webhook hit | `alerts: 1` |
| `decision_skip` | Action skipped | `reason: "cooldown"`, `alertname` |
| `action_dry_run` | Would execute (dry-run mode) | `cmd`, `alertname` |
| `action_ok` | Action executed successfully | `cmd`, `alertname`, `output` |
| `action_fail` | Action failed | `cmd`, `alertname`, `error` |
| `ack` | Silence created | `labels`, `duration`, `silence_id` |

---

## 🔧 Configuration

### Environment Variables

```yaml
AUTOHEAL_ENABLED: "false"              # Master kill switch
AUTOHEAL_DRY_RUN: "true"               # Safe mode (default)
AUTOHEAL_AUDIT_PATH: "/data/audit.jsonl"  # Persistent audit trail
AUTOHEAL_DEFAULT_COOLDOWN_SEC: "600"   # Default cooldown (10 minutes)
ALERTMANAGER_URL: "http://alertmanager:9093"
AUTOHEAL_PUBLIC_URL: "http://localhost:9009"
```

### Per-Alert Cooldowns

Configured in `monitoring/autoheal/main.py`:

```python
PER_ALERT_COOLDOWN_SEC = {
    "TcpEndpointDownFast": 600,
    "UptimeProbeFailing": 600,
    "CrmMetricsScrapeStale": 600,
}
```

### Registered Actions

Current remediation actions:

1. **TcpEndpointDownFast** → `docker restart crm-api`
2. **UptimeProbeFailing** → `docker restart crm-api`
3. **CrmMetricsScrapeStale** → `docker restart crm-api`

---

## 🚨 Alertmanager Routing

Autoheal health alerts (`Autoheal*`) are routed to `autoheal-notify` receiver:

```yaml
routes:
  - matchers:
      - alertname=~"Autoheal.*"
    receiver: autoheal-notify
    repeat_interval: 1h
```

---

## 📁 File Locations

- **Audit Trail**: `monitoring/data/autoheal/audit.jsonl` (persistent)
- **Source Code**: `monitoring/autoheal/main.py`, `monitoring/autoheal/audit.py`
- **Console HTML**: `monitoring/sse-console/index.html`
- **Scripts**: `monitoring/scripts/` (open-autoheal.ps1, autoheal-provision.ps1, etc.)
- **Docker Config**: `monitoring/docker-compose.yml` (autoheal service)
- **Prometheus Config**: `monitoring/prometheus-config.yml` (autoheal job + labels)
- **Alertmanager Config**: `monitoring/alertmanager.yml` (autoheal-notify receiver)

---

## 🧪 Testing

### Smoke Tests

```powershell
# Full validation suite (7 tests)
.\monitoring\scripts\event-stream-smoke.ps1

# Generate test alert
$body = @{
    alerts = @(
        @{
            status = "firing"
            labels = @{
                alertname = "TcpEndpointDownFast"
                service = "crm-api"
                instance = "crm-api:8000"
            }
            annotations = @{
                autoheal_action = "docker restart crm-api"
            }
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method POST -Uri 'http://localhost:9009/alert' `
    -ContentType 'application/json' -Body $body
```

---

## 📖 Related Documentation

- **Alerts Runbook**: `monitoring/docs/ALERTS_CRM_FINANCE.md`
- **SLO Burn-Rate**: `monitoring/docs/SLO_BURN_RATE.md`
- **AetherVision**: `monitoring/docs/AETHERVISION_PREDICTIVE.md`
- **Autoheal Design**: `monitoring/docs/AUTOHEAL.md`

---

**Last Updated**: 2025-11-02
**Owner**: Aetherlink Platform Team
**Project**: PeakPro CRM Ops
