# AetherVision: Predictive SLO Intelligence & Unified Operations View

**Status**: ✅ **OPERATIONAL**  
**Deployed**: 2025-11-03  
**Version**: 1.0

## Overview

AetherVision transforms your monitoring from reactive ("Is it bad now?") to predictive ("How long do we have?"). It provides:

1. **Predictive SLO Intelligence** - Calculate runway to SLO breach based on current burn rates
2. **Unified Operations View** - Single pane of glass for alerts, probes, autoheal status, and SLO health
3. **Actionable Foresight** - Alert early when runway is short, not on every metric blip

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AetherVision Stack                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Autoheal    │───▶│  Prometheus  │───▶│   Grafana    │  │
│  │  /metrics    │    │  Recording   │    │  AetherVision│  │
│  └──────────────┘    │  Rules       │    │  Dashboard   │  │
│                      └──────────────┘    └──────────────┘  │
│                             │                                │
│                             ▼                                │
│                      ┌──────────────┐                       │
│                      │  Predictive  │                       │
│                      │  Alerts      │                       │
│                      └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Components Deployed

### 1. Autoheal Metrics Exporter ✅
**File**: `monitoring/autoheal/main.py`

Exposes Prometheus metrics at `http://localhost:9009/metrics`:

```prometheus
# HELP autoheal_enabled Whether autoheal is enabled (1/0)
# TYPE autoheal_enabled gauge
autoheal_enabled 0.0

# HELP autoheal_actions_total Total autoheal actions executed
# TYPE autoheal_actions_total counter

# HELP autoheal_last_action_epoch Unix epoch of last autoheal action
# TYPE autoheal_last_action_epoch gauge
autoheal_last_action_epoch 0.0
```

**Scrape Configuration**: Added to `prometheus-config.yml` as job `autoheal`

### 2. Predictive SLO Recording Rules ✅
**File**: `monitoring/prometheus-recording-rules.yml`

**Group**: `slo_payment_rate.predict.recording`

#### Metrics Generated:

| Metric | Formula | Purpose |
|--------|---------|---------|
| `slo:payment_rate:hours_to_breach_1h` | `(EBR * 720h) / burn_1h` | Runway based on 1h burn rate |
| `slo:payment_rate:hours_to_breach_6h` | `(EBR * 720h) / burn_6h` | Runway based on 6h burn rate |
| `slo:payment_rate:hours_to_breach` | `min(1h, 6h)` | Conservative runway estimate |
| `slo:payment_rate:days_to_breach` | `hours_to_breach / 24` | Human-friendly days remaining |

**Example Query**:
```promql
# How many days until SLO breach at current burn rate?
slo:payment_rate:days_to_breach
```

### 3. AetherVision Aggregation Rules ✅
**File**: `monitoring/prometheus-recording-rules.yml`

**Group**: `aethervision.recording`

#### Metrics Generated:

| Metric | Purpose |
|--------|---------|
| `aethervision:alerts:count` | Total firing alerts |
| `aethervision:alerts_critical:count` | Critical alerts only |
| `aethervision:alerts_warning:count` | Warning alerts only |
| `aethervision:probes_http_up` | Healthy HTTP probes |
| `aethervision:probes_tcp_up` | Healthy TCP probes |
| `aethervision:days_to_breach` | Alias for SLO runway |
| `aethervision:autoheal_enabled` | Is autoheal currently enabled? |
| `aethervision:autoheal_last_action_age` | Seconds since last autoheal action |

### 4. Predictive Alerts ✅
**File**: `monitoring/prometheus-alerts.yml`

**Group**: `slo_payment_rate.alerts`

#### PaymentRatePredictedBreachSoon
- **Trigger**: Runway < 24 hours
- **Severity**: warning
- **For**: 15m
- **Message**: "Current burn trend projects SLO budget exhaustion in ~XX hours"
- **Action**: Investigate payment failures, pause risky deploys

#### PaymentRatePredictedBreachCritical
- **Trigger**: Runway < 6 hours
- **Severity**: critical
- **For**: 10m
- **Message**: "Runway ~XX hours. Budget will be exhausted soon at current burn"
- **Action**: Declare incident, rollback changes, throttle flows

### 5. AetherVision Operator Alerts ✅
**File**: `monitoring/prometheus-alerts.yml`

**Group**: `aethervision.alerts`

#### AutohealDisabledInDev
- **Trigger**: `autoheal_enabled == 0` for 10m
- **Severity**: info
- **Purpose**: Remind operators that autoheal is disabled (expected in prod)

#### AutohealStaleActions
- **Trigger**: Enabled but no actions in 24h
- **Severity**: warning
- **Purpose**: Detect misconfigured autoheal mappings

#### ProbesCoverageLow
- **Trigger**: < 5 healthy probes
- **Severity**: warning
- **Purpose**: Alert on degraded observability coverage

### 6. Makefile Commands ✅

```makefile
# SLO Runway
make show-breach       # Display days/hours to SLO breach
make open-vision       # Open AetherVision dashboard

# Quick Status
make vision-verify     # Quick AetherVision health check
```

## Current Metrics

**Validation Results**:
```
✅ Recording Rules: 37 total
✅ Alert Rules: 39 total
✅ Autoheal metrics: Exposed on port 9009
✅ AetherVision metrics: All 8 recording rules active
```

**Live AetherVision State**:
```
aethervision:alerts:count = 3
aethervision:alerts_critical:count = 2
aethervision:probes_http_up = 4
aethervision:autoheal_enabled = 0 (disabled)
```

## Usage Examples

### Query SLO Runway
```bash
# PowerShell
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=slo:payment_rate:days_to_breach"

# PromQL (Grafana)
slo:payment_rate:days_to_breach

# Expected output
{
  "metric": {"service": "crm", "component": "slo"},
  "value": [1762132900, "12.5"]  # 12.5 days remaining
}
```

### Check Autoheal Status
```bash
# Via Prometheus
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=aethervision:autoheal_enabled"

# Via Autoheal directly
Invoke-RestMethod "http://localhost:9009/"
```

### Simulate SLO Burn
```powershell
# Increase burn rate (degrade payment rate)
.\scripts\simulate_payment_rate_dip.ps1

# Watch runway decrease
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=slo:payment_rate:hours_to_breach"

# Alerts should fire:
# - PaymentRatePredictedBreachSoon (runway < 24h)
# - PaymentRatePredictedBreachCritical (runway < 6h)
```

### Recovery Simulation
```powershell
# Improve payment rate
.\scripts\simulate_payment_rate_recovery.ps1

# Watch runway increase
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=slo:payment_rate:days_to_breach"
```

## Dashboard Integration (Next Step)

To add AetherVision panels to Grafana:

### Panel 1: Days to Breach (Gauge)
```json
{
  "type": "stat",
  "title": "🧭 Days to Breach (Conservative)",
  "targets": [{"expr": "aethervision:days_to_breach"}],
  "fieldConfig": {
    "defaults": {
      "unit": "d",
      "thresholds": {
        "steps": [
          {"color": "red", "value": 0},
          {"color": "orange", "value": 5},
          {"color": "yellow", "value": 10},
          {"color": "green", "value": 20}
        ]
      }
    }
  }
}
```

### Panel 2: Runway Trend (Time Series)
```json
{
  "type": "timeseries",
  "title": "Runway to Breach (hours) — 1h vs 6h",
  "targets": [
    {"expr": "slo:payment_rate:hours_to_breach_1h", "legendFormat": "1h burn"},
    {"expr": "slo:payment_rate:hours_to_breach_6h", "legendFormat": "6h burn"},
    {"expr": "slo:payment_rate:hours_to_breach", "legendFormat": "conservative"}
  ]
}
```

### Panel 3: Operations KPIs
```json
{
  "type": "stat",
  "title": "Ops Snapshot",
  "targets": [
    {"expr": "aethervision:alerts_critical:count", "legendFormat": "Critical Alerts"},
    {"expr": "aethervision:probes_http_up + aethervision:probes_tcp_up", "legendFormat": "Probes Up"},
    {"expr": "aethervision:autoheal_enabled", "legendFormat": "Autoheal"}
  ]
}
```

## Benefits

### Before AetherVision
- ❌ Reactive: Alert fires → scramble to fix
- ❌ Noisy: Alert on every metric blip
- ❌ Blind: No visibility into "time remaining"
- ❌ Manual: Check multiple dashboards for ops status

### After AetherVision
- ✅ Proactive: "You have 18 hours to fix this"
- ✅ Signal-focused: Alert when runway is short
- ✅ Forecasting: Math-based prediction of SLO breach
- ✅ Unified: One view for alerts + probes + autoheal + SLO

## Operational Runbook

### Scenario 1: PaymentRatePredictedBreachSoon (24h runway)
**Actions**:
1. Review payment processor errors: `make logs-crm`
2. Check QBO sync health: Grafana → CRM KPIs
3. Investigate recent deployments: `git log --since="24 hours ago"`
4. Consider pausing non-critical deploys
5. Monitor runway: `make show-breach`

### Scenario 2: PaymentRatePredictedBreachCritical (6h runway)
**Actions**:
1. **DECLARE INCIDENT** - Page on-call SRE
2. Rollback last deployment: `git revert HEAD; make restart-crm`
3. Throttle risky flows (disable non-essential background jobs)
4. Enable autoheal for critical services: `docker exec autoheal sed -i 's/AUTOHEAL_ENABLED=false/AUTOHEAL_ENABLED=true/' .env; docker restart autoheal`
5. Watch alerts: `http://localhost:9090/alerts`
6. Track recovery: `make show-breach` every 5 minutes

### Scenario 3: AutohealStaleActions
**Actions**:
1. Check autoheal is enabled: `Invoke-RestMethod http://localhost:9009/`
2. Verify alert annotations have `autoheal: "true"`: `grep autoheal prometheus-alerts.yml`
3. Check Alertmanager route: `grep autoheal alertmanager.yml`
4. Review autoheal logs: `docker logs aether-autoheal --tail 50`
5. Test with chaos: `make chaos-tcp` (should trigger TcpEndpointDownFast → autoheal action)

## Troubleshooting

### Problem: Days to breach shows N/A

**Cause**: No payment metrics flowing yet

**Solution**:
```bash
# Run payment rate simulator
.\scripts\simulate_payment_rate_dip.ps1

# Wait 30s for recording rules to evaluate
Start-Sleep -Seconds 30

# Check again
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=slo:payment_rate:days_to_breach"
```

### Problem: Autoheal metrics not appearing

**Cause**: Autoheal not running with dev profile

**Solution**:
```bash
# Verify autoheal container running
docker ps | grep autoheal

# If not running, start with dev profile
cd monitoring
docker compose --profile dev up -d autoheal

# Check metrics endpoint
Invoke-RestMethod http://localhost:9009/metrics | Select-String autoheal
```

### Problem: AetherVision metrics return 0

**Cause**: Prometheus hasn't scraped autoheal yet

**Solution**:
```bash
# Force Prometheus reload
Invoke-RestMethod -Method POST http://localhost:9090/-/reload

# Wait for next scrape interval (10s)
Start-Sleep -Seconds 15

# Check target health
Invoke-RestMethod "http://localhost:9090/api/v1/targets" | 
  Select-Object -ExpandProperty data | 
  Select-Object -ExpandProperty activeTargets | 
  Where-Object { $_.labels.job -eq 'autoheal' }
```

## Next Steps

### Optional Enhancements
1. **Grafana Dashboard**: Add AetherVision row to existing SLO dashboard
2. **Slack Integration**: Include runway in Slack alert messages
3. **Chaos Playbook**: Automated failure injection + pre/post checks
4. **Multi-Service SLO**: Extend predictions to CRM, Agent, Invoice services
5. **Capacity Planning**: Historical runway trends for capacity decisions

### Monitoring the Monitors
```bash
# Daily health check
make vision-verify

# Expected output:
# ✅ 37 recording rules
# ✅ 39 alert rules
# ✅ Days to breach: 18.5
# ✅ Alerts firing: 2
# ✅ Autoheal: disabled
```

## References

- [Production Safety Documentation](./PRODUCTION_SAFETY.md)
- [SLO Metrics Guide](./SLO_METRICS.md)
- [Alerting Runbooks](./runbooks/ALERTS_CRM_FINANCE.md)
- [Prometheus Recording Rules](../prometheus-recording-rules.yml)
- [Prometheus Alerts](../prometheus-alerts.yml)

---

**Maintained By**: DevOps Team  
**Review Cadence**: Monthly  
**Last Updated**: 2025-11-03
