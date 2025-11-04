# Failure Prevention: Uptime Probes, SLO Alerts & Configuration Linting

**Status**: ✅ Production Ready  
**Sprint**: Post-Sprint 5 Enhancement  
**Last Updated**: 2025-11-02

---

## 🎯 Overview

This document describes the comprehensive failure prevention system added to catch issues before they impact production:

1. **Blackbox Uptime Probes**: HTTP health checks for all monitoring endpoints
2. **SLO Burn-Rate Alerts**: Fast & slow detection of payment rate and revenue degradation
3. **Docker Healthchecks**: Self-healing signals for container orchestration
4. **promtool Linting**: Configuration validation in CI to prevent bad rules from merging

**Detection Times**:
- Endpoint failures: **5 minutes** (UptimeProbeFailing)
- SLO degradation (fast): **30-90 minutes** (burn-rate alerts)
- SLO violations (slow): **6-8 hours** (sustained violations)
- Configuration errors: **Pre-merge** (CI lint)

---

## 📊 Component Overview

### 1. Blackbox Exporter (Uptime Probes)

**Service**: `prom/blackbox-exporter:v0.25.0`  
**Port**: `9115`  
**Config**: `monitoring/blackbox.yml`

**Monitored Endpoints** (5 total):
```
✅ http://crm-api:8080/metrics           - CRM API metrics endpoint
✅ http://crm-api:8080/qbo/status        - QuickBooks OAuth status
✅ http://prometheus:9090/-/ready        - Prometheus readiness
✅ http://grafana:3000/api/health        - Grafana health API
✅ http://alertmanager:9093/api/v2/status - Alertmanager status API
```

**Probe Modules**:
- `http_2xx`: Standard HTTP probe (5s timeout, status codes 200/204)
- `http_2xx_with_auth`: Same with basic auth support (for Grafana)

**Scrape Configuration** (`prometheus-config.yml`):
```yaml
- job_name: 'blackbox_http'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets: [...]  # 5 endpoints listed above
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox:9115
```

**Key Metric**: `probe_success` (1 = success, 0 = failure)

---

### 2. SLO Burn-Rate Alerts

**Purpose**: Detect when payment rates or revenue fall below SLO thresholds at different velocities.

#### Alert: PaymentRateSLOBurnFast
```yaml
expr: (85 - crm:payment_rate_30d_pct) > 5
for: 30m
severity: warning
```
**Triggers when**: Payment rate drops below 80% for 30 minutes  
**SLO Target**: 85% payment conversion  
**Use Case**: Early warning of payment rate degradation

#### Alert: PaymentRateSLOBurnSlow
```yaml
expr: (85 - crm:payment_rate_30d_pct) > 10
for: 6h
severity: critical
```
**Triggers when**: Payment rate drops below 75% for 6 hours  
**Impact**: Sustained SLO violation, executive escalation required

#### Alert: RevenueFlatlineFast
```yaml
expr: sum(increase(crm_invoice_payments_cents_total[1h])) == 0
for: 90m
severity: warning
```
**Triggers when**: Zero payments in last 1h, persisting for 90m  
**Use Case**: Detect payment processing issues or genuine lulls

#### Alert: RevenueFlatlineSlow
```yaml
expr: sum(increase(crm_invoice_payments_cents_total[6h])) == 0
for: 8h
severity: critical
```
**Triggers when**: Zero payments in last 6h, persisting for 8h  
**Impact**: Half-business-day revenue outage, immediate escalation

---

### 3. Docker Healthchecks

**Purpose**: Provide self-healing signals to Docker/K8s orchestration.

**Configuration** (all services):
```yaml
healthcheck:
  test: [...service-specific check...]
  interval: 15s
  timeout: 5s
  retries: 8
```

**Service-Specific Healthchecks**:

| Service | Test Command | Notes |
|---------|-------------|-------|
| **prometheus** | `wget -qO- http://localhost:9090/-/ready` | Official readiness endpoint |
| **grafana** | `wget -qO- http://localhost:3000/api/health` | Health API, returns JSON |
| **alertmanager** | `wget -qO- http://localhost:9093/api/v2/status` | Status API |
| **crm-api** | `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/metrics', timeout=2)"` | Python-based (no curl/wget in image) |

**Health States**:
- `healthy`: All retries passing
- `unhealthy`: Failed 8 consecutive checks (2 minutes)
- `starting`: First 8 checks not yet complete

**Docker Status**:
```bash
$ docker ps --format '{{.Names}}: {{.Status}}'
aether-prom: Up 10 minutes (healthy)
aether-grafana: Up 10 minutes (healthy)
aether-alertmanager: Up 10 minutes (healthy)
aether-blackbox: Up 10 minutes
crm-api: Up 10 minutes (healthy)
```

---

### 4. promtool Configuration Linting

**Purpose**: Validate Prometheus configurations before merge to prevent runtime errors.

**Installation** (CI):
```bash
curl -fsSL https://github.com/prometheus/prometheus/releases/download/v2.55.1/prometheus-2.55.1.linux-amd64.tar.gz -o prom.tar.gz
tar -xzf prom.tar.gz
sudo mv prometheus-2.55.1.linux-amd64/promtool /usr/local/bin/promtool
```

**Validation Steps** (in CI):
```bash
promtool check config monitoring/prometheus-config.yml
promtool check rules monitoring/prometheus-alerts.yml
promtool check rules monitoring/prometheus-recording-rules.yml
```

**CI Workflow**: `.github/workflows/monitoring-smoke.yml`  
Runs on push to:
- `monitoring/**`
- `pods/crm/**`
- `scripts/test_monitoring_stack.ps1`

**Local Validation**:
```bash
cd monitoring
make prom-lint
```

**Checks**:
- ✅ YAML syntax correctness
- ✅ PromQL query validity
- ✅ Label name compliance
- ✅ Alert/recording rule structure
- ✅ File reference correctness

---

## 🚨 New Alerts Summary

Total alerts in `crm_finance.rules` group: **11** (was 6)

| Alert | Severity | Detection Time | Purpose |
|-------|----------|----------------|---------|
| **LowInvoicePaymentRate** | warning | 4 hours | Payment rate < 60% for 4h |
| **RevenueZeroStreak** | critical | 6 hours | No revenue for 6h |
| **InvoiceGenerationStalled** | warning | 2 hours | No invoices created in 2h |
| **CrmApiDown** | critical | 5 minutes | CRM API not scraped for 5m |
| **CrmRecordingRulesStale** | warning | 10 minutes | Recording rules stop evaluating |
| **CrmMetricsScrapeStale** | critical | 10 minutes | Core metrics not scraped for 10m |
| **UptimeProbeFailing** | critical | 5 minutes | Blackbox probe failing |
| **PaymentRateSLOBurnFast** | warning | 30 minutes | Payment rate < 80% (fast) |
| **PaymentRateSLOBurnSlow** | critical | 6 hours | Payment rate < 75% (sustained) |
| **RevenueFlatlineFast** | warning | 90 minutes | No revenue ~2.5h |
| **RevenueFlatlineSlow** | critical | 8 hours | No revenue ~14h |

---

## 📈 Metrics Reference

### Blackbox Exporter Metrics
```promql
# Probe success (1 = success, 0 = failure)
probe_success{instance="http://crm-api:8080/metrics"}

# Probe duration in seconds
probe_duration_seconds{instance="http://crm-api:8080/metrics"}

# HTTP status code
probe_http_status_code{instance="http://crm-api:8080/metrics"}

# Count probes by status
count by (instance) (probe_success)

# Failed probes
probe_success == 0
```

### SLO Metrics (via Recording Rules)
```promql
# Payment rate percentage (30-day)
crm:payment_rate_30d_pct

# Revenue in USD (24h)
crm:revenue_usd

# Distance from SLO target
85 - crm:payment_rate_30d_pct

# Revenue flatline detection
sum(increase(crm_invoice_payments_cents_total[1h])) == 0
```

---

## 🛠️ Operations Guide

### Starting the Stack
```bash
cd monitoring
docker compose up -d
```

**Services Started**:
- prometheus (9090)
- alertmanager (9093)
- grafana (3000)
- blackbox (9115)
- crm-api (8089)
- postgres-crm (5432)
- minio (9000, 9001)
- mailhog (8025, 1025)
- aether-agent (8088)

### Verifying Blackbox Probes
```bash
# Check Blackbox exporter is running
curl http://localhost:9115/metrics | grep blackbox_exporter

# Query probe success in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=probe_success' | jq '.data.result[] | {instance: .metric.instance, success: .value[1]}'

# Check specific endpoint
curl -s 'http://localhost:9115/probe?target=http://crm-api:8080/metrics&module=http_2xx' | grep probe_success
```

### Checking Alert Status
```bash
# List all CRM finance alerts
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="crm_finance.rules") | .rules[] | select(.type=="alerting") | {name: .name, state: .state}'

# Check firing alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing") | {name: .labels.alertname, severity: .labels.severity}'
```

### Testing Healthchecks
```bash
# View health status for all services
docker ps --format 'table {{.Names}}\t{{.Status}}'

# Inspect specific healthcheck
docker inspect aether-prom | jq '.[0].State.Health'

# Test healthcheck command manually
docker exec aether-prom wget -qO- http://localhost:9090/-/ready
```

### Running Configuration Lint
```bash
# Local validation
cd monitoring
make prom-lint

# Manual promtool checks
promtool check config prometheus-config.yml
promtool check rules prometheus-alerts.yml
promtool check rules prometheus-recording-rules.yml
```

---

## 🧪 Testing & Validation

### Smoke Test (Full Stack)
```bash
cd monitoring
make smoke-test
```

**Validates**:
- ✅ Prometheus: 4 rule groups, 8 recording rules, 11 alerts loaded
- ✅ Grafana: Health API, datasource connectivity
- ✅ Alertmanager: Config loaded, receivers configured
- ✅ CRM API: Metrics endpoint, scrape health
- ✅ Blackbox: 5 probes configured and running

### Nightly CI Test
**Workflow**: `.github/workflows/monitoring-nightly.yml`  
**Schedule**: Daily at 03:17 UTC  
**Purpose**: Zero-deploy validation (catches silent failures)

**Steps**:
1. Start full stack
2. Wait for health (90s timeout per service)
3. Synthetic bump (increment counters)
4. Wait 30s for scrape
5. Run smoke test
6. Collect logs on failure
7. Teardown

### Manual Probe Test
```bash
# Test CRM API metrics probe
curl 'http://localhost:9115/probe?target=http://crm-api:8080/metrics&module=http_2xx'

# Expected output:
probe_success 1
probe_http_status_code 200
probe_duration_seconds 0.002

# Test QuickBooks status probe
curl 'http://localhost:9115/probe?target=http://crm-api:8080/qbo/status&module=http_2xx'

# Expected: probe_success 0 or 1 depending on auth
```

### Alert Dry Run
```bash
# Check if any alerts would fire based on current metrics
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="crm_finance.rules") | .rules[] | select(.type=="alerting") | select(.state=="pending" or .state=="firing") | {alert: .name, state: .state, duration: .duration}'
```

---

## 🐛 Troubleshooting

### Blackbox Exporter Issues

**Problem**: `probe_success == 0` for all targets

**Diagnosis**:
```bash
docker logs aether-blackbox --tail 50
curl http://localhost:9115/metrics | grep probe_
```

**Common Causes**:
1. Blackbox service not running
2. Target service unreachable from blackbox container
3. Incorrect module configuration in `blackbox.yml`
4. Network isolation (check `aether-monitoring` network)

**Fix**:
```bash
# Restart Blackbox
docker compose restart blackbox

# Check network connectivity
docker exec aether-blackbox wget -qO- http://crm-api:8080/metrics

# Verify configuration
docker exec aether-blackbox cat /etc/blackbox/blackbox.yml
```

---

### Healthcheck Never Becomes Healthy

**Problem**: Service stuck in `starting` or `unhealthy` state

**Diagnosis**:
```bash
docker inspect <container-name> | jq '.[0].State.Health'
docker logs <container-name> --tail 50
```

**Common Causes**:
1. Wrong port in healthcheck command
2. `wget` or `curl` not available in container
3. Service not actually healthy (check logs)
4. Healthcheck timeout too short

**Fix for crm-api** (Python container without wget/curl):
```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/metrics', timeout=2)\" || exit 1"]
```

---

### SLO Alerts Firing Incorrectly

**Problem**: PaymentRateSLOBurn alerts firing when payment rate seems fine

**Diagnosis**:
```bash
# Check current payment rate
curl -s 'http://localhost:9090/api/v1/query?query=crm:payment_rate_30d_pct' | jq '.data.result[0].value[1]'

# Check distance from SLO
curl -s 'http://localhost:9090/api/v1/query?query=85-crm:payment_rate_30d_pct' | jq '.data.result[0].value[1]'

# Verify recording rule evaluation
curl -s 'http://localhost:9090/api/v1/query?query=crm:payment_rate_30d_pct' | jq '.data.result[0].metric'
```

**Common Causes**:
1. Recording rule not evaluating (check `CrmRecordingRulesStale` alert)
2. Insufficient data (< 30 days)
3. Counter resets (Prometheus restart)

**Fix**:
```bash
# Restart Prometheus to reload recording rules
docker compose restart prometheus

# Wait for recording rules to evaluate (30s interval)
sleep 35

# Re-check
curl -s 'http://localhost:9090/api/v1/query?query=crm:payment_rate_30d_pct'
```

---

### promtool Lint Failures in CI

**Problem**: CI fails with "promtool check" errors

**Example Error**:
```
FAILED: parsing YAML: yaml: line 123: mapping values are not allowed in this context
```

**Diagnosis**:
```bash
# Run locally to see full error
cd monitoring
promtool check config prometheus-config.yml
promtool check rules prometheus-alerts.yml
```

**Common Causes**:
1. YAML syntax errors (indentation, quotes)
2. Invalid PromQL expressions
3. Missing required fields (expr, labels, annotations)
4. Invalid label names (must match `[a-zA-Z_][a-zA-Z0-9_]*`)

**Fix**:
1. Run `make prom-lint` locally before pushing
2. Use PromQL validator in Prometheus UI (Graph → Expression)
3. Check YAML syntax with online validator
4. Reference: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

---

## 📚 Related Documentation

- **[ALERTS_CRM_FINANCE.md](../runbooks/ALERTS_CRM_FINANCE.md)**: Runbook for all 11 CRM finance alerts
- **[SILENT_FAILURE_DETECTION.md](./SILENT_FAILURE_DETECTION.md)**: Nightly CI and staleness alerts
- **[CONTINUOUS_MONITORING_VALIDATION.md](./CONTINUOUS_MONITORING_VALIDATION.md)**: Smoke test script and CI pipeline
- **[QUICK_REFERENCE_FINANCE_MONITORING.md](./QUICK_REFERENCE_FINANCE_MONITORING.md)**: Daily ops commands

---

## 🎓 Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     Failure Prevention                       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌─────▼─────┐        ┌─────▼─────┐
   │ Blackbox│          │    SLO    │        │ promtool  │
   │ Probes  │          │  Alerts   │        │   Lint    │
   └─────────┘          └───────────┘        └───────────┘
        │                     │                     │
   Every 10s           Every 30s-8h            Pre-merge
        │                     │                     │
   ┌────▼────────────────────▼─────────────────────▼────┐
   │              Prometheus (9090)                      │
   │  • 5 uptime probes                                  │
   │  • 11 finance alerts                                │
   │  • 8 recording rules                                │
   └─────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────▼─────┐      ┌─────▼─────┐
              │Alertmanager│      │  Grafana  │
              │   (9093)   │      │  (3000)   │
              └────────────┘      └───────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    ┌────▼────┐          ┌─────▼─────┐
    │  Slack  │          │  Aether   │
    │ #crm-   │          │  Agent    │
    │ alerts  │          │  (8088)   │
    └─────────┘          └───────────┘
```

**Detection Layers**:
1. **Uptime Probes**: 5-minute endpoint failure detection
2. **SLO Burn-Rate**: 30m-8h business metric degradation
3. **Staleness Alerts**: 10-15m silent monitoring failure
4. **Nightly CI**: 24-hour zero-deploy validation
5. **Configuration Lint**: Pre-merge PromQL validation

---

## 🔐 Production Checklist

Before deploying to production:

- [ ] Set `SLACK_WEBHOOK_URL` environment variable for Slack notifications
- [ ] Uncomment Slack receiver configs in `alertmanager.yml`
- [ ] Adjust SLO targets (`85%` payment rate, revenue thresholds) for your business
- [ ] Configure alert `repeat_interval` based on on-call rotation schedule
- [ ] Add promtool lint to required CI checks (block merge on failure)
- [ ] Set up runbook links to point to your internal docs
- [ ] Configure Prometheus retention (`--storage.tsdb.retention.time=15d`)
- [ ] Review Blackbox probe targets (add/remove based on infrastructure)
- [ ] Test alert delivery end-to-end (fire test alert, verify Slack receipt)
- [ ] Document alert escalation procedures (who gets paged for critical alerts)

---

## 📊 Metrics Dashboard

**Key Queries** (add to Grafana dashboard):

**Uptime Overview**:
```promql
# Probe success rate (last 1h)
avg_over_time(probe_success[1h])

# Endpoints down right now
probe_success == 0

# Probe failure count (last 24h)
sum(changes(probe_success[24h])) by (instance)
```

**SLO Tracking**:
```promql
# Distance from payment rate SLO
85 - crm:payment_rate_30d_pct

# Hours until SLO violation (projected)
(crm:payment_rate_30d_pct - 75) / rate(crm:payment_rate_30d_pct[1h]) / 3600

# Revenue per hour (last 24h)
rate(crm_invoice_payments_cents_total[24h]) * 3600 / 100
```

---

**Last Updated**: 2025-11-02  
**Next Review**: Sprint 6 kickoff  
**Owner**: Platform/SRE Team  
**Contact**: #ops-alerts (Slack)
