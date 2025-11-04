# Metrics & Observability Guide

## Prometheus Metrics

### Ops Metrics

**`api_tenants_count`** (Gauge)
- Number of active tenants (unique values in AUTH_KEYS)
- Updated on startup and after `/ops/reload-auth`
- Query: `api_tenants_count`

### Lead Metrics

**`lead_enrich_total`** (Counter)
- Count of lead enrichment operations
- Labels: `intent`, `urgency`, `sentiment`
- Query: `rate(lead_enrich_total[5m])`

**`lead_enrich_score`** (Histogram)
- Distribution of enrichment scores (0.0-1.0)
- Buckets: 0, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0
- Query: `histogram_quantile(0.95, lead_enrich_score_bucket)`

**`lead_outcome_total`** (Counter)
- Count of recorded outcomes
- Labels: `outcome` (booked, ghosted, etc.)
- Query: `rate(lead_outcome_total{outcome="booked"}[1h])`

**`lead_conversion_rate`** (Gauge)
- Current conversion rate (booked / total)
- Updated when outcomes are recorded
- Query: `lead_conversion_rate`

**`lead_pred_prob`** (Histogram)
- Distribution of prediction probabilities
- Buckets: 0.0-1.0 in 0.1 increments
- Query: `histogram_quantile(0.5, lead_pred_prob_bucket)`

**`lead_pred_latency_seconds`** (Summary)
- Prediction inference latency
- Query: `lead_pred_latency_seconds_sum / lead_pred_latency_seconds_count`

### Intent Metrics

**`intent_count`** (Counter)
- Count by intent type and endpoint
- Labels: `intent`, `endpoint`
- Query: `rate(intent_count{intent="faq"}[5m])`

## Quick Access

### VS Code Tasks
- **Check Metrics**: `Tasks: Run Task → AetherLink: Check Metrics`
- **List Tenants**: `Tasks: Run Task → AetherLink: List Tenants`
- **Health Check**: `Tasks: Run Task → AetherLink: Health Check`
- **Reload Auth**: `Tasks: Run Task → AetherLink: Reload Auth Keys`

### PowerShell Commands

```powershell
# View all metrics
Invoke-RestMethod http://localhost:8000/metrics

# Filter for tenants
Invoke-RestMethod http://localhost:8000/metrics | Select-String "api_tenants_count"

# Reload auth and check tenant count
$h = @{ "x-api-key" = $env:API_KEY_EXPERTCO; "x-admin-key" = $env:API_ADMIN_KEY }
Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $h | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/metrics | Select-String "api_tenants_count"

# List tenants (admin-only)
Invoke-RestMethod http://localhost:8000/ops/tenants -Headers $h | ConvertTo-Json
```

## Grafana Dashboards

### Recommended Panels

**Tenants Overview**
- Query: `api_tenants_count`
- Type: Stat
- Thresholds: Green > 1, Yellow = 1, Red = 0

**Lead Conversion Funnel**
- Queries:
  - Total: `rate(lead_enrich_total[1h])`
  - Booked: `rate(lead_outcome_total{outcome="booked"}[1h])`
  - Rate: `lead_conversion_rate`
- Type: Time series

**Prediction Performance**
- Queries:
  - P50: `histogram_quantile(0.5, lead_pred_prob_bucket)`
  - P95: `histogram_quantile(0.95, lead_pred_prob_bucket)`
  - Latency: `rate(lead_pred_latency_seconds_sum[5m]) / rate(lead_pred_latency_seconds_count[5m])`
- Type: Time series

**Intent Distribution**
- Query: `sum by (intent) (rate(intent_count[5m]))`
- Type: Pie chart

## Alerting Rules

```yaml
groups:
  - name: aetherlink_ops
    rules:
      - alert: NoTenants
        expr: api_tenants_count == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "No active tenants configured"

      - alert: LowConversionRate
        expr: lead_conversion_rate < 0.05
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Conversion rate below 5%"

      - alert: HighPredictionLatency
        expr: |
          rate(lead_pred_latency_seconds_sum[5m]) /
          rate(lead_pred_latency_seconds_count[5m]) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Prediction latency > 1s"
```

## Request-ID Tracing

Every response includes `x-request-id` header for correlation:

```powershell
# Supply your own request ID
$headers = @{ "x-request-id" = "my-trace-123" }
Invoke-RestMethod http://localhost:8000/health -Headers $headers

# Check logs for that ID
Get-Content pods/customer_ops/api.log | Select-String "my-trace-123"
```

Request IDs are automatically included in:
- Response headers
- JSON structured logs
- Error responses (429, 500, etc.)

## Next Steps

1. **Ship logs to aggregator**: Configure JSON log shipping to Loki/OpenSearch
2. **OTel integration**: Wire request-ID into distributed traces
3. **Custom dashboards**: Build team-specific Grafana dashboards
4. **SLO tracking**: Define and monitor service-level objectives
5. **Alerts**: Set up PagerDuty/Slack notifications for critical alerts
