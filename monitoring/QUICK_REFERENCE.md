# 🎯 Quick Reference - CRM Events Monitoring

## 🚀 Deployment (30 seconds)

```powershell
cd C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring
docker compose up -d
```

## 🔍 Health Check (10 seconds)

```powershell
curl http://localhost:9011/ready      # 200=healthy, 500=unhealthy
curl http://localhost:9011/status     # Detailed JSON
```

## 📊 Dashboards

| URL | Purpose |
|-----|---------|
| http://localhost:3000/d/crm-events-pipeline | Main dashboard (19 panels) |
| http://localhost:9090/alerts | Active alerts |
| http://localhost:9093 | Alertmanager |
| http://localhost:9011/metrics | Health probe metrics |

## 🚨 Key Alerts

| Alert | Trigger | Action |
|-------|---------|--------|
| **CrmEventsHotKeySkewHigh** | Skew >4x for 12m | Check Panel 17 (partition lag) |
| **CrmEventsUnderReplicated** | Consumers <2 for 7m | Scale up consumers |
| **CrmEventsPartitionStuck** | No consumption 10m | Restart consumers |
| **CrmEventsServiceDown** | No heartbeat 5m | Check container logs |

## 🧰 Key Commands

```powershell
# Check consumer health
docker logs aether-crm-events --tail 50

# Check health probe
docker logs aether-crm-events-health --tail 20

# View Prometheus metrics
curl http://localhost:9308/metrics | findstr "kafka_consumergroup_lag"

# Describe consumer group
docker exec kafka rpk group describe crm-events-sse

# Watch health status
while ($true) { curl -s http://localhost:9011/status | ConvertFrom-Json | ConvertTo-Json; Start-Sleep 5 }
```

## 📈 Key Panels

| Panel | Metric | What to Look For |
|-------|--------|------------------|
| **13** | Consumer Lag Sum | Should trend ↓ (draining) |
| **17** | Per-Partition Lag | Should be balanced (<2x diff) |
| **18** | Consumer Count | Should show ≥2 (green) |
| **19** | Skew Ratio | Should be <2x (green) |

## 🔧 Troubleshooting

### Probe returns 500 (unhealthy)
```powershell
# 1. Check what's failing
curl http://localhost:9011/status

# 2. If skew >4x → Hot-key issue
#    See: monitoring/docs/RUNBOOK_HOTKEY_SKEW.md

# 3. If consumers <2 → Scale issue
docker compose up -d --scale crm-events=2
```

### Alert fires but system looks fine
```powershell
# Check if alert is sustained (not flapping)
# Navigate to: http://localhost:9090/alerts
# Look at "Active Since" timestamp
# If <5 minutes → May be transient spike (windowed queries will handle)
```

### Container keeps restarting
```powershell
# Check health probe logs
docker logs aether-crm-events-health

# Temporarily disable healthcheck
# Edit docker-compose.yml, comment out healthcheck section
docker compose up -d
```

## 🧪 Testing

### 90-Second Smoke Test
```powershell
# 1. Baseline
curl -i http://localhost:9011/ready  # Expect 200

# 2. Force unhealthy
docker stop aether-crm-events
Start-Sleep -Seconds 15
curl -i http://localhost:9011/ready  # Expect 500 (after 5m window)

# 3. Recover
docker start aether-crm-events
Start-Sleep -Seconds 15
curl -i http://localhost:9011/ready  # Expect 200
```

### Hot-Key Skew Drill
```powershell
# Produce 300 messages to hot-key
$evt = '{"Type":"Test","Key":"HOTKEY"}'
1..300 | % { $evt | docker exec -i kafka rpk topic produce --key HOTKEY aetherlink.events }

# Watch Panel 17 for skew
# Open: http://localhost:3000/d/crm-events-pipeline

# Wait 12 minutes for alert
# Open: http://localhost:9090/alerts
```

## 📖 Documentation

| File | Purpose | Lines |
|------|---------|-------|
| **PROD_READY.md** | Production certification | 450+ |
| **RUNBOOK_HOTKEY_SKEW.md** | Incident response | 420+ |
| **HEALTH_PROBE_INTEGRATION.md** | Integration guide | 450+ |
| **docker-compose-health-probe.yml** | Deployment patterns | 350+ |

## 🎯 Configuration Presets

### Development (Lenient)
```yaml
SKEW_THRESHOLD=6.0
MIN_CONSUMERS=1
WINDOW_MINUTES=3
PROM_TIMEOUT_MS=2000
```

### Production (Strict) ⭐ RECOMMENDED
```yaml
SKEW_THRESHOLD=4.0
MIN_CONSUMERS=2
WINDOW_MINUTES=5
PROM_TIMEOUT_MS=1500
PROM_RETRIES=2
```

### High-Volume (Very Strict)
```yaml
SKEW_THRESHOLD=3.0
MIN_CONSUMERS=3
WINDOW_MINUTES=10
PROM_TIMEOUT_MS=1000
```

## 🚨 Emergency Procedures

### Rollback Health Probe
```powershell
git checkout -- pods/customer-ops/health_probe.py
git checkout -- pods/customer-ops/requirements-health.txt
docker compose up -d
```

### Silence Flapping Alert (30m)
```
1. Navigate to: http://localhost:9090/alerts
2. Click "Silence" next to alert name
3. Duration: 30 minutes
4. Reason: "Planned test" or "Known issue"
```

### Scale Consumers Manually
```powershell
# Scale up
docker compose up -d --scale crm-events=3

# Scale down
docker compose up -d --scale crm-events=1
```

## 📞 On-Call Escalation

### Severity Levels

| Severity | Response Time | Action |
|----------|---------------|--------|
| **Critical** | 5 minutes | Page team lead |
| **Warning** | 15 minutes | Check dashboard, follow runbook |
| **Info** | Next business day | Log for review |

### Alert Severity Map

| Alert | Severity | Escalation |
|-------|----------|------------|
| ServiceDown | Critical | Immediate page |
| UnderReplicated | Warning | Follow runbook |
| HotKeySkewHigh | Warning | Follow runbook |
| PartitionStuck | Warning | Follow runbook |
| HighLag | Info | Monitor trend |

## ✅ Resolution Checklist

**Before closing incident, verify:**
- [ ] Panel 18: ≥2 consumers (GREEN)
- [ ] Panel 13: Lag trending ↓
- [ ] Panel 17: Lag balanced across partitions
- [ ] Panel 19: Skew ratio <2x (GREEN)
- [ ] Alert: Auto-resolved in Prometheus
- [ ] No active related alerts
- [ ] 30min silence added if doing tests

## 🎓 Training Resources

1. **Read First**: `PROD_READY.md` (this file)
2. **Practice**: Run 90-second smoke test
3. **Drill**: Hot-key skew scenario (15 min)
4. **Reference**: Bookmark dashboards + runbooks
5. **Review**: Attend post-incident reviews

---

**Quick Start**: `docker compose up -d` → `curl http://localhost:9011/ready` → Open http://localhost:3000/d/crm-events-pipeline

**Help**: See `monitoring/docs/RUNBOOK_HOTKEY_SKEW.md` or ask #aetherlink-monitoring
