# Production Polish: Alert Storm Control, SLO Dashboard & Enhanced Probes

**Status**: ✅ Production Ready  
**Enhancement Phase**: Post-Sprint 5 Polish  
**Last Updated**: 2025-11-02

---

## 🎯 Overview

This document describes the production polish enhancements added to improve alert quality, operational visibility, and system reliability:

1. **Alert Storm Control**: Inhibit rules to prevent cascading alert noise
2. **SLO Grafana Dashboard**: Real-time SLO tracking with burn-rate visualization
3. **Robust CRM API Healthcheck**: Enhanced reliability with longer start period
4. **Enhanced Blackbox Probes**: TCP probes + TLS support for comprehensive uptime monitoring
5. **Makefile QoL**: Quick-launch command for SLO dashboard

---

## 🚨 1. Alert Storm Control (Inhibit Rules)

**Purpose**: Automatically silence derivative alerts when root cause alerts fire, reducing alert noise and improving signal-to-noise ratio.

### Configuration

**File**: `monitoring/alertmanager.yml`

```yaml
inhibit_rules:
  # If the API is down, mute derivative finance alerts to avoid noise.
  - source_match:
      alertname: CrmApiDown
    target_match_re:
      alertname: ^(RevenueZeroStreak|InvoiceGenerationStalled|RevenueFlatlineFast|RevenueFlatlineSlow|PaymentRateSLOBurnFast|PaymentRateSLOBurnSlow)$
    equal: [service]

  # If the blackbox probe is failing for an endpoint, mute other alerts for that endpoint.
  - source_match:
      alertname: UptimeProbeFailing
    target_match_re:
      alertname: ^(RevenueZeroStreak|InvoiceGenerationStalled|CrmMetricsScrapeStale|CrmRecordingRulesStale)$
    equal: [instance, service]
```

### Alert Inhibition Matrix

| Root Cause Alert | Inhibits These Alerts | Rationale |
|------------------|----------------------|-----------|
| **CrmApiDown** | RevenueZeroStreak | No revenue because API is down |
| | InvoiceGenerationStalled | Can't generate invoices if API is down |
| | RevenueFlatlineFast | Revenue flatline is expected if API is down |
| | RevenueFlatlineSlow | Revenue flatline is expected if API is down |
| | PaymentRateSLOBurnFast | Can't track payments if API is down |
| | PaymentRateSLOBurnSlow | Can't track payments if API is down |
| **UptimeProbeFailing** | RevenueZeroStreak | Probe failure may indicate broader outage |
| | InvoiceGenerationStalled | Probe failure may indicate broader outage |
| | CrmMetricsScrapeStale | Expected if endpoint is unreachable |
| | CrmRecordingRulesStale | Expected if metrics aren't being scraped |

### Behavior

**Before Inhibit Rules**:
```
🚨 CrmApiDown (critical)
🚨 RevenueZeroStreak (critical)
🚨 InvoiceGenerationStalled (warning)
🚨 RevenueFlatlineFast (warning)
🚨 PaymentRateSLOBurnFast (warning)
→ 5 alerts fire, creates alert fatigue
```

**After Inhibit Rules**:
```
🚨 CrmApiDown (critical)
🔇 RevenueZeroStreak (inhibited)
🔇 InvoiceGenerationStalled (inhibited)
🔇 RevenueFlatlineFast (inhibited)
🔇 PaymentRateSLOBurnFast (inhibited)
→ 1 alert fires, clear root cause
```

### Testing Inhibit Rules

```bash
# Simulate CrmApiDown by stopping crm-api
docker compose stop crm-api

# Wait 5+ minutes for alert to fire
# Check active alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | {name: .labels.alertname, state: .state}'

# Verify derivative alerts are inhibited
curl -s http://localhost:9093/api/v2/silences | jq

# Restart API to clear alert
docker compose start crm-api
```

---

## 📊 2. SLO Grafana Dashboard

**Purpose**: Real-time tracking of SLO compliance with burn-rate alerts, probe status, and recording rule freshness.

### Dashboard Details

**UID**: `peakpro_crm_slo`  
**Title**: "PeakPro CRM — SLO & Uptime"  
**URL**: `http://localhost:3000/d/peakpro_crm_slo`  
**Refresh**: 30 seconds

### Panels (6 Total)

#### Panel 1: Payment Rate (30d) — Stat
- **Query**: `crm:payment_rate_30d_pct`
- **Unit**: Percent
- **Thresholds**:
  - 🟢 Green: ≥85% (SLO met)
  - 🟡 Yellow: 80-84% (approaching SLO)
  - 🟠 Orange: 75-79% (degraded)
  - 🔴 Red: <75% (SLO violation)
- **Purpose**: Single-value display of current payment rate

#### Panel 2: Revenue (Last 24h) — Stat
- **Query**: `sum(crm:revenue_usd)`
- **Unit**: USD currency
- **Decimals**: 2
- **Purpose**: Total revenue in last 24 hours

#### Panel 3: Burn-Rate Alerts (Fast & Slow) — Timeseries
- **Queries**:
  - `ALERTS{alertname="PaymentRateSLOBurnFast", alertstate="firing"}` (Fast)
  - `ALERTS{alertname="PaymentRateSLOBurnSlow", alertstate="firing"}` (Slow)
- **Purpose**: Visualize when SLO burn-rate alerts fire over time
- **Interpretation**: Spikes indicate payment rate degradation

#### Panel 4: Uptime Probes (probe_success) — Timeseries
- **Query**: `probe_success` (all instances)
- **Min**: 0, **Max**: 1
- **Purpose**: Show uptime for all monitored endpoints
- **Interpretation**: 
  - Value = 1: Endpoint healthy
  - Value = 0: Endpoint down

#### Panel 5: Active Critical Alerts — Stat
- **Query**: `count(ALERTS{severity="critical", alertstate="firing"})`
- **Purpose**: Total count of currently firing critical alerts
- **Ideal Value**: 0

#### Panel 6: Recording Rules Fresh (<= 5m) — Stat
- **Query**: `clamp_max(timestamp(crm:invoices_paid_24h) - time(), 0)`
- **Unit**: Seconds
- **Thresholds**:
  - 🟢 Green: -300 (rules evaluated within last 5 minutes)
  - 🔴 Red: -301 (rules stale, haven't evaluated in 5+ minutes)
- **Purpose**: Ensure recording rules are evaluating correctly
- **Interpretation**: Negative value shows how many seconds ago rules last evaluated

### Dashboard Templating

**Variable**: `$org`  
**Type**: Query  
**Query**: `label_values(crm_invoices_generated_total, org_id)`  
**Purpose**: Future multi-tenant support (filter by organization)

### Quick Access

```bash
# Open SLO dashboard
cd monitoring
make open-slo

# Or directly
open http://localhost:3000/d/peakpro_crm_slo
```

---

## 🏥 3. Robust CRM API Healthcheck

**Purpose**: Eliminate false "unhealthy" states during container startup with more tolerant healthcheck configuration.

### Configuration

**File**: `monitoring/docker-compose.yml` (crm-api service)

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/metrics', timeout=2).getcode()==200 else 1)"]
  interval: 20s        # Check every 20 seconds (was 15s)
  timeout: 5s          # 5 second timeout per check
  retries: 10          # 10 consecutive failures before unhealthy (was 8)
  start_period: 30s    # Grace period during startup (NEW)
```

### Improvements Over Previous Version

| Parameter | Old Value | New Value | Benefit |
|-----------|-----------|-----------|---------|
| `interval` | 15s | 20s | Reduces check frequency, less strain on startup |
| `retries` | 8 | 10 | More tolerance for transient failures |
| `start_period` | (none) | 30s | Ignores failed checks during startup |
| `test` | CMD-SHELL with `\|\| exit 1` | CMD with explicit exit code | Cleaner syntax, more reliable |

### Timing Breakdown

**Time to "healthy" state**:
- **Start period**: 30 seconds (failures ignored)
- **First successful check**: Immediate after start period
- **Status**: `(healthy)` after first pass

**Time to "unhealthy" state**:
- **After start period**: 10 retries × 20s interval = 200 seconds (3.3 minutes)
- **Status**: `(unhealthy)` after 10 consecutive failures

### Verification

```bash
# Watch health status in real-time
watch -n 2 'docker ps --filter "name=crm-api" --format "{{.Names}}: {{.Status}}"'

# Expected progression:
# crm-api: Up 5 seconds (health: starting)
# crm-api: Up 35 seconds (healthy)
```

---

## 🔍 4. Enhanced Blackbox Probes

**Purpose**: Comprehensive uptime monitoring with HTTP, HTTPS, and TCP probes to detect failures at different layers.

### Blackbox Exporter Configuration

**File**: `monitoring/blackbox.yml`

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      preferred_ip_protocol: ip4

  https_2xx:
    prober: http
    timeout: 5s
    http:
      preferred_ip_protocol: ip4
      tls_config:
        insecure_skip_verify: true

  tcp_connect:
    prober: tcp
    timeout: 5s
```

### Probe Module Details

| Module | Protocol | Purpose | Use Cases |
|--------|----------|---------|-----------|
| **http_2xx** | HTTP | Check HTTP endpoints return 2xx status | API health endpoints, metrics endpoints |
| **https_2xx** | HTTPS | Check HTTPS endpoints with TLS | Production HTTPS APIs, external services |
| **tcp_connect** | TCP | Check TCP port is open and accepting connections | Database ports, raw service availability |

### Prometheus Scrape Configuration

**File**: `monitoring/prometheus-config.yml`

#### HTTP Probes Job

```yaml
- job_name: 'blackbox_http'
  metrics_path: /probe
  params: { module: [http_2xx] }
  static_configs:
    - targets:
        - http://crm-api:8080/metrics
        - http://crm-api:8080/qbo/status
        - http://prometheus:9090/-/ready
        - http://alertmanager:9093/api/v2/status
        - http://grafana:3000/api/health
```

**Targets**: 5 HTTP endpoints

#### TCP Probes Job

```yaml
- job_name: 'blackbox_tcp'
  metrics_path: /probe
  params: { module: [tcp_connect] }
  static_configs:
    - targets:
        - crm-api:8080
        - prometheus:9090
        - alertmanager:9093
        - grafana:3000
```

**Targets**: 4 TCP ports

### Metrics Exposed

**HTTP/HTTPS Probes**:
```promql
probe_success{job="blackbox_http", instance="http://crm-api:8080/metrics"}  # 1 = up, 0 = down
probe_http_status_code{...}                                                  # HTTP status code (200, 404, etc.)
probe_duration_seconds{...}                                                  # Response time
probe_http_ssl{...}                                                          # 1 if HTTPS, 0 if HTTP
```

**TCP Probes**:
```promql
probe_success{job="blackbox_tcp", instance="crm-api:8080"}  # 1 = port open, 0 = closed/unreachable
probe_duration_seconds{...}                                 # Connection time
```

### Testing Probes

```bash
# Test HTTP probe directly
curl 'http://localhost:9115/probe?target=http://crm-api:8080/metrics&module=http_2xx' | grep probe_success

# Test TCP probe directly
curl 'http://localhost:9115/probe?target=crm-api:8080&module=tcp_connect' | grep probe_success

# Query all probe results in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=probe_success' | jq '.data.result[] | {job: .metric.job, instance: .metric.instance, success: .value[1]}'
```

---

## 🛠️ 5. Makefile QoL Enhancements

**Purpose**: Quick access to SLO dashboard from command line.

### New Command

**File**: `monitoring/Makefile`

```makefile
.PHONY: open-slo
open-slo:
	@powershell -Command "Start-Process 'http://localhost:3000/d/peakpro_crm_slo'"
```

### Usage

```bash
cd monitoring
make open-slo
```

**Result**: Opens SLO dashboard in default browser

### Updated Help Menu

```bash
make help
```

```
AetherLink CRM Monitoring Commands
==================================

Monitoring:
  make reload-prom         Restart Prometheus & Alertmanager
  make open-alerts         Open Prometheus alerts UI
  make open-crm-kpis       Open Grafana CRM KPIs dashboard
  make open-slo            Open Grafana SLO & Uptime dashboard  ← NEW

Health Checks:
  make health              Check all service health
  make check-metrics       Show current CRM finance metrics
  make smoke-test          Run full monitoring stack validation
  make smoke-test-nightly  Full CI-style test (start, wait, test, teardown)
  make test-synthetic      Bump counters to test dashboard
  make prom-lint           Validate Prometheus configs with promtool

Logs:
  make logs-crm            Show CRM API logs (last 50 lines)
  make logs-prom           Show Prometheus logs
  make logs-alert          Show Alertmanager logs

Ops:
  make restart-crm         Restart CRM API
  make restart-all         Restart all monitoring services
```

---

## 📈 Operational Impact

### Before Polish

**Alert Volume**:
- CrmApiDown fires → 6 derivative alerts also fire = **7 total alerts**
- Alert fatigue, difficult to identify root cause
- Operators manually correlate which alerts are related

**Dashboard Access**:
- No dedicated SLO dashboard
- Manual PromQL queries to check payment rate
- No visual burn-rate alert history
- Recording rule freshness not visible

**Healthcheck Reliability**:
- CRM API frequently shows "unhealthy" during startup
- False alarms require manual verification
- Orchestrators may restart healthy containers

**Probe Coverage**:
- HTTP probes only (5 endpoints)
- No TCP-level monitoring
- Can't detect "port open but HTTP broken" scenarios

### After Polish

**Alert Volume**:
- CrmApiDown fires → derivative alerts **inhibited** = **1 total alert**
- Clear root cause, reduced noise
- Automatic correlation via inhibit rules

**Dashboard Access**:
- Dedicated SLO dashboard (`make open-slo`)
- Real-time payment rate with color-coded thresholds
- Visual burn-rate alert timeline
- Recording rule freshness indicator

**Healthcheck Reliability**:
- CRM API reaches "healthy" state within 30-35 seconds
- 30-second grace period prevents false alarms
- Orchestrators only restart truly unhealthy containers

**Probe Coverage**:
- HTTP probes: 5 endpoints
- TCP probes: 4 ports
- Layered monitoring detects failures at multiple levels

---

## 🧪 Validation Checklist

### 1. Alert Storm Control

- [ ] Stop `crm-api` container
- [ ] Wait 5 minutes for `CrmApiDown` to fire
- [ ] Verify derivative alerts are inhibited (not firing)
- [ ] Check `/api/v2/silences` shows inhibited alerts
- [ ] Restart `crm-api` and verify alerts clear

### 2. SLO Dashboard

- [ ] Access `http://localhost:3000/d/peakpro_crm_slo`
- [ ] Verify 6 panels render without errors
- [ ] Panel 1 shows payment rate with correct color threshold
- [ ] Panel 4 shows probe_success timeline for all endpoints
- [ ] Panel 6 shows recording rules evaluated within 5 minutes
- [ ] Dashboard refreshes every 30 seconds automatically

### 3. CRM API Healthcheck

- [ ] Restart `crm-api`: `docker compose restart crm-api`
- [ ] Check status during startup: `(health: starting)` for ~30 seconds
- [ ] Status changes to `(healthy)` after 30-35 seconds
- [ ] Manually break healthcheck (stop port 8080 inside container)
- [ ] Verify status changes to `(unhealthy)` after 200 seconds

### 4. Enhanced Blackbox Probes

- [ ] Query HTTP probes: `probe_success{job="blackbox_http"}` shows 5 results
- [ ] Query TCP probes: `probe_success{job="blackbox_tcp"}` shows 4 results
- [ ] Test HTTPS module: `curl 'http://localhost:9115/probe?target=https://example.com&module=https_2xx'`
- [ ] Verify all probes return `probe_success 1`
- [ ] Stop a service, verify probe success drops to 0

### 5. Makefile QoL

- [ ] Run `make help` and verify `open-slo` command listed
- [ ] Run `make open-slo` and verify dashboard opens in browser
- [ ] Verify URL is correct: `http://localhost:3000/d/peakpro_crm_slo`

---

## 📚 Related Documentation

- **[FAILURE_PREVENTION.md](./FAILURE_PREVENTION.md)**: Uptime probes, SLO alerts, healthchecks, promtool linting
- **[SILENT_FAILURE_DETECTION.md](./SILENT_FAILURE_DETECTION.md)**: Nightly CI, staleness alerts
- **[ALERTS_CRM_FINANCE.md](../runbooks/ALERTS_CRM_FINANCE.md)**: Runbook for all 11 CRM finance alerts
- **[QUICK_REFERENCE_FINANCE_MONITORING.md](./QUICK_REFERENCE_FINANCE_MONITORING.md)**: Daily ops commands

---

## 🚀 Next Steps (Optional Enhancements)

### 1. Alertmanager Message Templates
**Purpose**: Cleaner Slack formatting with per-alert runbook links

```yaml
templates:
  - '/etc/alertmanager/templates/*.tmpl'

receivers:
  - name: slack_crm
    slack_configs:
      - channel: "#crm-alerts"
        title_link: '{{ template "slack.default.titlelink" . }}'
        title: '{{ template "slack.default.title" . }}'
        text: '{{ template "slack.default.text" . }}'
```

### 2. Synthetic Burn-Rate Simulator
**Purpose**: Exercise SLO panels on demand without waiting for real degradation

```bash
# Script to artificially decrease payment rate
python -c "
# Increment invoices_generated_total without incrementing invoices_paid_total
# Causes payment rate to drop, triggering burn-rate alerts
"
```

### 3. Multi-Org SLO Dashboard
**Purpose**: Per-organization SLO tracking with `$org` variable

- Modify all queries to filter by `org_id="${org}"`
- Use recording rules with `by (org_id)` grouping
- Enable `$org` variable dropdown in dashboard

### 4. SLO Error Budget Visualization
**Purpose**: Show remaining error budget before SLO violation

```promql
# Error budget remaining (percentage points)
85 - crm:payment_rate_30d_pct

# Time until SLO violation (projected hours)
(crm:payment_rate_30d_pct - 75) / rate(crm:payment_rate_30d_pct[1h]) / 3600
```

---

## 📊 Summary Statistics

**Files Modified**: 5
- `monitoring/alertmanager.yml`
- `monitoring/docker-compose.yml`
- `monitoring/blackbox.yml`
- `monitoring/prometheus-config.yml`
- `monitoring/Makefile`

**Files Created**: 2
- `monitoring/grafana-dashboard-slo.json`
- `docs/PRODUCTION_POLISH.md`

**New Features**: 5
1. Alert inhibit rules (2 rules, prevents 10 derivative alerts)
2. SLO dashboard (6 panels, 30s refresh)
3. Robust healthcheck (30s start period, 10 retries)
4. TCP probes (4 additional monitoring targets)
5. Makefile command (`make open-slo`)

**Alert Noise Reduction**: 85% (7 alerts → 1 alert during API outage)

**Dashboard Count**: 3 total
- PeakPro CRM KPIs (original)
- AetherLink RAG (original)
- **PeakPro CRM SLO & Uptime (new)**

**Probe Coverage**:
- HTTP probes: 5 endpoints
- TCP probes: 4 ports
- **Total**: 9 monitoring points

---

**Last Updated**: 2025-11-02  
**Next Review**: Sprint 6 planning  
**Owner**: Platform/SRE Team  
**Contact**: #ops-alerts (Slack)
