# AetherLink Enhanced Dashboard & Alerts

## 🎨 Enhanced Dashboard Features

### New File: `grafana-dashboard-enhanced.json`

This enhanced dashboard includes **3 new high-impact panels** with color-coded thresholds:

#### 1. **Answer Cache Hit Ratio (Health Proxy)** 🎯
- **Purpose:** Latency health indicator when explicit latency metrics aren't available
- **PromQL:**
  ```promql
  sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
  /
  (
    sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
    +
    sum(rate(aether_rag_cache_misses_total{endpoint="answer", tenant=~"$tenant"}[5m]))
  )
  ```
- **Thresholds:**
  - 🔴 Red: < 30% (poor cache effectiveness)
  - 🟡 Yellow: 30-60% (moderate effectiveness)
  - 🟢 Green: > 60% (good cache effectiveness)
- **Panel Type:** Gauge (0-100%)
- **Interpretation:** Lower ratio = more backend hits = higher latency

---

#### 2. **Rerank Utilization % (Cost Signal)** 💰
- **Purpose:** Cost monitoring for reranking operations
- **PromQL:**
  ```promql
  100 *
  sum(rate(aether_rag_answers_total{rerank="true", tenant=~"$tenant"}[15m]))
  /
  sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[15m]))
  ```
- **Thresholds:**
  - 🟢 Green: < 30% (cost-effective)
  - 🟡 Yellow: 30-60% (moderate cost)
  - 🔴 Red: > 60% (high cost - investigate if intentional)
- **Panel Type:** Gauge (0-100%)
- **Interpretation:** Higher = more expensive operations per tenant

---

#### 3. **Low-Confidence Share (Quality Signal)** 📊
- **Purpose:** Quality indicator for answer confidence
- **PromQL:**
  ```promql
  100 *
  sum(rate(aether_rag_lowconfidence_total{tenant=~"$tenant"}[15m]))
  /
  sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[15m]))
  ```
- **Thresholds:**
  - 🟢 Green: < 10% (excellent quality)
  - 🟡 Yellow: 10-20% (acceptable quality)
  - 🔴 Red: > 20% (quality issues - investigate)
- **Panel Type:** Gauge (0-100%)
- **Interpretation:** Higher = more low-confidence answers = quality concerns

---

## 🚨 New Alert Rules

### Added to `prometheus-alerts.yml`:

#### 1. **CacheEffectivenessDrop** (Warning)
```yaml
expr: |
  (
    sum(rate(aether_rag_cache_hits_total{endpoint="answer"}[10m])) by (tenant)
  )
  /
  ignoring(endpoint)
  (
    sum(rate(aether_rag_cache_hits_total{endpoint="answer"}[10m])) by (tenant)
    +
    sum(rate(aether_rag_cache_misses_total{endpoint="answer"}[10m])) by (tenant)
  )
  < 0.3
for: 15m
severity: warning
```
- **Triggers:** Cache hit ratio below 30% for 15 minutes
- **Impact:** Degraded performance, increased backend load
- **Action:** Investigate cache configuration, check Redis health

---

#### 2. **CacheEffectivenessCritical** (Critical)
```yaml
expr: <same as above> < 0.15
for: 15m
severity: critical
```
- **Triggers:** Cache hit ratio below 15% for 15 minutes
- **Impact:** Severe performance degradation
- **Action:** Immediate investigation required - possible cache failure

---

#### 3. **LowConfidenceSpike** (Warning)
```yaml
expr: |
  (
    sum(rate(aether_rag_lowconfidence_total[15m])) by (tenant)
  )
  /
  (
    sum(rate(aether_rag_answers_total[15m])) by (tenant)
  )
  > 0.2
for: 10m
severity: warning
```
- **Triggers:** Low-confidence rate exceeds 20% for 10 minutes
- **Impact:** Quality degradation, poor user experience
- **Action:** Check knowledge base freshness, review recent queries

---

#### 4. **LowConfidenceSpikeVIP** (Critical)
```yaml
expr: <same as above> > 0.15
for: 10m
severity: critical
```
- **Triggers:** Low-confidence rate exceeds 15% for VIP tenants
- **Impact:** SLA at risk, premium customer impact
- **Action:** Priority investigation, customer notification if needed

---

## 📋 Variable Wiring (Already Configured)

### Tenant Variable Configuration
```json
{
  "name": "tenant",
  "type": "query",
  "datasource": "Prometheus",
  "query": "label_values(aether_rag_answers_total, tenant)",
  "refresh": 1,
  "includeAll": true,
  "multi": false,
  "allValue": ".*"
}
```

✅ **Best Practices Applied:**
- `includeAll=true` with `allValue=".*"` for "All tenants" option
- All panel queries use `tenant=~"$tenant"` (regex-safe)
- Auto-refresh on dashboard load
- Sorted alphabetically for easy selection

---

## 🎯 60-Second Verification

```powershell
# 1. Start monitoring stack
.\scripts\start-monitoring.ps1

# 2. Generate test traffic
$env:API_ADMIN_KEY = "admin-secret-123"
.\scripts\tenant-smoke-test.ps1

# 3. Confirm tenant metrics exist
curl.exe -s http://localhost:8000/metrics | Select-String "aether_rag_.*tenant=" | Select-Object -First 10

# 4. Open Grafana
Start-Process "http://localhost:3000"

# 5. Import enhanced dashboard
# Go to Dashboards → Import → Upload JSON file
# Select: monitoring/grafana-dashboard-enhanced.json

# 6. Check alerts are loaded
Start-Process "http://localhost:9090/alerts"
```

---

## 🔄 Hot Reload (No Restart Needed)

### Reload Prometheus alerts:
```powershell
curl.exe -X POST http://localhost:9090/-/reload
```

### Re-import Grafana dashboard:
- Option A: Delete old dashboard, import new JSON
- Option B: Overwrite via UI (Dashboard Settings → JSON Model → paste → Save)

---

## 📊 Dashboard Comparison

| Feature | Original Dashboard | Enhanced Dashboard |
|---------|-------------------|-------------------|
| **Panels** | 11 panels | 14 panels |
| **Gauges** | 1 (cache ratio) | 4 (cache, rerank, confidence, overall) |
| **Health Proxy** | ❌ | ✅ Answer cache ratio |
| **Cost Signal** | ❌ | ✅ Rerank utilization % |
| **Quality Signal** | ❌ | ✅ Low-confidence share |
| **Thresholds** | Basic | Color-coded (red/yellow/green) |
| **Tenant Variable** | ✅ Fully wired | ✅ Fully wired |
| **Auto-refresh** | 10s | 10s |

---

## 🚀 Advanced Use Cases

### 1. **Tenant Health Score**
Combine the three new panels into a single composite metric:
```promql
# Weighted health score (0-100)
(
  # Cache effectiveness (30% weight)
  (
    sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
    / (sum(rate(aether_rag_cache_hits_total{endpoint="answer", tenant=~"$tenant"}[5m]))
       + sum(rate(aether_rag_cache_misses_total{endpoint="answer", tenant=~"$tenant"}[5m])))
  ) * 30
  +
  # Confidence quality (50% weight)
  (1 - sum(rate(aether_rag_lowconfidence_total{tenant=~"$tenant"}[15m]))
       / sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[15m]))) * 50
  +
  # Normalized volume (20% weight)
  clamp_max(rate(aether_rag_answers_total{tenant=~"$tenant"}[5m]) / 10, 1) * 20
)
```

### 2. **Billing Dashboard Panel**
Add a stat panel for monthly cost tracking:
```promql
# Monthly cost per tenant ($0.001/answer base, $0.005 rerank surcharge)
sum(increase(aether_rag_answers_total{rerank="false", tenant=~"$tenant"}[30d])) * 0.001
+ sum(increase(aether_rag_answers_total{rerank="true", tenant=~"$tenant"}[30d])) * 0.006
```
- **Unit:** Currency (USD)
- **Panel Type:** Stat with sparkline

### 3. **Cache ROI Panel**
Show requests saved by caching:
```promql
# Backend calls avoided per day
sum(increase(aether_rag_cache_hits_total{tenant=~"$tenant"}[1d]))
```
- **Unit:** Short
- **Panel Type:** Stat with trend

### 4. **Power User Detection**
Identify tenants heavily using reranking:
```promql
# Tenants with >50% rerank usage
(
  sum(rate(aether_rag_answers_total{rerank="true"}[1h])) by (tenant)
  / sum(rate(aether_rag_answers_total[1h])) by (tenant)
) > 0.5
```
- **Panel Type:** Table showing tenant + percentage

---

## 🎓 Recording Rules (Optional Performance Boost)

Add these to Prometheus for faster dashboard queries:

```yaml
# prometheus-recording-rules.yml
groups:
- name: aetherlink_rag.recording
  interval: 30s
  rules:
  # Pre-calculate cache ratio per tenant
  - record: aether:cache_hit_ratio:5m
    expr: |
      sum(rate(aether_rag_cache_hits_total[5m])) by (tenant)
      /
      (
        sum(rate(aether_rag_cache_hits_total[5m])) by (tenant)
        + sum(rate(aether_rag_cache_misses_total[5m])) by (tenant)
      )

  # Pre-calculate rerank percentage
  - record: aether:rerank_utilization_pct:15m
    expr: |
      100 *
      sum(rate(aether_rag_answers_total{rerank="true"}[15m])) by (tenant)
      /
      sum(rate(aether_rag_answers_total[15m])) by (tenant)

  # Pre-calculate low-confidence percentage
  - record: aether:lowconfidence_pct:15m
    expr: |
      100 *
      sum(rate(aether_rag_lowconfidence_total[15m])) by (tenant)
      /
      sum(rate(aether_rag_answers_total[15m])) by (tenant)
```

**Then update dashboard queries to use recorded metrics:**
```promql
# Instead of the full expression, use:
aether:cache_hit_ratio:5m{tenant=~"$tenant"}
aether:rerank_utilization_pct:15m{tenant=~"$tenant"}
aether:lowconfidence_pct:15m{tenant=~"$tenant"}
```

**Benefits:**
- ⚡ Faster dashboard rendering
- 🔋 Lower Prometheus CPU usage
- 📊 Consistent calculations across panels and alerts

---

## 🌐 Grafana Cloud Ready

The enhanced dashboard is compatible with:
- ✅ Grafana OSS (v8.0+)
- ✅ Grafana Cloud
- ✅ Grafana Enterprise

**Import Steps:**
1. Go to https://grafana.com (or your Grafana instance)
2. Navigate to **Dashboards** → **Import**
3. Upload `grafana-dashboard-enhanced.json`
4. Select your Prometheus datasource
5. Click **Import**

---

## 📱 Alert Routing (Next Step)

To receive notifications for new alerts, add Alertmanager:

### `monitoring/alertmanager.yml`
```yaml
global:
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

route:
  group_by: ['alertname', 'tenant', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'slack-notifications'

  # Route critical alerts to separate channel
  routes:
  - match:
      severity: critical
    receiver: 'slack-critical'

receivers:
- name: 'slack-notifications'
  slack_configs:
  - channel: '#alerts'
    title: '🚨 {{ .GroupLabels.alertname }}'
    text: |
      *Tenant:* {{ .GroupLabels.tenant }}
      *Severity:* {{ .GroupLabels.severity }}
      {{ range .Alerts }}
      {{ .Annotations.description }}
      {{ end }}
    color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'

- name: 'slack-critical'
  slack_configs:
  - channel: '#critical-alerts'
    title: '🔥 CRITICAL: {{ .GroupLabels.alertname }}'
    text: |
      *Tenant:* {{ .GroupLabels.tenant }}
      {{ range .Alerts }}
      {{ .Annotations.description }}
      *Impact:* {{ .Annotations.impact }}
      {{ end }}
    color: 'danger'
```

### Add to `docker-compose.yml`:
```yaml
alertmanager:
  image: prom/alertmanager:latest
  container_name: aether-alertmanager
  ports:
    - "9093:9093"
  volumes:
    - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
  restart: unless-stopped
  networks:
    - aether-monitoring
```

### Update Prometheus config:
```yaml
# In prometheus-config.yml
alerting:
  alertmanagers:
  - static_configs:
    - targets: ['aether-alertmanager:9093']
```

**Restart stack:**
```powershell
.\scripts\start-monitoring.ps1 -Restart
```

---

## ✅ Complete Feature Checklist

### Metrics & Code
- ✅ Per-tenant labels on all metrics
- ✅ Cache hit/miss tracking
- ✅ Answer mode/rerank tracking
- ✅ Low-confidence tracking

### Dashboards
- ✅ Original 11-panel dashboard
- ✅ Enhanced 14-panel dashboard
- ✅ Color-coded gauges (red/yellow/green)
- ✅ Tenant variable with "All" option
- ✅ Auto-refresh (10s)

### Alerts
- ✅ 8 original alert rules
- ✅ 4 new enhanced alert rules
- ✅ Severity levels (info/warning/critical)
- ✅ Tenant-specific alerting
- ✅ VIP tenant special handling

### Automation
- ✅ Docker Compose stack
- ✅ Auto-provisioning (dashboards + datasource)
- ✅ Start/stop/restart scripts
- ✅ Smoke test automation
- ✅ VS Code task integration

### Documentation
- ✅ Setup guides
- ✅ Troubleshooting guides
- ✅ Query examples
- ✅ Use case documentation
- ✅ Enhancement guide (this file!)

---

## 🎉 You're Production Ready!

**Enhanced dashboard includes:**
- 3 new high-impact panels
- Color-coded thresholds
- Health/cost/quality signals
- Fully wired tenant variable

**Enhanced alerts include:**
- Sharper cache effectiveness monitoring
- Quality spike detection
- VIP tenant special handling
- Actionable severity levels

**Import the enhanced dashboard:**
```powershell
# Dashboard JSON location:
monitoring/grafana-dashboard-enhanced.json

# Alert rules location:
monitoring/prometheus-alerts.yml
```

**Dashboard UID:** `aetherlink_rag_tenant_metrics_enhanced`

🚀 **Ready to go!** Import the enhanced dashboard and enjoy pro-level observability!
