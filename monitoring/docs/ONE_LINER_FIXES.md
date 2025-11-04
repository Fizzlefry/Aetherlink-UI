# Quick Reference: One-Liner Fixes & Commands

## Instant Remediation Commands

### Scale to Green (Panel 18: Consumer Group Size)
```powershell
# Scale consumers to 2 replicas (baseline for failover)
docker compose up -d --scale crm-events=2
```

**When to use**: 
- Panel 18 shows 1 (yellow) or 0 (red)
- Alert `CrmEventsUnderReplicatedConsumers` is firing
- Need immediate failover capacity

**Expected outcome**:
- Panel 18 turns GREEN (2 members)
- Alert auto-resolves after 7m
- Lag drains faster (parallel consumption)

---

### Force Consumer Rebalance
```powershell
# Restart consumers to trigger partition rebalance
docker restart aether-crm-events
```

**When to use**:
- Consumers stuck on wrong partitions after scaling
- One consumer handling all 3 partitions (check `rpk group describe`)
- Panel 19 shows high skew despite 2+ consumers

**Expected outcome**:
- Kafka triggers consumer group rebalance
- Partitions redistributed across active members
- Takes ~30 seconds to complete

---

### Temporary Drain Boost (Hot Partition)
```powershell
# Temporarily scale to 3 replicas to drain faster
docker compose up -d --scale crm-events=3
Start-Sleep -Seconds 90
docker compose up -d --scale crm-events=2
```

**When to use**:
- Alert `CrmEventsHotKeySkewHigh` is firing
- Partition 2 has >300 lag
- Need to drain backlog quickly (emergency)

**Expected outcome**:
- 3 consumers share partition load
- Lag drains in ~90 seconds
- Scale back to 2 for steady state

---

## Monitoring Commands

### Watch Skew Ratio Live
```powershell
# Loop to monitor skew ratio with color-coded output
while ($true) {
    $raw = curl.exe -s "http://localhost:9090/api/v1/query?query=kafka:group_skew_ratio"
    $json = $raw | ConvertFrom-Json
    if ($json.data.result.Count -gt 0) {
        $skew = [math]::Round($json.data.result[0].value[1], 2)
        $color = if($skew -gt 4){'Red'}elseif($skew -gt 2){'Yellow'}else{'Green'}
        Write-Host "Skew: ${skew}x" -ForegroundColor $color
    } else {
        Write-Host "Skew: calculating..." -ForegroundColor Gray
    }
    Start-Sleep -Seconds 10
}
```

**Stop with**: `Ctrl+C`

---

### Watch Partition Lag Distribution
```powershell
# Loop to show lag by partition
while ($true) {
    Write-Host "`n$(Get-Date -Format 'HH:mm:ss') - Partition Lag:" -ForegroundColor Cyan
    curl.exe -s http://localhost:9308/metrics |  
        Select-String 'kafka_consumergroup_lag\{consumergroup="crm-events-sse"' | 
        ForEach-Object {
            if ($_ -match 'partition="(\d+)".*\}\s+(\d+)') {
                $p = $matches[1]; $lag = $matches[2]
                $color = if($lag -gt 100){'Red'}elseif($lag -gt 0){'Yellow'}else{'Green'}
                Write-Host "  Partition $p`: $lag" -ForegroundColor $color
            }
        }
    Start-Sleep -Seconds 10
}
```

**Stop with**: `Ctrl+C`

---

### Check Consumer Group Status
```powershell
# Show detailed consumer group info (partition assignment)
docker exec kafka rpk group describe crm-events-sse
```

**Output shows**:
- Active members (consumer IDs)
- Partition assignment per member
- Current offset vs high-water mark (lag)
- Consumer state (Stable, Rebalancing, Dead)

---

### Sample Messages from Hot Partition
```powershell
# Consume 10 messages from partition 2 to inspect keys
docker exec kafka rpk topic consume aetherlink.events --partition 2 --num 10
```

**Look for**:
- Repeated keys (e.g., same TenantId appearing multiple times)
- Pattern in keys (sequential, all same prefix)
- Large message sizes

---

## Validation Commands

### Verify Recording Rules Loaded
```powershell
# Check if new recording rules are evaluating
curl.exe "http://localhost:9090/api/v1/rules" | ConvertFrom-Json | 
    Select-Object -ExpandProperty data | 
    Select-Object -ExpandProperty groups | 
    Where-Object { $_.name -eq 'crm_events_lag_capacity' } | 
    Select-Object -ExpandProperty rules | 
    Select-Object record
```

**Expected output**:
```
record
------
crm_events:consumer_rate_1m
crm_events:consumer_peak_capacity_1h
kafka:group_lag_sum
kafka:group_drain_eta_seconds
kafka:group_partition_lag
kafka:group_skew_ratio
kafka:group_hottest_partition
```

---

### Query Skew Ratio Directly
```powershell
# Get current skew ratio value
$response = curl.exe -s 'http://localhost:9090/api/v1/query?query=kafka:group_skew_ratio{consumergroup="crm-events-sse"}'
$json = $response | ConvertFrom-Json
if ($json.data.result) {
    $skew = [math]::Round($json.data.result[0].value[1], 2)
    Write-Host "Current Skew: ${skew}x" -ForegroundColor Yellow
} else {
    Write-Host "Skew ratio not yet available (wait 30s after Prometheus restart)" -ForegroundColor Gray
}
```

---

### Check Alert Status
```powershell
# Show active/pending alerts
curl.exe "http://localhost:9090/api/v1/alerts" | ConvertFrom-Json | 
    Select-Object -ExpandProperty data | 
    Select-Object -ExpandProperty alerts | 
    Where-Object { $_.labels.alertname -match 'HotKey|UnderReplicated|PartitionStuck' } | 
    Select-Object @{N='Alert';E={$_.labels.alertname}}, state, activeAt
```

---

### Verify Panel 18 & 19 Metrics
```powershell
# Panel 18: Consumer Group Size
$members = curl.exe -s 'http://localhost:9090/api/v1/query?query=count(count%20by%20(memberid)%20(kafka_consumergroup_current_offset{consumergroup=%22crm-events-sse%22}))'
Write-Host "Consumer Group Size: Check above output"

# Panel 19: Hot-Key Skew Ratio  
$skew = curl.exe -s 'http://localhost:9090/api/v1/query?query=kafka:group_skew_ratio{consumergroup=%22crm-events-sse%22}'
Write-Host "Skew Ratio: Check above output"
```

---

## Dashboard Access

### Open All Monitoring Views
```powershell
# Open dashboard, alerts, and metrics in browser
Start-Process "http://localhost:3000/d/crm-events-pipeline"
Start-Process "http://localhost:9090/alerts"
Start-Process "http://localhost:9308/metrics"
```

---

## Troubleshooting Commands

### Check Kafka Broker Health
```powershell
# Verify Kafka cluster status
docker exec kafka rpk cluster health
docker exec kafka rpk cluster info
```

---

### Check Consumer Resource Usage
```powershell
# Show CPU, memory, network usage
docker stats aether-crm-events --no-stream
```

---

### Tail Consumer Logs
```powershell
# Follow consumer logs in real-time
docker logs aether-crm-events --tail 50 --follow
```

**Stop with**: `Ctrl+C`

---

### Check Prometheus Target Health
```powershell
# Verify all scrape targets are UP
curl.exe "http://localhost:9090/api/v1/targets" | ConvertFrom-Json | 
    Select-Object -ExpandProperty data | 
    Select-Object -ExpandProperty activeTargets | 
    Select-Object @{N='Job';E={$_.labels.job}}, health, lastError | 
    Format-Table -AutoSize
```

**Expected**: All targets show `health: up`

---

## Emergency Rollback

### Revert Recording Rules
```powershell
# If recording rules cause issues, restore previous version
git checkout monitoring/prometheus-crm-events-rules.yml
docker compose restart prometheus
```

---

### Revert Dashboard Changes
```powershell
# Restore previous dashboard
git checkout monitoring/grafana/dashboards/crm_events_pipeline.json
docker compose restart grafana
```

---

### Scale Down to Single Consumer
```powershell
# Fallback to 1 consumer if rebalancing causes crashes
docker compose up -d --scale crm-events=1
```

---

## Performance Tuning

### Increase Partition Count (Permanent Fix)
```powershell
# WARNING: Cannot be decreased, plan carefully
# Increases parallelism and reduces hot-key impact
docker exec kafka rpk topic add-partitions aetherlink.events --num 6

# Verify
docker exec kafka rpk topic describe aetherlink.events
```

**Note**: Existing messages stay in old partitions. Only new messages use new partitions.

---

### Check Message Sizes
```powershell
# Identify large messages that may slow consumption
docker exec kafka rpk topic consume aetherlink.events --num 20 --format '%k: %v\n' | 
    ForEach-Object { 
        $len = $_.Length
        if ($len -gt 1000) {
            Write-Host "Large message: $len bytes" -ForegroundColor Yellow
        }
    }
```

---

## Cheat Sheet Summary

| **Problem** | **Command** | **Panel/Alert** |
|-------------|-------------|-----------------|
| No consumers running | `docker compose up -d --scale crm-events=2` | Panel 18 (RED) |
| Single replica (no failover) | `docker compose up -d --scale crm-events=2` | Panel 18 (YELLOW) |
| Hot partition stuck | `docker compose up -d --scale crm-events=3; sleep 90; docker compose up -d --scale crm-events=2` | Panel 19 (RED) |
| Consumers stuck on wrong partitions | `docker restart aether-crm-events` | Panel 17 (uneven) |
| Alert: HotKeySkewHigh | Scale to 2+, check runbook | Panel 19 >4x |
| Alert: UnderReplicatedConsumers | Scale to 2 | Panel 18 <2 |
| Alert: PartitionStuck | Restart consumers, check logs | Panel 17 |
| View all alerts | `Start-Process http://localhost:9090/alerts` | - |
| View dashboard | `Start-Process http://localhost:3000/d/crm-events-pipeline` | - |

---

**Last Updated**: 2025-11-02  
**Maintainer**: DevOps Team  
**Related Docs**: 
- `RUNBOOK_HOTKEY_SKEW.md` - Detailed hot-key remediation
- `LAG_CAPACITY_MONITORING.md` - Architecture & capacity planning
- `QUICK_VALIDATION.md` - Validation checklist
