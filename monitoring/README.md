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

---

## 📈 Phase XIX: Command Center Analytics Monitoring

**Status**: ✅ Complete - Analytics metrics exposed via Prometheus for alerting and monitoring.

### Overview

The Command Center now exposes operational analytics as Prometheus metrics, enabling monitoring and alerting on grouped operation data (e.g., alert when "Data Changes" operations drop to zero).

### Metrics Exposed

- `aetherlink_ops_analytics_all_time{label="...", env="..."}` - Total operations by category since startup
- `aetherlink_ops_analytics_last_24h{label="...", env="..."}` - Operations in the last 24 hours

**Operation Categories:**
- Schedule Updates
- Data Changes
- Auto-Healing
- Lead Enrichment
- Chat Interactions
- Lead Outcomes
- And more...

### Alert Rules

The `aetherlink-ops-analytics.rules.yml` file includes production-ready alerts:

- **Data Changes Stopped** (Warning): Alerts when data import operations cease (30min threshold)
- **Auto-Healing Spike** (Warning): Alerts when auto-healing operations increase significantly (15min threshold)
- **Schedule Updates Low** (Info): Alerts when scheduled operations are low (2h threshold)
- **No Operations** (Critical): Alerts when all operations stop (1h threshold)

### Setup

1. **Install and Configure Prometheus:**
   ```powershell
   .\setup-monitoring.ps1 -Install -Configure
   ```

2. **Start Command Center:**
   ```powershell
   .\run-command-center.ps1
   ```

3. **Start Prometheus:**
   ```powershell
   & 'C:\ProgramData\prometheus\prometheus.exe' --config.file='C:\ProgramData\prometheus\prometheus.yml'
   ```

4. **Test Setup:**
   ```powershell
   .\setup-monitoring.ps1 -Test
   ```

### Accessing Metrics

- **Metrics Endpoint**: `http://localhost:8000/metrics`
- **Analytics API**: `http://localhost:8000/ops/analytics` (requires API key)
- **Prometheus UI**: `http://localhost:9090`

### Integration Details

- **ASGI Mounting**: `/metrics` endpoint mounted using `prometheus_client.make_asgi_app()` for proper async support
- **Data Structure**: Analytics API returns combined `groups` structure with `all_time` and `last_24h` counts
- **UI Updates**: AnalyticsCard.tsx updated to consume new data format while maintaining trend indicators
- **Environment Labeling**: Metrics include `env` label (defaults to "dev" if `AETHER_ENV` not set)

---

## 🎛️ Phase XX: Operator Control Deck

**Status**: ✅ Complete - Production-ready operator dashboard with tenant-scoped controls and monitoring.

### Overview

The Command Center now provides a comprehensive operator control deck with tenant-aware analytics, job management, and queue monitoring. All controls are scoped by tenant for multi-tenant operations.

### Endpoints

- **`/ops/operator/jobs`** → List schedulable/managed jobs (tenant-aware)
- **`/ops/operator/jobs/{id}/pause`** → Pause a job
- **`/ops/operator/jobs/{id}/resume`** → Resume a paused job
- **`/ops/operator/queues`** → Current queue/alerts snapshot (tenant-aware)

### UI Components

- **`TenantScopeSelector.tsx`** - Dropdown for tenant selection with active/inactive status
- **`AnalyticsCard.tsx`** - Now tenant-aware with filtered operation data
- **`JobsControlCard.tsx`** - Job pause/resume controls with optimistic UI updates
- **`QueueStatusCard.tsx`** - Queue monitoring with issue detection and alerts

### Features

- **Tenant Filtering**: All components respect tenant selection for scoped operations
- **Defensive JSON Shapes**: Components handle malformed responses gracefully with defaults
- **Optimistic UI**: Job controls update immediately with rollback on API failure
- **Error Handling**: User-friendly error messages prevent silent failures
- **Operator Audit Trail**: Pause/resume actions are logged and appear in analytics as "Operator Controls"

### Integration Details

- **Query Parameters**: All operator endpoints accept optional `tenant` parameter
- **Response Structure**: Endpoints return `tenant` field in response for consistency
- **UI State Management**: Centralized tenant state in `DashboardHome.tsx`
- **TypeScript Safety**: Updated interfaces with optional properties for backward compatibility
- **Audit Integration**: Operator actions logged to scheduler audit trail and grouped as "Operator Controls" in analytics
