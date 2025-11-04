# Runbook: Hot-Key Skew Detection & Remediation

## Alert Trigger
**Alert Name**: `CrmEventsHotKeySkewHigh`
**Condition**: Skew ratio (max partition lag / avg partition lag) > 4x for 12 minutes
**Severity**: Warning
**Team**: CRM

## What This Means
One partition is accumulating significantly more lag than others, indicating:
- **Hot-key problem**: Messages with the same key are routing to a single partition
- **Unbalanced consumption**: One partition is slower or stuck
- **Key distribution issue**: Hashing strategy is creating hot-spots

## Triage (60 seconds)

### 1. Identify the hottest partition
**Dashboard**: http://localhost:3000/d/crm-events-pipeline

- **Panel 17** (Per-Partition Lag): Look for partition with highest lag
- **Panel 19** (Hot-Key Skew Ratio): Check current skew value
- Record which partition has the spike

### 2. Verify consumer health
- **Panel 18** (Consumer Group Size): Should show ≥2 (green)
- If showing 1 (yellow) or 0 (red): Consumer scaling issue, not hot-key
- If showing 2+ but still skewed: True hot-key problem

### 3. Confirm consumption is active
- **Panel 13** (Consumer Lag Sum): Should be decreasing or stable
- **Panel 6** (Messages/sec): Should show >0 consumption rate
- If consumption = 0: Check for consumer stuck/crashed

## Quick Diagnosis Commands

```powershell
# Check current partition lag distribution
curl.exe -s http://localhost:9308/metrics | findstr "kafka_consumergroup_lag{consumergroup=\`"crm-events-sse\`""

# Check consumer group status
docker exec kafka rpk group describe crm-events-sse

# Check consumer logs for errors
docker logs aether-crm-events --tail 50 --follow

# Query skew ratio in Prometheus
# Navigate to: http://localhost:9090/graph
# Query: kafka:group_skew_ratio{consumergroup="crm-events-sse"}
```

## Remediation (5-10 minutes)

### Option 1: Scale consumers (immediate relief)
If Panel 18 shows <2 consumers:

```powershell
# Scale to 2 replicas for balanced consumption
docker compose up -d --scale crm-events=2
```

If already at 2 consumers but still skewed, temporarily boost:

```powershell
# Temporarily scale to 3 replicas to drain faster
docker compose up -d --scale crm-events=3

# Wait 90 seconds for rebalance and drain
Start-Sleep -Seconds 90

# Scale back to 2 for steady state
docker compose up -d --scale crm-events=2
```

### Option 2: Force consumer rebalance
If consumers are stuck on wrong partitions:

```powershell
# Restart consumers to trigger rebalance
docker restart aether-crm-events

# Wait 30 seconds for reconnection
Start-Sleep -Seconds 30

# Verify rebalance completed
docker exec kafka rpk group describe crm-events-sse
```

### Option 3: Investigate message key strategy
If hot-key persists after scaling:

1. **Sample messages from hot partition**:
   ```powershell
   # Consume from specific partition to see keys
   docker exec kafka rpk topic consume aetherlink.events --partition 2 --num 10
   ```

2. **Common hot-key patterns**:
   - All messages using same `TenantId` (multi-tenant skew)
   - All messages using same `JobId` (batch processing)
   - Sequential keys causing hash collisions

3. **Key strategy fixes**:
   - **Add randomness**: Use composite key `{TenantId}:{UUID}`
   - **Salt keys**: Append random suffix for high-volume tenants
   - **Round-robin**: Use `null` key for partition round-robin (if ordering not required)

### Option 4: Increase partition count (long-term fix)
If hot-key is persistent and legitimate (e.g., high-volume tenant):

```powershell
# WARNING: Requires producer coordination and rebalancing
# 1. Increase partitions (existing messages stay in old partitions)
docker exec kafka rpk topic add-partitions aetherlink.events --num 6

# 2. Monitor lag drain on old partitions
# 3. Once drained, new messages will distribute across all 6 partitions

# Note: Partition count cannot be decreased, plan carefully
```

## Verification (3-5 minutes)

### Success Criteria
✅ **Panel 19**: Skew ratio drops below 2x (green)
✅ **Panel 17**: Lag distributed evenly across partitions
✅ **Panel 18**: 2+ consumers active (green)
✅ **Panel 13**: Total lag decreasing steadily
✅ **Alert**: `CrmEventsHotKeySkewHigh` auto-resolves after 12m below threshold

### Monitoring Commands
```powershell
# Watch skew ratio live
while ($true) {
    $skew = (curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_skew_ratio{consumergroup='crm-events-sse'}" | ConvertFrom-Json).data.result[0].value[1]
    Write-Host "Skew: $([math]::Round($skew, 2))x" -ForegroundColor $(if($skew -gt 4){'Red'}elseif($skew -gt 2){'Yellow'}else{'Green'})
    Start-Sleep -Seconds 10
}

# Watch partition lag distribution
while ($true) {
    curl.exe -s http://localhost:9308/metrics | findstr "kafka_consumergroup_lag{consumergroup=\`"crm-events-sse\`""
    Start-Sleep -Seconds 10
}
```

## Escalation

### If skew persists after remediation (>30 minutes)
1. **Check Kafka broker health**: One broker may be slow/degraded
   ```powershell
   docker exec kafka rpk cluster health
   docker logs kafka --tail 100
   ```

2. **Check for large messages**: One partition may have oversized messages
   ```powershell
   # Check message sizes
   docker exec kafka rpk topic consume aetherlink.events --partition 2 --num 5 --format '%k %v\n' | Measure-Object -Line
   ```

3. **Review producer**: Producer may be stuck sending to same partition
   - Check CRM API outbox publisher logs
   - Verify message key generation logic

### If consumer crashes during rebalance
1. **Check resource limits**: OOM, CPU throttling
   ```powershell
   docker stats aether-crm-events --no-stream
   ```

2. **Review consumer error logs**:
   ```powershell
   docker logs aether-crm-events --tail 200 | findstr /i "error|exception|rebalance"
   ```

3. **Fallback**: Scale back to 1 consumer and investigate
   ```powershell
   docker compose up -d --scale crm-events=1
   ```

## Prevention

### Short-term
- Set consumer count to **2 replicas** as baseline (failover + parallelism)
- Monitor Panel 19 weekly for trending skew increases

### Long-term
- Implement composite keys: `{TenantId}:{EventType}:{UUID}`
- Add salting for high-volume tenants (detected via telemetry)
- Consider partition count increase if consistent >4x skew
- Set up auto-scaling based on `kafka:group_lag_sum` threshold

## Related Alerts
- **CrmEventsPartitionStuck**: Lag increasing with no consumption
- **CrmEventsUnderReplicatedConsumers**: <2 active members
- **CrmEventsConsumerLagHigh**: Total lag >500 messages

## References
- **Dashboard**: http://localhost:3000/d/crm-events-pipeline
- **Prometheus Alerts**: http://localhost:9090/alerts
- **Kafka Metrics**: http://localhost:9308/metrics
- **Recording Rules**: `monitoring/prometheus-crm-events-rules.yml` (line ~185)
- **Lag Monitoring Guide**: `monitoring/docs/LAG_CAPACITY_MONITORING.md`

---

## Resolution Checklist (≤5 min)

**Use this checklist to confirm full resolution before closing the incident:**

- [ ] **Panel 18**: Shows ≥2 consumers (GREEN status)
- [ ] **Panel 13**: Lag trending ↓ (total lag decreasing over time)
- [ ] **Panel 17**: Lag balanced across partitions (no single partition >2x others)
- [ ] **Panel 19**: Skew ratio <2x (GREEN status)
- [ ] **Alert**: `CrmEventsHotKeySkewHigh` auto-resolved (check http://localhost:9090/alerts)
- [ ] **Related Alerts**: No active `PartitionStuck` or `UnderReplicated` alerts
- [ ] **Optional**: Add 30-minute silence if doing planned tests to avoid alert noise

**If all boxes checked**: Incident resolved. Document any hot-key patterns found for future prevention.

**If not resolved after 30 minutes**: Escalate to team lead. Consider increasing partition count or investigating message key strategy.

---

---

## ✅ Production Readiness Checklist

**Before deploying to production, verify all items:**

### Health Probe Endpoints
- [ ] `GET /health` → Always returns 200 (liveness probe)
- [ ] `GET /status` → Returns JSON with `window_minutes`, `skew_threshold`, `min_consumers`
- [ ] `GET /metrics` → Exposes `health_probe_checks_total`, `health_probe_status`, `health_probe_duration_seconds`
- [ ] `GET /ready` → Returns 200 when skew≤4 AND consumers≥2; returns 500 otherwise

### Windowed Queries (Anti-Flapping)
- [ ] Skew check uses: `max_over_time(kafka:group_skew_ratio{consumergroup="crm-events-sse"}[5m])`
- [ ] Consumer check uses: `min_over_time(kafka:group_consumer_count{consumergroup="crm-events-sse"}[5m])`

### Safety Configuration
- [ ] `PROM_TIMEOUT_MS=1500` configured (request timeout)
- [ ] `PROM_RETRIES=2` configured (retry count)
- [ ] `WINDOW_MINUTES=5` configured (query window)

### Docker Integration
- [ ] Consumer healthcheck points to `http://crm-events-health:9011/ready`
- [ ] Health probe container has `restart: unless-stopped`
- [ ] Health probe exposed only to internal network (no host port mapping)

### Alertmanager Configuration
- [ ] Inhibition rule configured: `CrmEventsServiceDown` inhibits `CrmEventsUnderReplicatedConsumers`
- [ ] Alerts have clean labels: `team=crm`, `service=crm-events-sse`, `product=aetherlink`

### Grafana Dashboard
- [ ] Panel 18 uses recording rule: `kafka:group_consumer_count{consumergroup="crm-events-sse"}`
- [ ] Panel 19 uses recording rule: `kafka:group_skew_ratio{consumergroup="crm-events-sse"}`
- [ ] Dashboard auto-provisions on Grafana startup (no manual import needed)

### Documentation
- [ ] Health probe integration guide exists: `monitoring/docs/HEALTH_PROBE_INTEGRATION.md`
- [ ] Recording rules documented: `monitoring/prometheus-crm-events-rules.yml`
- [ ] This runbook is accessible to on-call team

---

## 🚦 90-Second Smoke Test

**Test the complete health probe cycle: healthy → unhealthy → healthy**

```powershell
# 0) Baseline - Expect 200 (healthy)
curl -i http://localhost:9011/ready

# Expected output:
# HTTP/1.1 200 OK
# {"status": "healthy", "checks": [...]}

# 1) Force unhealthy state - Drop consumers below threshold
docker stop aether-crm-events
Start-Sleep -Seconds 15

# Check status - Expect 500 after window kicks in (may take up to 5 minutes for windowed query)
curl -i http://localhost:9011/ready

# Expected output:
# HTTP/1.1 500 INTERNAL SERVER ERROR
# {"status": "unhealthy", "reason": "consumer_count check failed", ...}

# 2) Restore and verify recovery
docker start aether-crm-events
Start-Sleep -Seconds 15

# Check status - Expect 200 (healthy again)
curl -i http://localhost:9011/ready

# Expected output:
# HTTP/1.1 200 OK
# {"status": "healthy", "checks": [...]}
```

**✅ Smoke test passes if**: All three curl commands return expected status codes

---

## 🧪 Hot-Key Skew Drill (Windowed Logic Proof)

**Test that windowed queries prevent flapping on transient spikes:**

```powershell
# 1) Accumulate hot-key skew (300 messages to single partition)
$evt = '{"Type":"JobCreated","TenantId":"00000000-0000-0000-0000-000000000001","HotKey":"TESTKEY","Ts":"' + (Get-Date -Format o) + '"}'
1..300 | ForEach-Object {
    $evt | docker exec -i kafka rpk topic produce --key TESTKEY aetherlink.events | Out-Null
}

# 2) Immediately check health probe (may still be 200 until 5m window sustains >4x)
curl -i http://localhost:9011/ready

# 3) Watch status every 30 seconds for 5 minutes (until windowed max_over_time crosses threshold)
for ($i=0; $i -lt 10; $i++) {
    Write-Host "`n=== Check $($i+1) at $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Cyan
    $status = curl -s http://localhost:9011/status | ConvertFrom-Json
    Write-Host "Status: $($status.status)"
    Write-Host "Skew: $($status.checks[0].value) (threshold: $($status.checks[0].threshold))"
    Write-Host "Consumers: $($status.checks[1].value) (threshold: $($status.checks[1].threshold))"
    Start-Sleep -Seconds 30
}

# 4) Verify alert fired in Prometheus
Start-Process "http://localhost:9090/alerts?search=CrmEventsHotKeySkewHigh"

# 5) Verify lag visible in Grafana Panel 17
Start-Process "http://localhost:3000/d/crm-events-pipeline"

# 6) Wait for consumers to drain (watch Panel 13 - Consumer Lag Sum)
Write-Host "`nMonitoring lag drain..." -ForegroundColor Yellow
Write-Host "Open Grafana Panel 13 and watch lag decrease to 0"
Write-Host "Once drained, health probe should return to 200"
```

**✅ Drill passes if**:
- Probe remains 200 (healthy) for ~5 minutes despite skew spike
- Probe transitions to 500 (unhealthy) after windowed query sustains >4x skew
- Alert `CrmEventsHotKeySkewHigh` fires in Prometheus
- Panel 17 shows unbalanced partition lag
- Probe returns to 200 after consumers drain backlog

---

## 🛡️ Production Configuration Recommendations

### Network Security
```yaml
# In docker-compose.yml
crm-events-health:
  expose:
    - "9011"  # Internal only - no ports: mapping
  # Do NOT expose to host:
  # ports:
  #   - "9011:9011"  # REMOVE THIS
```

### Resource Limits
```yaml
crm-events-health:
  deploy:
    resources:
      limits:
        cpus: "0.10"
        memory: 64M
      reservations:
        cpus: "0.05"
        memory: 32M
```

### JSON Logging Integration
```powershell
# Stream JSON logs to file for aggregation
docker logs aether-crm-events-health --follow 2>&1 | Tee-Object -FilePath logs/health-probe.jsonl

# Query logs with jq
Get-Content logs/health-probe.jsonl | jq 'select(.event=="health_check_failed")'
```

### Scaling Considerations
```yaml
# If you need multiple consumer instances:
services:
  crm-events-health:
    # REMOVE container_name for auto-scaling
    # container_name: aether-crm-events-health  # <-- DELETE THIS

  crm-events:
    # REMOVE container_name for auto-scaling
    # container_name: aether-crm-events  # <-- DELETE THIS

# Then scale:
# docker compose up -d --scale crm-events=3 --scale crm-events-health=1
```

---

## 🧰 Optional: Grafana Panels for Probe Quality

**Add these panels to monitor the health probe itself:**

### Panel: Probe Status (Stat)
```promql
health_probe_status
```
- Thresholds: 0=red (unhealthy), 1=green (healthy)
- Display: Big number with color background

### Panel: Unhealthy Rate (Time Series)
```promql
rate(health_probe_checks_total{status="unhealthy"}[5m])
```
- Shows frequency of unhealthy checks
- Alert if sustained >0.1 (probe flapping)

### Panel: Check P95 Latency (Time Series)
```promql
histogram_quantile(0.95, rate(health_probe_duration_seconds_bucket[5m]))
```
- Shows 95th percentile check duration
- Alert if >2s (Prometheus slow)

### Panel: Failures by Reason (Bar Gauge)
```promql
sum(rate(health_probe_failures_total[5m])) by (reason)
```
- Shows breakdown: timeout, connection, parse
- Helps diagnose probe issues

---

## 🧯 Emergency Rollback

**If health probe causes issues, quick rollback:**

```powershell
# 1) Revert probe changes
cd C:\Users\jonmi\OneDrive\Documents\AetherLink
git checkout -- pods/customer-ops/health_probe.py
git checkout -- pods/customer-ops/requirements-health.txt

# 2) Disable consumer healthcheck temporarily
# Edit docker-compose.yml - comment out healthcheck section:
#   healthcheck:
#     test: ["CMD", "curl", "-fsS", "http://crm-events-health:9011/ready"]
#     # ... rest of config

# 3) Restart containers
cd monitoring
docker compose up -d

# 4) Verify consumer is running (no healthcheck)
docker ps --filter name=crm-events
docker logs aether-crm-events --tail 20
```

---

**Last Updated**: 2025-11-03
**Maintainer**: DevOps Team
**Incident Playbook**: Follow this runbook for all `CrmEventsHotKeySkewHigh` alerts
