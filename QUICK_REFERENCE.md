# 🚀 Quick Reference Card - Enhanced Monitoring

## One-Command Quick Start
```powershell
.\scripts\start-monitoring.ps1
.\scripts\tenant-smoke-test.ps1
Start-Process "http://localhost:3000"
```

---

## 📊 Dashboard Files

| Dashboard | Panels | Gauges | File |
|-----------|--------|--------|------|
| **Original** | 11 | 1 | `monitoring/grafana-dashboard.json` |
| **Enhanced** ⭐ | 14 | 4 | `monitoring/grafana-dashboard-enhanced.json` |

### Enhanced Dashboard Adds:
1. **Answer Cache Hit Ratio** - Health proxy (🔴<30% 🟡30-60% 🟢>60%)
2. **Rerank Utilization %** - Cost signal (🟢<30% 🟡30-60% 🔴>60%)
3. **Low-Confidence Share** - Quality signal (🟢<10% 🟡10-20% 🔴>20%)

---

## 🚨 Alert Rules

| Count | Severity | Description |
|-------|----------|-------------|
| 3 | Info | Low priority notifications |
| 4 | Warning | Attention needed |
| 5 | Critical | Immediate action required |
| **12** | **TOTAL** | **All production-ready** |

### New Alerts ⭐
- `CacheEffectivenessDrop` (warning <30%)
- `CacheEffectivenessCritical` (critical <15%)
- `LowConfidenceSpike` (warning >20%)
- `LowConfidenceSpikeVIP` (critical >15%)

---

## 🔗 Access Points

| Service | URL | Login |
|---------|-----|-------|
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | - |
| API Metrics | http://localhost:8000/metrics | - |
| Enhanced Dashboard | http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced | admin/admin |

---

## ⚡ Common Commands

```powershell
# Stack Management
.\scripts\start-monitoring.ps1          # Start
.\scripts\start-monitoring.ps1 -Stop    # Stop
.\scripts\start-monitoring.ps1 -Restart # Restart
.\scripts\start-monitoring.ps1 -Logs    # View logs

# Testing
.\scripts\tenant-smoke-test.ps1                  # E2E test
.\scripts\quick-check-tenant-metrics.ps1         # Quick check
.\scripts\validate-quick-wins.ps1 -Strict        # Red team tests

# Prometheus
curl.exe -X POST http://localhost:9090/-/reload  # Hot reload alerts
Start-Process "http://localhost:9090/targets"    # Check targets
Start-Process "http://localhost:9090/alerts"     # View alerts

# Docker
docker ps | Select-String "aether"               # Check containers
docker logs aether-prom -f                       # Prom logs
docker logs aether-grafana -f                    # Grafana logs
```

---

## 📋 Import Enhanced Dashboard

### Method 1: Grafana UI (Recommended)
1. Open http://localhost:3000
2. Dashboards → Import → Upload JSON
3. Select `monitoring/grafana-dashboard-enhanced.json`
4. Click Import

### Method 2: Direct Link
- After import: http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced

---

## 🔍 Quick Verification

```powershell
# 1. Check services
docker ps | Select-String "aether"

# 2. Check metrics exist
curl.exe http://localhost:8000/metrics | Select-String "tenant=" | Select-Object -First 10

# 3. Check Prometheus scraping
curl.exe http://localhost:9090/api/v1/targets | ConvertFrom-Json

# 4. Check alerts loaded
curl.exe http://localhost:9090/api/v1/rules | ConvertFrom-Json

# 5. Open dashboard
Start-Process "http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced"
```

---

## 🎨 Enhanced Features Summary

### 3 New Gauges
| Panel | Purpose | Thresholds |
|-------|---------|------------|
| Answer Cache Ratio | Health proxy | R<30 Y:30-60 G>60 |
| Rerank Utilization | Cost signal | G<30 Y:30-60 R>60 |
| Low-Confidence | Quality signal | G<10 Y:10-20 R>20 |

### 4 New Alerts
| Alert | Threshold | Severity |
|-------|-----------|----------|
| CacheEffectivenessDrop | <30% for 15m | Warning |
| CacheEffectivenessCritical | <15% for 15m | Critical |
| LowConfidenceSpike | >20% for 10m | Warning |
| LowConfidenceSpikeVIP | >15% for 10m | Critical |

---

## 📚 Documentation Quick Links

| Doc | Purpose | Location |
|-----|---------|----------|
| **Complete Summary** | All features overview | `MONITORING_COMPLETE.md` |
| **Enhanced Features** | New panels & alerts | `monitoring/ENHANCED_FEATURES.md` |
| **Import Guide** | Dashboard import help | `monitoring/IMPORT_GUIDE.md` |
| **Quick Start** | Troubleshooting | `monitoring/QUICKSTART.md` |
| **Setup Guide** | Deep dive | `monitoring/README.md` |
| **Reference Card** | This doc! | `QUICK_REFERENCE.md` |

---

## 🎯 Key PromQL Queries

### Cache Hit Ratio (Answer Endpoint)
```promql
sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
/
(
  sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
  + sum(rate(aether_rag_cache_misses_total{endpoint="answer", tenant=~"$tenant"}[5m]))
)
```

### Rerank Utilization %
```promql
100 * sum(rate(aether_rag_answers_total{rerank="true", tenant=~"$tenant"}[15m]))
      / sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[15m]))
```

### Low-Confidence Share
```promql
100 * sum(rate(aether_rag_lowconfidence_total{tenant=~"$tenant"}[15m]))
      / sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[15m]))
```

### Monthly Cost Per Tenant
```promql
sum(increase(aether_rag_answers_total{rerank="false", tenant=~"$tenant"}[30d])) * 0.001
+ sum(increase(aether_rag_answers_total{rerank="true", tenant=~"$tenant"}[30d])) * 0.006
```

---

## ✅ Feature Checklist

### Metrics
- ✅ Tenant labels on all 4 metrics
- ✅ Cache hits/misses (2 endpoints)
- ✅ Answers (mode + rerank)
- ✅ Low-confidence tracking

### Dashboards
- ✅ Original dashboard (11 panels)
- ✅ Enhanced dashboard (14 panels)
- ✅ 4 color-coded gauges
- ✅ Tenant variable (fully wired)

### Alerts
- ✅ 12 production-ready rules
- ✅ 3 severity levels
- ✅ VIP tenant handling
- ✅ Runbook annotations

### Infrastructure
- ✅ Docker Compose stack
- ✅ Auto-provisioning
- ✅ Persistent volumes
- ✅ Hot-reload support

### Automation
- ✅ Start/stop/restart script
- ✅ Smoke test
- ✅ Quick metrics check
- ✅ Red team tests
- ✅ VS Code tasks

### Documentation
- ✅ 9 comprehensive guides
- ✅ Setup & troubleshooting
- ✅ PromQL examples
- ✅ Import instructions
- ✅ Enhancement details

---

## 🚦 Traffic Light Guide

### 🟢 Green = Healthy
- Cache ratio >60%
- Low-confidence <10%
- Rerank usage <30% (cost-effective)

### 🟡 Yellow = Monitor
- Cache ratio 30-60%
- Low-confidence 10-20%
- Rerank usage 30-60%

### 🔴 Red = Action Needed
- Cache ratio <30%
- Low-confidence >20%
- Rerank usage >60% (expensive)

---

## 🎊 You're Ready!

**Stack Status:** Production-grade, enterprise-ready ✅

**Quick Start:** 3 commands, 60 seconds
```powershell
.\scripts\start-monitoring.ps1
.\scripts\tenant-smoke-test.ps1
Start-Process "http://localhost:3000"
```

**Import Enhanced Dashboard:**
- File: `monitoring/grafana-dashboard-enhanced.json`
- Method: Grafana UI → Dashboards → Import

**Documentation:** 9 guides covering everything

**Support:** Check `MONITORING_COMPLETE.md` for full details

---

## 🌟 Pro Tips

1. **Hot reload after alert changes:**
   ```powershell
   curl.exe -X POST http://localhost:9090/-/reload
   ```

2. **Import both dashboards** (they don't conflict):
   - Original: Basic overview
   - Enhanced: Deep insights with gauges

3. **Use tenant variable** to filter all panels:
   - Select specific tenant OR "All" for aggregate

4. **Check alerts status** in Prometheus:
   - http://localhost:9090/alerts

5. **Add Alertmanager** for Slack notifications:
   - See `monitoring/ENHANCED_FEATURES.md` → "Alert Routing"

---

**🎯 Everything you need, one page. Enjoy!** 🚀
