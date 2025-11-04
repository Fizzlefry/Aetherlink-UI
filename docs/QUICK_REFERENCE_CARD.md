# 🎯 AETHERLINK MONITORING - QUICK REFERENCE CARD

## 📊 Dashboard & URLs

```
Main Dashboard:  http://localhost:3000/d/aetherlink_rag_tenant_metrics_enhanced
Prometheus:      http://localhost:9090
Alertmanager:    http://localhost:9093

Login: admin / admin (CHANGE THIS!)
```

## ⚡ Essential Commands

```powershell
# Quick health check
.\scripts\ship-sanity-sweep.ps1

# Create backup
.\scripts\backup-monitoring.ps1

# Maintenance mode (60 min)
.\scripts\maintenance-mode.ps1

# Lock-in (password + backup + test)
.\scripts\lock-in.ps1

# Hot-reload config changes
curl -X POST http://localhost:9090/-/reload
```

## 🔥 Critical Alerts (Page Immediately)

```
LowConfidenceSpikeVIP       - >40% low-confidence for VIP (10min) → Page on-call
CacheEffectivenessDropVIP   - <20% cache hit for VIP (10min)     → Page on-call
```

## ⚠️ General Alerts (30min SLA)

```
CacheEffectivenessDrop      - <30% cache hit (15min)
LowConfidenceSpike          - >30% low-confidence (15min)
HealthScoreDegradation      - <60 health score (15min)
```

## 📈 Key Metrics (SLO Targets)

```
Cache Hit Ratio:       >50% (critical: <30%)
Low-Confidence %:      <20% (critical: >30%)
Rerank Utilization:    <50% (critical: >60%)
Health Score:          >80 (critical: <60)
30-Day Cost:           <$50 (watch: >$200)
```

## 🔍 Investigation Queries (Prometheus)

```promql
# Top tenants by volume
topk(10, sum(rate(aether_rag_answers_total[1h])) by (tenant_id))

# Costliest tenants (rerank)
topk(5, sum(increase(aether_rag_answers_total{rerank="true"}[24h])) by (tenant_id))

# VIP tenant health
aether:cache_hit_ratio:5m{tenant_id="vip-customer-123"}
aether:lowconfidence_pct:15m{tenant_id="vip-customer-123"}
```

## 🛠️ Common Operations

```powershell
# Silence alerts for deploy (30 min)
.\scripts\maintenance-mode.ps1 -DurationMinutes 30 -Comment "Deploy v2.3.0"

# Check active silences
Start-Process http://localhost:9093/#/silences

# View recording rule output
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'

# Sample current health score
curl -s "http://localhost:9090/api/v1/query?query=aether:health_score:15m"
```

## 📞 Escalation Paths

```
VIP Alert Fires           → Page on-call (5min)
General Alert >1hr        → Ping #aether-ops Slack (30min)
Cost >$200/30d            → Email VP Eng + Finance (4hrs)
Health <40 sustained      → Activate Incident Commander (15min)
```

## 🏗️ Architecture

```
┌─────────────────┐
│  Prometheus     │  Recording rules (8) → Alerts (5) → Alertmanager
│  v2.54.1        │  15-day retention, 20 max concurrency
└─────────────────┘
         │
         ├─ Scrape: customer-ops API (30s interval)
         ├─ Evaluate: rules every 30s
         └─ Alert: Alertmanager (v0.27.0)
                   │
                   └─ Route: Slack (configurable)

┌─────────────────┐
│  Grafana        │  Dashboards (2) → Panels (5 + 4)
│  11.2.0         │  Main: 5 panels (cache/rerank/conf/cost/health)
└─────────────────┘  Exec: 4 panels (cost stat + health + 2 trends)
```

## 🎯 Recording Rules (8 Total)

```yaml
Per-Tenant:
- aether:cache_hit_ratio:5m
- aether:rerank_utilization_pct:15m
- aether:lowconfidence_pct:15m

Aggregate (:all suffix):
- aether:cache_hit_ratio:5m:all
- aether:rerank_utilization_pct:15m:all
- aether:lowconfidence_pct:15m:all

Business KPIs:
- aether:estimated_cost_30d_usd       # $0.001 base + $0.006 rerank
- aether:health_score:15m             # 50% cache + 30% quality + 20% efficiency
```

## 🚨 Traffic Guard Pattern

```yaml
# All alerts use this pattern to prevent false alarms on zero traffic
expr: (alert_condition) and sum(rate(traffic_metric[window])) > 0

# Example:
expr: |
  (aether:cache_hit_ratio:5m < 30) 
  and 
  sum(rate(aether_cache_requests_total[5m])) > 0
```

## 📁 File Locations

```
monitoring/
├── docker-compose.yml                    # Pinned versions
├── prometheus-config.yml                 # Main config
├── prometheus-recording-rules.yml        # 8 rules
├── prometheus-alerts.yml                 # 5 alerts
├── alertmanager.yml                      # Slack routing
├── grafana-dashboard-enhanced.json       # Main dashboard (5 panels)
└── grafana-dashboard-business-kpis.json  # Exec dashboard (4 panels)

scripts/
├── ship-sanity-sweep.ps1                 # Quick health check
├── backup-monitoring.ps1                 # Backup automation
├── maintenance-mode.ps1                  # Alert silencing
├── lock-in.ps1                          # Password + backup + test
├── pre-prod-go.ps1                      # 7-check validation
└── quick-check.ps1                      # Rapid 6-step check

docs/
├── ON_CALL_RUNBOOK.md                   # Incident response
├── SLO_TUNING.md                        # 8-week roadmap
├── RELIABILITY_PACK.md                  # Master overview
├── FINAL_SHIP_CHECKLIST.md              # Deployment summary
└── PRODUCTION_DASHBOARD_FINAL.md        # Dashboard details
```

## 🔐 Security Checklist

```
[ ] Change Grafana admin password (http://localhost:3000)
[ ] Create first backup (.\scripts\backup-monitoring.ps1)
[ ] Test maintenance mode (.\scripts\maintenance-mode.ps1 -DurationMinutes 1)
[ ] Commit backups to git (git add .\backups\)
[ ] Review on-call runbook (.\docs\ON_CALL_RUNBOOK.md)
```

## 📊 Health Score Formula

```
Health = 50% * cache_hit_ratio
       + 30% * (100 - low_confidence_pct)
       + 20% * (100 - rerank_utilization_pct)

Range: 0-100
Green: ≥80, Yellow: 60-79, Red: <60
```

## 💰 Cost Estimate Formula

```
Cost = (base_queries * $0.001) + (rerank_queries * $0.006)

Where:
- base_queries   = increase(aether_rag_answers_total{rerank="false"}[30d])
- rerank_queries = increase(aether_rag_answers_total{rerank="true"}[30d])

Thresholds:
Green: <$50, Yellow: $50-$200, Red: >$200
```

## 🎓 On-Call Quick Start

```
1. Read runbook (15 min): .\docs\ON_CALL_RUNBOOK.md
2. Bookmark dashboard: http://localhost:3000
3. Test commands: .\scripts\ship-sanity-sweep.ps1
4. Know escalation: VIP → page (5min), General → 30min
5. Know SLOs: cache >50%, quality <30%, rerank <60%
```

---

**Print this card and keep it handy!**  
**Status**: 🟢 PRODUCTION READY  
**Version**: 1.0 (2024-11-02)
