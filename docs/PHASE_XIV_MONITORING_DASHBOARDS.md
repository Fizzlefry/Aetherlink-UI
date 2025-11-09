# Phase XIV: Prometheus & Grafana Deployment
**Status:** In Progress
**Started:** 2025-11-07
**Prerequisites:** Phase XIII Complete (Environment-labeled metrics, Alert rules)

## 🎯 Objectives

Deploy production-grade monitoring infrastructure with:
1. Prometheus scraping Command Center metrics
2. Alert rules for vertical service health
3. Grafana dashboards for operator visibility
4. Alert routing to notification channels

## 📋 Implementation Checklist

### Milestone 1: Prometheus Configuration ✅
- [x] Add Command Center scrape target to `prometheus.yml`
- [x] Mount alert rules file (`monitoring/aetherlink-alerts.yaml`)
- [x] Configure scrape intervals and timeouts
- [x] Set retention period for metrics
- [x] Verify metrics endpoint is reachable
- [x] Test alert rule syntax with `promtool`

**Completed:** 2025-11-07
**Details:**
- Added `aetherlink-command-center` scrape job to [prometheus-config.yml](../monitoring/prometheus-config.yml:202-215)
- Mounted `aetherlink-alerts.yaml` in [docker-compose.yml](../monitoring/docker-compose.yml:14)
- Configured 15s scrape interval, 10s timeout for Command Center
- Metrics successfully scraped from `host.docker.internal:8010/metrics`
- Verified metrics in Prometheus: `aether_service_up`, `aether_platform_total_*`, etc.

### Milestone 2: Alert Rules Activation
- [ ] Load `aetherlink-alerts.yaml` into Prometheus
- [ ] Verify alert rules are parsed correctly
- [ ] Test alert firing with simulated outages
- [ ] Configure alert labels and annotations
- [ ] Set up alert grouping and inhibition rules

### Milestone 3: Grafana Dashboard
- [ ] Create "Vertical Fleet Health" dashboard
- [ ] Add panel: Service Up/Down by environment
- [ ] Add panel: Service Staleness indicators
- [ ] Add panel: Platform business metrics (contacts, deals, jobs, etc.)
- [ ] Add panel: Scrape errors and duration
- [ ] Add panel: Attribution metrics (top API keys)
- [ ] Configure auto-refresh intervals
- [ ] Export dashboard JSON for version control

### Milestone 4: Alertmanager Integration
- [ ] Configure Alertmanager receivers (Slack, PagerDuty, email)
- [ ] Set up routing rules by environment (dev → Slack, prod → PagerDuty)
- [ ] Configure alert grouping windows
- [ ] Set up inhibition rules (suppress lower-severity alerts)
- [ ] Test end-to-end alert delivery
- [ ] Document runbook links and escalation paths

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│ Command Center :8010                                 │
│  • Exposes /metrics with env labels                  │
│  • Aggregates vertical service stats                 │
│  • Emits platform business metrics                   │
└─────────────────┬────────────────────────────────────┘
                  │ HTTP GET /metrics (15s interval)
                  ↓
┌──────────────────────────────────────────────────────┐
│ Prometheus :9090                                     │
│  • Scrapes metrics from Command Center              │
│  • Evaluates alert rules (aetherlink-alerts.yaml)   │
│  • Stores time-series data (retention: 15d)         │
└─────────────────┬────────────────────────────────────┘
                  │ PromQL queries
                  ↓
┌──────────────────────────────────────────────────────┐
│ Grafana :3000                                        │
│  • Visualizes metrics in dashboards                  │
│  • Provides drill-down capabilities                  │
│  • Displays alert status                            │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ Alertmanager :9093                                   │
│  • Receives alerts from Prometheus                   │
│  • Routes to Slack/PagerDuty based on env           │
│  • Groups and deduplicates alerts                    │
└──────────────────────────────────────────────────────┘
```

## 📊 Key Metrics to Monitor

### Service Health Metrics
- `aether_service_up{service="...",env="..."}` - Service reachability (1=up, 0=down)
- `aether_service_stale{service="...",env="..."}` - Data freshness (1=stale, 0=fresh)
- `aether_verticals_scrape_errors_total{service="...",env="..."}` - Scrape failure count
- `aether_verticals_scrape_duration_seconds` - Scrape performance

### Platform Business Metrics
- `aether_platform_total_contacts{env="..."}` - Total contacts across all verticals
- `aether_platform_total_deals{env="..."}` - Total deals
- `aether_platform_total_jobs{env="..."}` - Total jobs
- `aether_platform_total_properties{env="..."}` - Total properties
- `aether_platform_total_policies{env="..."}` - Total policies
- `aether_platform_total_uploads{env="..."}` - Total media uploads

### Attribution Metrics
- `aether_attribution_writes_total{key="...",env="..."}` - Writes per API key

## 🚨 Alert Rules Summary

| Alert Name | Condition | Duration | Severity | Action |
|------------|-----------|----------|----------|--------|
| AetherlinkVerticalServiceDown | `aether_service_up == 0` | 5m | warning | Check service logs and container status |
| AetherlinkVerticalDataStale | `aether_service_stale == 1` | 10m | warning | Verify service is processing requests |
| AetherlinkVerticalScrapeErrors | `rate(errors[5m]) > 0` | 2m | warning | Check network connectivity |
| AetherlinkVerticalScrapeSlow | `avg_duration > 5s` | 5m | info | Investigate vertical performance |

## 📁 File Locations

- **Prometheus Config:** `monitoring/prometheus.yml`
- **Alert Rules:** `monitoring/aetherlink-alerts.yaml` ✅
- **Grafana Dashboard:** `monitoring/dashboards/vertical-fleet-health.json`
- **Alertmanager Config:** `monitoring/alertmanager.yml`
- **Docker Compose:** `docker-compose.monitoring.yml`

## 🔧 Configuration Snippets

### Prometheus Scrape Config
```yaml
scrape_configs:
  - job_name: 'aetherlink-command-center'
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets: ['command-center:8010']
```

### Alertmanager Routing (Example)
```yaml
route:
  receiver: 'slack-dev'
  routes:
    - match:
        env: prod
      receiver: 'pagerduty-oncall'
    - match:
        env: staging
      receiver: 'slack-staging'
```

## ✅ Success Criteria

1. **Prometheus scraping successfully** - Metrics visible in Prometheus UI at `:9090`
2. **Alerts firing correctly** - Test alerts appear in Prometheus alerts page
3. **Grafana dashboard functional** - All panels display data, auto-refresh works
4. **Alert delivery working** - Test alerts reach Slack/PagerDuty channels
5. **Environment separation working** - Dev/staging/prod metrics are distinguished

## 🔄 Rollback Plan

If issues arise during deployment:
1. Comment out new scrape targets in `prometheus.yml`
2. Disable alert rules by moving `aetherlink-alerts.yaml` out of rules directory
3. Revert to previous Prometheus/Grafana configuration
4. Document issues in this file under "Known Issues" section

## 📚 References

- [Prometheus Configuration Docs](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Grafana Provisioning Docs](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- Phase XIII Documentation: `docs/PHASE_XIII_OBSERVABILITY_MEDIA.md`

## 🐛 Known Issues

None yet - this phase just started!

## 📝 Notes

- Command Center must be running and accessible at `command-center:8010` for scraping
- All vertical services should be healthy for accurate dashboard display
- Consider setting up separate Prometheus instances per environment in production
- Alert fatigue mitigation: start with warning-level alerts, tune thresholds based on real data
