# Health Probe Integration for CRM Events Service

## Overview
The health probe (`health_probe.py`) provides readiness checking for Docker/K8s based on Prometheus metrics. It returns:
- **200 OK**: System healthy (skew ≤4x, consumers ≥2)
- **500 Error**: Pathological state detected (triggers container restart)

## Endpoints

### `/ready` - Readiness Probe
Use for Docker `healthcheck` or K8s `readinessProbe`.
- **200**: Service ready to handle traffic
- **500**: Service unhealthy (high skew or under-replicated)

### `/health` - Liveness Probe  
Use for Docker/K8s liveness checks.
- **200**: Service process is alive (always returns OK)

### `/status` - Debug Endpoint
Detailed health status for troubleshooting.
- **200**: Always returns full health details

## Health Checks

### 1. Hot-Key Skew Ratio
**Metric**: `kafka:group_skew_ratio{consumergroup="crm-events-sse"}`  
**Threshold**: `4.0x` (configurable via `SKEW_THRESHOLD`)  
**Unhealthy when**: Skew ratio >4x for sustained period  
**Action**: Container restart triggers consumer rebalance

### 2. Consumer Count
**Metric**: `kafka:group_consumer_count{consumergroup="crm-events-sse"}`  
**Threshold**: `2` (configurable via `MIN_CONSUMERS`)  
**Unhealthy when**: Active consumers <2  
**Action**: Container restart may trigger scaling or alert ops

## Docker Integration

### Option 1: Sidecar Container (Recommended)
Run health probe as separate container querying Prometheus:

```yaml
services:
  crm-events:
    build: ../pods/customer-ops
    container_name: aether-crm-events
    ports:
      - "9010:9010"
    environment:
      - KAFKA_BROKERS=kafka:9092
      - KAFKA_TOPIC=aetherlink.events
      - KAFKA_GROUP=crm-events-sse
    restart: unless-stopped
    networks:
      - aether-monitoring
    depends_on:
      - kafka
      - crm-events-health

  crm-events-health:
    build: ../pods/customer-ops
    container_name: aether-crm-events-health
    command: python health_probe.py
    ports:
      - "9011:9011"
    environment:
      - PROMETHEUS_URL=http://prometheus:9090
      - KAFKA_GROUP=crm-events-sse
      - SKEW_THRESHOLD=4.0
      - MIN_CONSUMERS=2
    restart: unless-stopped
    networks:
      - aether-monitoring
    depends_on:
      - prometheus
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9011/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

Then monitor health externally:
```bash
# Query readiness (for orchestrator decisions)
curl http://localhost:9011/ready

# Query detailed status (for debugging)
curl http://localhost:9011/status
```

### Option 2: Integrated Healthcheck (Direct)
If consumer service has `curl` available:

```yaml
services:
  crm-events:
    build: ../pods/customer-ops
    container_name: aether-crm-events
    ports:
      - "9010:9010"
    environment:
      - KAFKA_BROKERS=kafka:9092
      - KAFKA_TOPIC=aetherlink.events
      - KAFKA_GROUP=crm-events-sse
      - PROMETHEUS_URL=http://prometheus:9090
    restart: unless-stopped
    networks:
      - aether-monitoring
    depends_on:
      - kafka
      - prometheus
    healthcheck:
      test: |
        curl -f http://prometheus:9090/api/v1/query?query=kafka:group_skew_ratio{consumergroup="crm-events-sse"} | \
        python3 -c "import sys,json; d=json.load(sys.stdin); \
        skew=float(d['data']['result'][0]['value'][1]) if d['data']['result'] else 0; \
        sys.exit(0 if skew <= 4 else 1)"
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### Option 3: External Monitoring (Autoheal)
Use [autoheal](https://github.com/willfarrell/docker-autoheal) to restart based on external checks:

```yaml
services:
  autoheal:
    image: willfarrell/autoheal:latest
    container_name: autoheal
    restart: always
    environment:
      - AUTOHEAL_CONTAINER_LABEL=all
      - AUTOHEAL_INTERVAL=30
      - AUTOHEAL_START_PERIOD=60
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  crm-events:
    # ... (your existing config)
    labels:
      - "autoheal=true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://aether-crm-events-health:9011/ready"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## Kubernetes Integration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crm-events-sse
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: crm-events
        image: aetherlink/crm-events:latest
        ports:
        - containerPort: 9010
        env:
        - name: KAFKA_BROKERS
          value: "kafka:9092"
        - name: KAFKA_GROUP
          value: "crm-events-sse"
        
        # Liveness: Restart if process crashes
        livenessProbe:
          httpGet:
            path: /healthz
            port: 9010
          initialDelaySeconds: 10
          periodSeconds: 10
          failureThreshold: 3
        
        # Readiness: Remove from service if unhealthy
        readinessProbe:
          httpGet:
            path: /ready
            port: 9011  # Health probe sidecar
          initialDelaySeconds: 15
          periodSeconds: 30
          failureThreshold: 2
      
      - name: health-probe
        image: aetherlink/crm-events-health:latest
        ports:
        - containerPort: 9011
        env:
        - name: PROMETHEUS_URL
          value: "http://prometheus:9090"
        - name: KAFKA_GROUP
          value: "crm-events-sse"
        - name: SKEW_THRESHOLD
          value: "4.0"
        - name: MIN_CONSUMERS
          value: "2"
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus API endpoint |
| `KAFKA_GROUP` | `crm-events-sse` | Consumer group to monitor |
| `SKEW_THRESHOLD` | `4.0` | Max acceptable skew ratio (max/avg) |
| `MIN_CONSUMERS` | `2` | Minimum required active consumers |

### Tuning Recommendations

**Development/Testing**:
```bash
SKEW_THRESHOLD=6.0    # More lenient (allow higher skew)
MIN_CONSUMERS=1       # Allow single consumer
```

**Production**:
```bash
SKEW_THRESHOLD=4.0    # Strict (prevent hot-keys)
MIN_CONSUMERS=2       # Require failover capacity
```

**High-Volume**:
```bash
SKEW_THRESHOLD=3.0    # Very strict (perfect balance)
MIN_CONSUMERS=3       # Higher parallelism
```

## Testing

### Test Health Probe Locally
```bash
# Install dependencies
pip install -r requirements-health.txt

# Set environment
export PROMETHEUS_URL=http://localhost:9090
export KAFKA_GROUP=crm-events-sse

# Run probe
python health_probe.py

# In another terminal, test endpoints
curl http://localhost:9011/ready    # Should return 200 or 500
curl http://localhost:9011/health   # Always 200
curl http://localhost:9011/status   # Detailed JSON
```

### Simulate Unhealthy State
```bash
# Create hot-key skew (from monitoring drill)
docker stop aether-crm-events
docker exec -i kafka rpk topic produce aetherlink.events --key HOTKEY <<< '{"test":"hotkey"}' | head -400
docker start aether-crm-events

# Wait 30s, then check probe
curl http://localhost:9011/ready
# Should return 500 with: {"healthy": false, "message": "Hot-key skew high: 5.2x"}

# Resolve by scaling
docker compose up -d --scale crm-events=2

# Wait 3-5min for drain, then re-check
curl http://localhost:9011/ready
# Should return 200 with: {"healthy": true, "message": "System healthy"}
```

### Test Container Restart
```bash
# Add healthcheck to docker-compose.yml
# Set unhealthy-action: restart

# Trigger unhealthy state
# Watch container auto-restart after 3 failed checks (90s)
docker ps --filter "name=crm-events" --format "{{.Status}}"
```

## Monitoring & Observability

### Metrics to Add (Future)
Expose health check metrics via Prometheus exporter:

```python
from prometheus_client import Gauge, Counter, generate_latest

health_status = Gauge('crm_events_health_status', 'Overall health (1=healthy, 0=unhealthy)')
skew_ratio = Gauge('crm_events_health_skew_ratio', 'Current skew ratio from health check')
consumer_count = Gauge('crm_events_health_consumer_count', 'Consumer count from health check')
health_check_errors = Counter('crm_events_health_check_errors', 'Failed health checks')

@app.route('/metrics')
def metrics():
    is_healthy, status = check_health()
    health_status.set(1 if is_healthy else 0)
    if 'skew_ratio' in status['checks']:
        skew_ratio.set(status['checks']['skew_ratio']['value'] or 0)
    if 'consumer_count' in status['checks']:
        consumer_count.set(status['checks']['consumer_count']['value'] or 0)
    return Response(generate_latest(), mimetype='text/plain')
```

### Grafana Panel
Add panel showing health check history:

```promql
# Health status over time (1=healthy, 0=unhealthy)
crm_events_health_status

# Health check failures rate
rate(crm_events_health_check_errors[5m])
```

## Troubleshooting

### Health Probe Returns 500 (Unhealthy)
1. Check detailed status: `curl http://localhost:9011/status`
2. Identify failing check (skew_ratio or consumer_count)
3. Follow runbook: `monitoring/docs/RUNBOOK_HOTKEY_SKEW.md`

### Health Probe Returns 200 but System Still Slow
Health probe only checks skew and consumer count. Other issues:
- High latency: Check consumer processing time
- Network issues: Check Kafka broker connectivity
- Resource exhaustion: Check CPU/memory via `docker stats`

### Health Probe Not Available (Connection Refused)
1. Check service is running: `docker ps --filter name=health`
2. Check logs: `docker logs aether-crm-events-health`
3. Verify Prometheus connectivity: `curl http://prometheus:9090/-/healthy`

### False Positives (Restarts When Healthy)
1. Increase thresholds: `SKEW_THRESHOLD=5.0` or `MIN_CONSUMERS=1`
2. Increase retry count in healthcheck: `retries: 5`
3. Increase interval: `interval: 60s` (reduce check frequency)

## Best Practices

### DO ✅
- Use **sidecar pattern** (separate health container)
- Set **start_period** to allow service initialization
- Use **liveness** for process health, **readiness** for traffic routing
- Monitor health check metrics in Grafana
- Document threshold tuning in runbooks

### DON'T ❌
- Don't set `MIN_CONSUMERS=1` in production (no failover)
- Don't use aggressive intervals (<30s) on high-load systems
- Don't restart on transient issues (use `retries: 3+`)
- Don't check external dependencies in liveness (only process health)
- Don't block health endpoint on slow operations

## References
- **Runbook**: `monitoring/docs/RUNBOOK_HOTKEY_SKEW.md`
- **Recording Rules**: `monitoring/prometheus-crm-events-rules.yml`
- **One-Liners**: `monitoring/docs/ONE_LINER_FIXES.md`
- **Docker Healthcheck Docs**: https://docs.docker.com/engine/reference/builder/#healthcheck
- **K8s Probes**: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

---

**Created**: 2025-11-02  
**Maintainer**: DevOps Team  
**Status**: Production-ready auto-healing capability
