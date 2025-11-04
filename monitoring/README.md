# AetherLink RAG Monitoring

Complete monitoring setup for per-tenant RAG metrics with Prometheus and Grafana.

## 📊 Dashboard & Alerts

### Files Included
- **`grafana-dashboard.json`** - Pre-configured Grafana dashboard with 11 panels
- **`prometheus-alerts.yml`** - 8 production-ready alert rules
- **`prometheus-config.yml`** - Example Prometheus scrape configuration

---

## 🚀 Quick Setup

### 1. Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: aetherlink_api
    metrics_path: /metrics
    scheme: http
    static_configs:
      - targets: ['localhost:8000']
```

Load alert rules:
```yaml
rule_files:
  - '/path/to/monitoring/prometheus-alerts.yml'
```

Restart Prometheus:
```bash
# Docker
docker restart prometheus

# Systemd
systemctl restart prometheus
```

### 2. Grafana Dashboard Import

1. Open Grafana → Dashboards → Import
2. Upload `grafana-dashboard.json`
3. Select your Prometheus datasource
4. Click **Import**

**Dashboard Features:**
- ✅ Per-tenant answer volume (time series)
- ✅ Cache hit ratio gauge by tenant
- ✅ Cache activity stacked by endpoint
- ✅ Answers by search mode (semantic/lexical/hybrid)
- ✅ Low confidence tracking
- ✅ Reranking usage (percentage)
- ✅ Total stats (answers, hits, misses, low confidence)
- ✅ Tenant selector variable (filter by customer)

### 3. Verify Metrics

```bash
# Check metrics endpoint
curl http://localhost:8000/metrics | grep aether_rag

# Check specific tenant metrics
curl http://localhost:8000/metrics | grep 'tenant="expertco"'
```

---

## 📈 Dashboard Panels

### 1. Answer Requests by Tenant
**Query:** `sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[5m])) by (tenant)`
- Shows request rate per tenant
- Filterable by tenant variable
- Useful for: Volume tracking, billing, capacity planning

### 2. Cache Hit Ratio by Tenant
**Query:**
```promql
sum(rate(aether_rag_cache_hits_total{tenant=~"$tenant"}[5m])) by (tenant)
/ (sum(rate(aether_rag_cache_hits_total{tenant=~"$tenant"}[5m])) by (tenant)
   + sum(rate(aether_rag_cache_misses_total{tenant=~"$tenant"}[5m])) by (tenant))
```
- Gauge showing cache effectiveness (0-100%)
- Thresholds: Red <30%, Yellow 30-60%, Green >60%
- Useful for: Performance optimization, cache tuning

### 3. Cache Activity by Endpoint
**Queries:**
- Hits: `sum(rate(aether_rag_cache_hits_total{tenant=~"$tenant"}[5m])) by (endpoint)`
- Misses: `sum(rate(aether_rag_cache_misses_total{tenant=~"$tenant"}[5m])) by (endpoint)`
- Stacked area chart (green hits, red misses)
- Shows `/search` vs `/answer` cache behavior
- Useful for: Identifying which endpoint needs cache tuning

### 4. Answers by Search Mode
**Query:** `sum(rate(aether_rag_answers_total{tenant=~"$tenant"}[5m])) by (mode)`
- Bar chart showing semantic/lexical/hybrid usage
- Useful for: Understanding user preferences, optimizing modes

### 5. Low Confidence Answers
**Query:** `rate(aether_rag_lowconfidence_total{tenant=~"$tenant"}[5m])`
- Tracks when system can't confidently answer
- Threshold overlay (yellow >0.1, red >0.2)
- Useful for: Quality monitoring, SLA tracking

### 6. Reranking Usage
**Queries:**
- Rerank true: `sum(rate(aether_rag_answers_total{tenant=~"$tenant",rerank="true"}[5m])) by (tenant)`
- Rerank false: `sum(rate(aether_rag_answers_total{tenant=~"$tenant",rerank="false"}[5m])) by (tenant)`
- Percentage stacked bars
- Useful for: Cost tracking (reranking is more expensive)

### 7-10. Total Stats (Time Range)
- Total Answers
- Total Cache Hits
- Total Cache Misses
- Total Low Confidence

Single-value stats showing cumulative counts over selected time range.

---

## 🚨 Alert Rules

### 1. HighLowConfidenceRate
**Triggers when:** Low confidence rate > 0.2/s for 10 minutes
**Severity:** Warning
**Action:** Check document quality, review query patterns

### 2. CacheIneffectiveForTenant
**Triggers when:** Cache hit ratio < 30% for 15 minutes
**Severity:** Info
**Action:** Increase cache TTL, review cache key strategy

### 3. HighAnswerVolumeForTenant
**Triggers when:** Answer rate > 10/s for 10 minutes
**Severity:** Warning
**Action:** Check for abuse, verify billing, review rate limits

### 4. NoAnswerRequestsForTenant
**Triggers when:** Zero requests for 30 minutes
**Severity:** Info
**Action:** Check customer health, verify expected downtime

### 5. CacheCompletelyMissing
**Triggers when:** Zero cache hits with ongoing requests
**Severity:** Critical
**Action:** Check Redis connection, restart cache service

### 6. HighRerankUsageForTenant
**Triggers when:** >80% of answers use reranking for 30 minutes
**Severity:** Info (cost impact: high)
**Action:** Review cost impact, optimize rerank threshold

### 7. SLABreachLowConfidenceVIP
**Triggers when:** Low confidence rate >15% for VIP tenants (20 minutes)
**Severity:** Critical
**Action:** Immediate investigation, notify customer success

---

## 🔧 Customization

### Add Custom Tenant Tags

Label VIP customers for SLA monitoring:
```python
# In your auth middleware
if tenant_id in VIP_TENANTS:
    tenant_label = f"vip-{tenant_id}"
else:
    tenant_label = tenant_id
```

### Create Tenant-Specific Dashboards

Clone the dashboard and set tenant variable default:
1. Dashboard Settings → Variables → `tenant`
2. Set Default Value: `expertco`
3. Save as new dashboard: "AetherLink RAG - ExpertCo"

### Add Cost Tracking Panel

```promql
# Estimated cost per tenant (assuming $0.001/answer + $0.005/rerank)
sum(increase(aether_rag_answers_total{rerank="false"}[1h])) by (tenant) * 0.001
+ sum(increase(aether_rag_answers_total{rerank="true"}[1h])) by (tenant) * 0.006
```

### Monitor Response Latency

If you add latency metrics:
```python
# In main.py
REQUEST_LATENCY = Histogram(
    "aether_rag_request_duration_seconds",
    "Request duration",
    ["endpoint", "tenant"]
)
```

Panel query:
```promql
histogram_quantile(0.95,
  sum(rate(aether_rag_request_duration_seconds_bucket[5m])) by (tenant, le)
)
```

---

## 🎯 Use Cases

### 1. Billing & Usage Tracking
```promql
# Monthly answer count per tenant
sum(increase(aether_rag_answers_total[30d])) by (tenant)

# With rerank surcharge
sum(increase(aether_rag_answers_total{rerank="false"}[30d])) by (tenant)
+ (sum(increase(aether_rag_answers_total{rerank="true"}[30d])) by (tenant) * 3)
```

### 2. SLA Monitoring
```promql
# Availability: answers not blocked by low confidence
1 - (
  rate(aether_rag_lowconfidence_total[5m])
  / rate(aether_rag_answers_total[5m])
)
```

### 3. Cache ROI
```promql
# Requests saved by cache (per day)
sum(increase(aether_rag_cache_hits_total[1d])) by (tenant)
```

### 4. Customer Health Score
Combine metrics:
- High volume + low confidence = customer struggling
- Low volume + high cache hits = healthy usage
- High rerank usage = power user (upsell opportunity)

---

## 📊 Grafana Dashboard Variables

### Pre-configured Variables

**`$tenant`** - Tenant selector
- Type: Query
- Query: `label_values(aether_rag_answers_total, tenant)`
- Multi-select: No
- Include All: Yes
- Refresh: On Dashboard Load

### Add More Variables

**Time range shortcuts:**
```json
{
  "name": "timerange",
  "type": "custom",
  "options": [
    {"text": "Last Hour", "value": "1h"},
    {"text": "Last 6 Hours", "value": "6h"},
    {"text": "Last Day", "value": "1d"},
    {"text": "Last Week", "value": "7d"}
  ]
}
```

**Search mode filter:**
- Query: `label_values(aether_rag_answers_total, mode)`
- Use in panels: `{mode=~"$mode"}`

---

## 🧪 Testing & Validation

### Generate Test Traffic
```powershell
# Run smoke test
.\scripts\tenant-smoke-test.ps1

# Generate sustained load
for ($i=0; $i -lt 100; $i++) {
  curl.exe -s -H "X-API-Key: $env:API_KEY_EXPERTCO" "http://localhost:8000/answer?q=test$i&mode=hybrid" | Out-Null
  Start-Sleep -Milliseconds 500
}
```

### Verify Metrics Appear
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check specific metric
curl http://localhost:9090/api/v1/query?query=aether_rag_answers_total
```

### Test Alerts
```bash
# Trigger low confidence alert (make bad queries)
for i in {1..50}; do
  curl -H "X-API-Key: $API_KEY" "http://localhost:8000/answer?q=gibberishasdfqwerty$i"
done

# Check Alertmanager
curl http://localhost:9093/api/v2/alerts
```

---

## 🔗 Related Documentation

- **Quick Verification:** `../TENANT_METRICS_VERIFY.md`
- **Implementation Guide:** `../TENANT_METRICS_COMPLETE.md`
- **Usage Examples:** `../TENANT_METRICS_USAGE.md`

---

## 📝 Metrics Reference

### Available Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `aether_rag_cache_hits_total` | Counter | endpoint, tenant | Cache hits |
| `aether_rag_cache_misses_total` | Counter | endpoint, tenant | Cache misses |
| `aether_rag_answers_total` | Counter | mode, rerank, tenant | Answer requests |
| `aether_rag_lowconfidence_total` | Counter | tenant | Low confidence answers |

### Label Values

**endpoint:** `search`, `answer`
**mode:** `semantic`, `lexical`, `hybrid`
**rerank:** `true`, `false`
**tenant:** Dynamic (from API key)

---

## 🎉 You're All Set!

1. ✅ Import Grafana dashboard
2. ✅ Load Prometheus alerts
3. ✅ Configure scrape targets
4. ✅ Run smoke test to generate metrics
5. ✅ View dashboard with tenant selector

**Questions?** Check the main docs or run:
```powershell
.\scripts\tenant-smoke-test.ps1
```
