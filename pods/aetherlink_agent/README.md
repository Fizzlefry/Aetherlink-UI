# AetherLink Command AI Agent

Autonomous monitoring and operations agent for AetherLink.

## Features

- **Health Score Monitoring**: Polls `aether:health_score:15m` every 60 seconds, logs warnings on consecutive low scores
- **Alertmanager Integration**: Receives webhook notifications, logs alerts, increments metrics
- **PromQL Proxy**: Execute instant and range queries against Prometheus
- **Action Stubs**: Placeholder for auto-remediation (restart, scale)
- **Prometheus Metrics**: Exposes custom counters for alerts and health checks

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROM_URL` | `http://prometheus:9090` | Prometheus base URL |
| `ALERTMANAGER_URL` | `http://alertmanager:9093` | Alertmanager base URL |
| `GRAFANA_URL` | `http://grafana:3000` | Grafana base URL |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Local Development

### Install Dependencies

```bash
cd pods/aetherlink_agent
pip install -r requirements.txt
```

### Run Locally

```bash
cd pods/aetherlink_agent/src
uvicorn app.main:app --reload --port 8080
```

### Test Endpoints

```bash
# Health check
curl -s http://localhost:8080/health | jq

# PromQL query
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"ql":"aether:health_score:15m"}' | jq

# Perform action (stub)
curl -s -X POST http://localhost:8080/act \
  -H "Content-Type: application/json" \
  -d '{"action":"restart_api","reason":"manual test"}' | jq

# Metrics
curl -s http://localhost:8080/metrics | grep aether_agent
```

## Docker

### Build Image

```bash
cd pods/aetherlink_agent
docker build -t aetherlink/agent:local .
```

### Run Container

```bash
docker run -d \
  --name aether-agent \
  -p 8088:8080 \
  -e PROM_URL=http://prometheus:9090 \
  -e LOG_LEVEL=INFO \
  aetherlink/agent:local
```

### Compose

See `monitoring/docker-compose.yml` for full stack integration.

```bash
cd monitoring
docker compose up -d aether-agent
docker compose logs -f aether-agent
```

## Endpoints

### `GET /health`

Returns service health and current health score monitoring status.

**Response:**
```json
{
  "ok": true,
  "health_score": 85.5,
  "consecutive_low": 0
}
```

### `GET /metrics`

Prometheus metrics endpoint.

**Custom Metrics:**
- `aether_agent_alerts_total{alertname, severity}` - Total alerts received
- `aether_agent_health_checks_total{status}` - Health checks performed (ok/low)

### `POST /query`

Execute instant PromQL query.

**Request:**
```json
{
  "ql": "aether:health_score:15m"
}
```

**Response:**
```json
{
  "value": 85.5,
  "query": "aether:health_score:15m"
}
```

### `POST /act`

Trigger operational action (currently stubs that log only).

**Request (restart):**
```json
{
  "action": "restart_api",
  "reason": "health score degradation"
}
```

**Request (scale):**
```json
{
  "action": "scale_up",
  "service": "customer-ops",
  "replicas": 3,
  "reason": "high load detected"
}
```

**Response:**
```json
{
  "accepted": true,
  "action": "restart_api",
  "details": {
    "action": "restart_api",
    "status": "logged",
    "reason": "health score degradation"
  }
}
```

### `POST /alertmanager`

Alertmanager webhook receiver.

**Request (Alertmanager sends this):**
```json
{
  "alerts": [
    {
      "labels": {
        "alertname": "HealthScoreDegradation",
        "severity": "warning",
        "tenant": "acme-corp"
      },
      "annotations": {
        "summary": "Health score below 60 for 15 minutes"
      },
      "startsAt": "2025-11-02T10:30:00Z",
      "status": "firing"
    }
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "alerts_processed": 1
}
```

## Background Tasks

### Health Check Loop (60s interval)

1. Queries `aether:health_score:15m` from Prometheus
2. Tracks consecutive low scores (< 60)
3. Logs warning if score is low twice in a row
4. Increments `aether_agent_health_checks_total{status="ok|low"}`

## Future Enhancements

- [ ] Implement real remediation actions (Docker API, kubectl)
- [ ] Grafana annotation API (mark incidents on dashboards)
- [ ] VIP tenant awareness (priority-based actions)
- [ ] Action cooldown/rate limiting
- [ ] Historical action audit log
- [ ] Slack/PagerDuty notifications
- [ ] ML-based anomaly detection

## Architecture

```
┌─────────────────┐
│   Prometheus    │◄──────┐
│   :9090         │       │ scrape /metrics
└─────────────────┘       │
         ▲                │
         │ query          │
         │                │
┌─────────────────┐       │
│ Alertmanager    │       │
│   :9093         │       │
└─────────────────┘       │
         │                │
         │ webhook        │
         ▼                │
┌─────────────────────────┴──┐
│  AetherLink Agent          │
│  :8080                     │
│                            │
│  • Health monitoring       │
│  • Alert processing        │
│  • Action execution        │
│  • Metrics exposure        │
└────────────────────────────┘
         │
         │ (future)
         ▼
┌─────────────────┐
│   Grafana       │
│   :3000         │
└─────────────────┘
```

## Logs

The agent logs all key events:

- Health score checks (every 60s)
- Low health score warnings
- Received alerts (compact format)
- Action executions (stubs)

**Example:**
```
2025-11-02 10:30:15 - app.main - INFO - Health score: 85.50
2025-11-02 10:31:15 - app.main - INFO - Health score: 52.30
2025-11-02 10:31:15 - app.main - INFO - ALERT: HealthScoreDegradation | severity=warning | tenant=acme-corp | summary='Health score below 60' | startsAt=2025-11-02T10:30:00Z
2025-11-02 10:32:15 - app.main - WARNING - HEALTH SCORE LOW: 48.20 (consecutive: 2)
2025-11-02 10:32:15 - app.actions.ops - WARNING - ACTION STUB: restart_api called - reason: health score degradation
```

## Monitoring the Agent

The agent exposes its own metrics at `/metrics`:

```promql
# Alert processing rate
rate(aether_agent_alerts_total[5m])

# Health check failures
rate(aether_agent_health_checks_total{status="low"}[5m])

# Agent uptime
process_start_time_seconds
```

## License

Internal use - AetherLink platform
