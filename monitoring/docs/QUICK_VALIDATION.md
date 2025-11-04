# Quick Validation - Lag & Capacity Monitoring

**Date**: November 2, 2025  
**Status**: ✅ **ALL SYSTEMS OPERATIONAL**

---

## 🚀 Deployment Summary

### Components Deployed (in order)
1. ✅ **Kafka Exporter** - `aether-kafka-exporter` container (danielqsj/kafka-exporter:v1.7.0)
2. ✅ **Prometheus Scrape Job** - `kafka-exporter:9308` target added
3. ✅ **Recording Rules** - 4 new rules in `prometheus-crm-events-rules.yml`
4. ✅ **Alert Rules** - 2 new alerts (LagHigh, DrainEtaBreached)
5. ✅ **Grafana Panels** - 3 new panels in dashboard JSON (15 total)

---

## 🔍 Quick Validation Commands

### 1. Verify Kafka Exporter Running
```powershell
docker ps | findstr kafka-exporter
# Expected: aether-kafka-exporter container running
```

### 2. Check Lag Metrics from Exporter
```powershell
curl.exe -s http://localhost:9308/metrics | Select-String "kafka_consumergroup_lag{" | Select-Object -First 5
# Expected: kafka_consumergroup_lag{consumergroup="crm-events-sse",partition="X",...} <number>
```

### 3. Verify Prometheus Target UP
```powershell
Start-Process "http://localhost:9090/targets"
# Look for: kafka-exporter job, state=UP, last scrape <15s ago
```

### 4. Query Recording Rules
```powershell
# Total lag across all partitions
curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_lag_sum" | ConvertFrom-Json

# Consumer rate (may be 0 if idle)
curl.exe -s "http://localhost:9090/api/v1/query?query=crm_events:consumer_rate_1m" | ConvertFrom-Json

# Drain ETA (may be empty if rate is 0)
curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_drain_eta_seconds" | ConvertFrom-Json
```

### 5. Open Prometheus Graphs
```powershell
# Lag over time
Start-Process "http://localhost:9090/graph?g0.expr=kafka_consumergroup_lag&g0.tab=0&g0.range_input=15m"

# Lag sum (recording rule)
Start-Process "http://localhost:9090/graph?g0.expr=kafka%3Agroup_lag_sum&g0.tab=0&g0.range_input=15m"

# Consumer rate
Start-Process "http://localhost:9090/graph?g0.expr=crm_events%3Aconsumer_rate_1m&g0.tab=0&g0.range_input=15m"
```

### 6. Import Updated Grafana Dashboard
```powershell
# Open Grafana
Start-Process "http://localhost:3000"

# Manual steps:
# 1. Navigate: Dashboards → Import
# 2. Upload JSON file: monitoring/grafana/dashboards/crm_events_pipeline.json
# 3. Select data source: Prometheus
# 4. Click "Import"
# 5. Verify panels 13-15 visible:
#    - Panel 13: Consumer Lag (messages) - timeseries
#    - Panel 14: Drain ETA - stat
#    - Panel 15: Scale Hint (replicas) - stat
```

---

## 🧪 Optional: Lag Validation Drill

Run this to create artificial lag and verify alerts:

```powershell
# 1. Stop consumer
docker stop aether-crm-events

# 2. Publish 600 events (to trigger lag alert)
for ($i=1; $i -le 600; $i++) {
  $evt = @{Type="JobCreated"; TenantId="00000000-0000-0000-0000-000000000001"; Seq=$i; Ts=(Get-Date -Format "o")} | ConvertTo-Json -Compress
  echo $evt | docker exec -i kafka rpk topic produce aetherlink.events
  if ($i % 100 -eq 0) { Write-Host "Published $i events..." }
}

# 3. Wait 60 seconds for metrics to update
Write-Host "Waiting for lag to accumulate..." -ForegroundColor Yellow
Start-Sleep -Seconds 60

# 4. Check lag (should be ~600)
curl.exe -s http://localhost:9308/metrics | Select-String "kafka_consumergroup_lag{" | Select-Object -First 5

# 5. Check recording rule
curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_lag_sum"

# 6. Wait 5 more minutes for alert to fire
Write-Host "Waiting for CrmEventsConsumerLagHigh alert to fire (5m)..." -ForegroundColor Yellow
Start-Sleep -Seconds 300

# 7. Check alerts
Start-Process "http://localhost:9090/alerts"
# Look for: CrmEventsConsumerLagHigh (state=firing, lag >500)

# 8. Restart consumer and watch drain
docker start aether-crm-events
Start-Process "http://localhost:9090/graph?g0.expr=kafka%3Agroup_lag_sum&g0.tab=0&g0.range_input=15m"

# 9. Monitor until lag returns to 0 (should take ~3-5 minutes)
Write-Host "Watching lag drain..." -ForegroundColor Yellow
while ($true) {
  $lag = curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_lag_sum" | ConvertFrom-Json | Select-Object -ExpandProperty data | Select-Object -ExpandProperty result | Select-Object -First 1 | ForEach-Object { $_.value[1] }
  if ($lag -eq $null -or [int]$lag -eq 0) {
    Write-Host "✅ Lag drained to 0!" -ForegroundColor Green
    break
  }
  Write-Host "Current lag: $lag messages" -ForegroundColor Cyan
  Start-Sleep -Seconds 15
}

# 10. Verify alert auto-resolved
Start-Process "http://localhost:9090/alerts"
# Look for: CrmEventsConsumerLagHigh (state=resolved or inactive)
```

---

## 📊 Current Metrics (Baseline)

**As of November 2, 2025 23:00 CST**:

| Metric | Value | Status |
|--------|-------|--------|
| **Partition 0 Lag** | 0 messages | ✅ Healthy |
| **Partition 1 Lag** | 0 messages | ✅ Healthy |
| **Partition 2 Lag** | 39 messages | ⚠️ Minor lag |
| **Total Lag** (`kafka:group_lag_sum`) | 39 messages | ✅ Healthy (<500) |
| **Consumer Rate** (`crm_events:consumer_rate_1m`) | ~0 events/sec | ⚠️ Idle (no traffic) |
| **Drain ETA** (`kafka:group_drain_eta_seconds`) | N/A | ⚠️ Undefined (rate=0) |
| **Scale Hint** | 1 replica | ✅ Optimal |

**Notes**:
- Partition 2 has 39 messages of residual lag from previous validation drill
- Consumer is idle (rate ~0) because no new events are being published
- Drain ETA is undefined when consumer rate is 0 (division by near-zero)
- System is healthy and ready for production load

---

## 🎯 Success Criteria

### ✅ Deployment Success
- [x] Kafka Exporter container running
- [x] Prometheus scraping kafka-exporter:9308
- [x] Lag metrics visible in exporter endpoint
- [x] Recording rules created in prometheus-crm-events-rules.yml
- [x] Alert rules created (LagHigh, DrainEtaBreached)
- [x] Grafana dashboard JSON updated with 3 new panels

### ✅ Metrics Validation
- [x] `kafka_consumergroup_lag` exposed by exporter
- [x] `kafka:group_lag_sum` recording rule evaluating
- [x] `crm_events:consumer_rate_1m` recording rule created
- [x] `kafka:group_drain_eta_seconds` recording rule created
- [x] `crm_events:consumer_peak_capacity_1h` recording rule created

### 🔄 Pending Validation
- [ ] Import updated Grafana dashboard via UI
- [ ] Verify all 15 panels display correctly
- [ ] Run lag validation drill (stop consumer + 600 events)
- [ ] Verify CrmEventsConsumerLagHigh alert fires at >500 lag
- [ ] Verify alert auto-resolves after drain

---

## 📚 Documentation Created

1. **[LAG_CAPACITY_MONITORING.md](./LAG_CAPACITY_MONITORING.md)** (1,000+ lines)
   - Complete implementation guide
   - Metrics reference
   - Alert runbooks
   - Capacity planning guide
   - Scaling scenarios
   - Validation commands

2. **[QUICK_VALIDATION.md](./QUICK_VALIDATION.md)** (this file)
   - Quick validation checklist
   - Copy/paste commands
   - Current baseline metrics
   - Success criteria

---

## 🔗 Quick Links

### Prometheus
- **Targets**: http://localhost:9090/targets
- **Alerts**: http://localhost:9090/alerts
- **Rules**: http://localhost:9090/rules
- **Graph (Lag)**: http://localhost:9090/graph?g0.expr=kafka_consumergroup_lag&g0.tab=0&g0.range_input=15m
- **Graph (Lag Sum)**: http://localhost:9090/graph?g0.expr=kafka%3Agroup_lag_sum&g0.tab=0&g0.range_input=15m
- **Graph (Consumer Rate)**: http://localhost:9090/graph?g0.expr=crm_events%3Aconsumer_rate_1m&g0.tab=0&g0.range_input=15m
- **Graph (Drain ETA)**: http://localhost:9090/graph?g0.expr=kafka%3Agroup_drain_eta_seconds&g0.tab=0&g0.range_input=15m

### Services
- **Kafka Exporter Metrics**: http://localhost:9308/metrics
- **CRM Events Service**: http://localhost:9010
- **CRM Events Metrics**: http://localhost:9010/metrics
- **CRM Events Health**: http://localhost:9010/healthz
- **Grafana**: http://localhost:3000

### Documentation
- [VALIDATION_DRILL_RESULTS.md](./VALIDATION_DRILL_RESULTS.md) - Previous lag & recovery drill
- [OBSERVABILITY_STACK_COMPLETE.md](./OBSERVABILITY_STACK_COMPLETE.md) - Full monitoring stack
- [CRM_EVENTS_PRODUCTION_READY.md](./CRM_EVENTS_PRODUCTION_READY.md) - Service deployment guide
- [LAG_CAPACITY_MONITORING.md](./LAG_CAPACITY_MONITORING.md) - Lag monitoring implementation

---

## 🎉 Conclusion

**Status**: ✅ **DEPLOYMENT COMPLETE**

All components deployed successfully:
- Kafka Exporter running and exposing lag metrics
- Prometheus scraping and evaluating recording rules
- Alert rules active (will fire on lag >500 for 5m)
- Grafana dashboard updated with 3 new panels

**Next Step**: Import updated Grafana dashboard and run optional lag validation drill.

---

**Validated By**: GitHub Copilot  
**Date**: November 2, 2025  
**Version**: 1.0
