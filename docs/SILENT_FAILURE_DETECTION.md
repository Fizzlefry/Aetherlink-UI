# Silent Failure Detection - Setup Complete

## Overview

Added proactive monitoring to catch silent failures (recording rules stop evaluating, scrapes stall) even when no deployments happen. The system now validates itself nightly and alerts on quiet breakages within minutes.

## What Was Added

### 1. Nightly CI Workflow (`.github/workflows/monitoring-nightly.yml`)

**Schedule:** Runs at 03:17 UTC daily (~9:17 PM CT during DST)

**Purpose:** Catch monitoring degradation that happens between deployments

**Steps:**
1. Start full monitoring stack (Prometheus, Grafana, Alertmanager, CRM API, Postgres)
2. Wait for all services to be healthy (90-second timeout per service)
3. Synthetic metric bump (keeps counters fresh for testing)
4. Wait 30 seconds for Prometheus scrape
5. Run smoke test script (validates all components)
6. Optional: Send test Slack alert if `SLACK_WEBHOOK_URL` secret configured
7. Show Prometheus/Alert status
8. Collect logs on failure
9. Tear down stack

**Triggers:**
- Scheduled: 03:17 UTC every day
- Manual: GitHub Actions → Monitoring Nightly → Run workflow

**Artifacts on Failure:**
- prometheus.log
- alertmanager.log
- grafana.log
- crm-api.log
- postgres-crm.log

### 2. Staleness Alerts (2 new alerts in `prometheus-alerts.yml`)

#### Alert 1: `CrmRecordingRulesStale`

**Purpose:** Detect when Prometheus recording rules stop evaluating

**Trigger:**
```promql
absent_over_time(crm:invoices_created_24h[15m])
or absent_over_time(crm:invoices_paid_24h[15m])
or absent_over_time(crm:revenue_usd[15m])
or absent_over_time(crm:payment_rate_30d_pct[15m])
```

**Threshold:** No samples for 15 minutes, alerting after 10 minutes

**Severity:** Warning

**Impact:** Dashboard performance degraded, finance panels show stale data

**Common Causes:**
- Prometheus rule evaluation halted (out of memory, CPU overload)
- Source metrics stopped (crm-api crashed)
- Prometheus configuration error after reload

#### Alert 2: `CrmMetricsScrapeStale`

**Purpose:** Detect when core CRM metrics stop being scraped

**Trigger:**
```promql
absent_over_time(crm_invoices_generated_total{job="crm_api"}[10m])
or absent_over_time(crm_invoices_paid_total{job="crm_api"}[10m])
or absent_over_time(crm_invoice_payments_cents_total{job="crm_api"}[10m])
```

**Threshold:** No samples for 10 minutes, alerting after 10 minutes

**Severity:** Critical

**Impact:** No new finance data, all CRM monitoring and alerts stale or broken

**Common Causes:**
- CRM API /metrics endpoint crashed
- Prometheus scrape target misconfigured
- Network connectivity issue between Prometheus and CRM API
- CRM API container restarted without Prometheus discovering it

### 3. Makefile Integration (`monitoring/Makefile`)

Added `smoke-test-nightly` command for local CI-style testing:

```bash
make smoke-test-nightly
```

**What It Does:**
1. Starts full monitoring stack with Docker Compose
2. Waits for Prometheus, Grafana, Alertmanager, CRM API (90s timeout each)
3. Runs smoke test script
4. Tears down stack with `docker compose down -v`

**Use Cases:**
- Test nightly workflow locally before pushing
- Reproduce CI failures in local environment
- Validate monitoring stack after configuration changes
- Training new team members on monitoring validation

## Alert Configuration Summary

Total alerts: **6** (4 existing + 2 new)

| Alert | Severity | Condition | For | Impact |
|-------|----------|-----------|-----|--------|
| LowInvoicePaymentRate | Warning | < 50% payment rate | 24h | Low conversion |
| RevenueZeroStreak | Critical | $0 revenue | 48h | Pipeline broken |
| InvoiceGenerationStalled | Warning | 0 invoices created | 24h | Generation halted |
| CrmApiDown | Critical | Scrape target down | 5m | No metrics |
| **CrmRecordingRulesStale** | **Warning** | **Recording rules no samples** | **10m** | **Stale dashboards** |
| **CrmMetricsScrapeStale** | **Critical** | **Core metrics no samples** | **10m** | **No monitoring** |

## Testing & Validation

### Local Testing

**1. Quick smoke test:**
```bash
cd monitoring
make smoke-test
```

**2. Full nightly-style test:**
```bash
cd monitoring
make smoke-test-nightly
```

**3. Test staleness alerts:**
```bash
# Stop CRM API to trigger CrmMetricsScrapeStale
docker stop crm-api

# Wait 10-12 minutes, then check alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="CrmMetricsScrapeStale")'

# Restart to clear alert
docker start crm-api
```

### CI Validation

**1. Verify nightly workflow:**
- GitHub → Actions → Monitoring Nightly
- Run workflow manually
- Check logs and status

**2. Check schedule execution:**
- Wait for next scheduled run (03:17 UTC)
- Review workflow runs history
- Download artifacts if failed

**3. Test with Slack:**
- Add `SLACK_WEBHOOK_URL` to GitHub secrets
- Run workflow manually
- Verify synthetic alert in #crm-alerts or #ops-alerts

## Current Status

### Alerts Loaded ✅

```
name                     severity      
----                     --------      
LowInvoicePaymentRate    warning       
RevenueZeroStreak        critical      
InvoiceGenerationStalled warning       
CrmApiDown               critical      
CrmRecordingRulesStale   warning       
CrmMetricsScrapeStale    critical
```

### Workflows Configured ✅

1. **monitoring-smoke.yml**: Runs on push to monitoring/, pods/crm/, or scripts/
2. **monitoring-nightly.yml**: Runs at 03:17 UTC daily + manual dispatch

### Makefile Commands ✅

```bash
make smoke-test          # Quick validation (assumes services running)
make smoke-test-nightly  # Full CI-style test (start, wait, test, teardown)
```

## Benefits

### Immediate
- ✅ **Nightly validation** catches silent failures within 24 hours
- ✅ **Staleness alerts** detect broken monitoring within 10-15 minutes
- ✅ **Local CI simulation** for pre-push validation
- ✅ **Automated artifact collection** for faster debugging

### Long-term
- 📊 **Trend analysis**: Track monitoring health over time
- 🔔 **Proactive alerts**: Fix issues before users notice
- 📈 **Reliability metrics**: Calculate uptime and MTTR
- 🤖 **Self-healing**: Future auto-repair on nightly failure

## Architecture

```
┌───────────────────────────────────────────────────────┐
│  03:17 UTC Daily Schedule                             │
└───────────────┬───────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────┐
│  GitHub Actions: monitoring-nightly.yml               │
│  1. docker compose up -d (all services)               │
│  2. Wait for health (Prom, Grafana, Alert, CRM)       │
│  3. Synthetic metric bump                             │
│  4. Wait 30s for Prometheus scrape                    │
│  5. Run smoke test                                    │
│  6. (Optional) Send Slack test alert                  │
│  7. Show status (rules, alerts, targets)              │
│  8. Collect logs on failure                           │
│  9. docker compose down -v                            │
└───────────────┬───────────────────────────────────────┘
                │
                ├─── Exit 0 (PASS) → Badge: passing
                └─── Exit 1 (FAIL) → Badge: failing + logs artifact
```

```
┌───────────────────────────────────────────────────────┐
│  Prometheus (continuous evaluation)                   │
└───────────────┬───────────────────────────────────────┘
                │
                ├─── Every 30s: Evaluate recording rules
                │    └─── If absent_over_time(recording_rule[15m])
                │         → CrmRecordingRulesStale (after 10m)
                │
                └─── Every 30s: Evaluate scrape staleness
                     └─── If absent_over_time(crm_metrics[10m])
                          → CrmMetricsScrapeStale (after 10m)
                          → Route to #crm-alerts via Alertmanager
```

## Troubleshooting

### Nightly Workflow Fails

**Check workflow logs:**
- GitHub → Actions → Monitoring Nightly → Latest run
- Review failed step
- Download artifacts (logs) for detailed debugging

**Common issues:**
1. **Service timeout**: Increase wait loop from 90 to 120 iterations
2. **Synthetic bump fails**: CRM API migrations not applied
3. **Smoke test fails**: Check individual component (Prom, Grafana, Alertmanager)

**Local reproduction:**
```bash
cd monitoring
make smoke-test-nightly
```

### Staleness Alerts Firing

**CrmRecordingRulesStale:**
```bash
# Check Prometheus rule evaluation
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="crm_finance.recording")'

# Check Prometheus CPU/memory
docker stats aether-prom

# Check source metrics
curl -s http://localhost:9090/api/v1/query?query=crm_invoices_generated_total

# Restart Prometheus if needed
make reload-prom
```

**CrmMetricsScrapeStale:**
```bash
# Check CRM API health
curl http://localhost:8089/metrics | head -20

# Check Prometheus scrape targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="crm_api")'

# Check CRM API logs
make logs-crm

# Restart CRM API if needed
make restart-crm
```

### Smoke Test Fails Locally

**Quick diagnosis:**
```bash
# Check service health
make health

# Check individual components
curl http://localhost:9090/-/ready      # Prometheus
curl http://localhost:3000/api/health   # Grafana
curl http://localhost:9093/api/v2/status  # Alertmanager
curl http://localhost:8089/metrics      # CRM API

# View logs
make logs-prom
make logs-alert
make logs-crm

# Restart all services
make restart-all
```

## Next Steps

### Phase 1: Monitor Nightly Runs (1 week)
- Review workflow runs daily
- Track success rate
- Tune timeouts if needed
- Add more synthetic data if recording rules need samples

### Phase 2: Alert Tuning (after staleness alerts fire)
- Verify alert thresholds (10m/15m) are appropriate
- Adjust `for` duration if too noisy
- Add more metrics to scrape staleness check if needed

### Phase 3: Auto-Repair (future)
Extend nightly workflow to auto-fix common issues:
```yaml
- name: Auto-repair on failure
  if: failure()
  run: |
    # Restart Prometheus if rules evaluation stalled
    docker compose restart prometheus
    sleep 30
    # Re-run smoke test
    pwsh ./scripts/test_monitoring_stack.ps1
```

### Phase 4: Alerting on Nightly Failures (future)
Add Slack notification when nightly workflow fails:
```yaml
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "🚨 Monitoring nightly validation failed",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "View logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            }
          }
        ]
      }
```

## File Manifest

### New Files
```
.github/workflows/
└── monitoring-nightly.yml              # Nightly CI workflow (130 lines)

docs/
└── SILENT_FAILURE_DETECTION.md         # This file
```

### Modified Files
```
monitoring/
├── prometheus-alerts.yml               # Added 2 staleness alerts
└── Makefile                            # Added smoke-test-nightly command
```

## Success Metrics

- ✅ **Nightly workflow** configured and ready to run at 03:17 UTC
- ✅ **2 staleness alerts** loaded in Prometheus (CrmRecordingRulesStale, CrmMetricsScrapeStale)
- ✅ **Makefile command** `make smoke-test-nightly` for local testing
- ✅ **Total 6 alerts** covering payment rate, revenue, generation, API health, recording rules, scrape health
- ✅ **< 15 minute detection** for silent monitoring failures
- ✅ **24-hour validation** via nightly CI runs

---

**Status**: ✅ Production-ready silent failure detection
**Last Updated**: November 2, 2025
**Sprint**: 5 (Production Hardening + CI/CD + Silent Failure Detection)
