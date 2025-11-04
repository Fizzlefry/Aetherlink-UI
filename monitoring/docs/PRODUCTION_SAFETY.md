# Production Safety & Testing

## Overview
This document describes the production safety features, testing infrastructure, and operational guardrails for the AetherLink monitoring stack.

## CI/CD Policy Guards

### GitHub Actions Workflow
**File**: `.github/workflows/policy-guard.yml`

Prevents dangerous auto-remediation configurations from reaching production:

- ✅ **Blocks merges** with `AUTOHEAL_ENABLED=true` in docker-compose.yml
- ✅ **Validates** alertmanager.yml doesn't contain hardcoded external autoheal URLs
- ✅ **Runs on**: Pull requests and pushes to main branch

```bash
# Example: This would fail CI
environment:
  AUTOHEAL_ENABLED: "true"  # ❌ BLOCKED BY CI
```

## Unit Testing

### Prometheus Rules Tests
**File**: `monitoring/tests/rules.test.yml`

Tests alert rules and recording rules with promtool:

```bash
# Run tests (Windows)
docker run --rm --entrypoint promtool `
  -v ${PWD}:/workspace -w /workspace `
  prom/prometheus:v2.54.1 test rules tests/rules.test.yml

# Run tests (Linux/macOS)
docker run --rm --entrypoint promtool \
  -v $(pwd):/workspace -w /workspace \
  prom/prometheus:v2.54.1 test rules tests/rules.test.yml
```

**Current test coverage**:
- ✅ TCP endpoint alerts (TcpEndpointDownFast)
- ✅ Error budget alerts (PaymentRateErrorBudgetCritical)
- ✅ Recording rules (tcp:probe_success:ratio_5m)

### Alertmanager Config Validation
```bash
# Validate config (Windows)
docker run --rm --entrypoint amtool `
  -v ${PWD}:/conf `
  quay.io/prometheus/alertmanager:latest `
  check-config /conf/alertmanager.yml

# Validate config (Linux/macOS)
docker run --rm --entrypoint amtool \
  -v $(pwd):/conf \
  quay.io/prometheus/alertmanager:latest \
  check-config /conf/alertmanager.yml
```

**Validation results**:
- ✅ Global config
- ✅ Route configuration
- ✅ 3 inhibit rules
- ✅ 4 receivers
- ✅ 1 template file

## Auto-Remediation Safety

### Triple Safety Guarantees

**File**: `monitoring/autoheal/main.py`

The autoheal service has **three layers of safety**:

#### 1. Annotation Opt-In
Alerts MUST have `autoheal: "true"` annotation:

```yaml
# prometheus-alerts.yml
annotations:
  summary: "TCP down: {{ $labels.instance }}"
  autoheal: "true"  # ← Required for auto-remediation
```

#### 2. Action Allowlist
Only 3 alerts can trigger actions:
- `CrmMetricsScrapeStale`
- `TcpEndpointDownFast`
- `UptimeProbeFailing`

Any other alert will be skipped even with annotation.

#### 3. Rate Limiting
120-second cooldown between runs for same alert:

```python
COOLDOWN_SEC = 120  # Default: 2 minutes
```

### Docker Profile Isolation

**File**: `monitoring/docker-compose.yml`

```yaml
services:
  autoheal:
    profiles: ["dev"]  # Only starts with: docker compose --profile dev up
    environment:
      AUTOHEAL_ENABLED: "false"  # Disabled by default
      AUTOHEAL_COOLDOWN_SEC: "120"
```

**Production deployment**:
```bash
# Normal deploy - autoheal NOT started
docker compose up -d

# Dev deployment - autoheal started but disabled
docker compose --profile dev up -d
```

### Safety Status Endpoint

Check autoheal safety status:
```bash
# Windows
Invoke-RestMethod 'http://localhost:9009/'

# Linux/macOS
curl http://localhost:9009/
```

**Expected response**:
```json
{
  "service": "running",
  "status": "running",
  "enabled": false,
  "actions": [
    "CrmMetricsScrapeStale",
    "TcpEndpointDownFast",
    "UptimeProbeFailing"
  ],
  "cooldown_sec": 120,
  "timestamp": "2025-11-03T01:15:42.168582"
}
```

## Chaos Engineering

### TCP Outage Simulation
```bash
# Stop crm-api for 60 seconds
docker compose stop crm-api
Start-Sleep -Seconds 60
docker compose start crm-api
```

**Expected behavior**:
- TcpEndpointDownFast fires after 2 minutes
- If autoheal enabled + annotation present → auto-restart
- Alert resolves after service recovers

### Metrics Scrape Failure
```bash
# Stop Prometheus for 45 seconds
docker compose stop prometheus
Start-Sleep -Seconds 45
docker compose start prometheus
```

**Expected behavior**:
- CrmMetricsScrapeStale fires after 3 minutes
- Autoheal can restart target service (not Prometheus itself)
- Alert resolves after scraping resumes

## Observability Verification

### End-to-End Smoke Test

```bash
# 1. Check Prometheus rules
docker run --rm --entrypoint promtool `
  -v ${PWD}:/workspace -w /workspace `
  prom/prometheus:v2.54.1 check rules `
  prometheus-recording-rules.yml prometheus-alerts.yml

# 2. Validate Alertmanager config
docker run --rm --entrypoint amtool `
  -v ${PWD}:/conf `
  quay.io/prometheus/alertmanager:latest `
  check-config /conf/alertmanager.yml

# 3. Check Prometheus targets
Invoke-RestMethod 'http://localhost:9090/api/v1/targets' | `
  Select-Object -ExpandProperty data | `
  Select-Object -ExpandProperty activeTargets | `
  Select-Object job, health | Format-Table

# 4. Check active alerts
$alerts = (Invoke-RestMethod 'http://localhost:9090/api/v1/alerts').data.alerts
Write-Host "Active alerts: $($alerts.Count)"

# 5. Check autoheal status
Invoke-RestMethod 'http://localhost:9009/'
```

**Expected results**:
- ✅ 25 recording rules found
- ✅ 34 alert rules found
- ✅ Alertmanager config valid
- ✅ 12/13 targets UP (uptime-external expected DOWN)
- ✅ Autoheal: running, disabled, 120s cooldown

## Metrics

### Test Coverage
- **Total alert rules**: 34
- **Tested alert rules**: 2 (TcpEndpointDownFast, PaymentRateErrorBudgetCritical)
- **Total recording rules**: 25
- **Tested recording rules**: 1 (tcp:probe_success:ratio_5m)
- **Test coverage**: ~9% (3/34 rules)

### Safety Metrics
- **Auto-remediation enabled**: False (default)
- **Allowed actions**: 3 alerts
- **Cooldown period**: 120 seconds
- **Annotation opt-in required**: Yes
- **CI guards active**: Yes

## Best Practices

### Adding New Auto-Remediation Actions

1. **Add to allowlist** in `autoheal/main.py`:
```python
ACTIONS = {
    "TcpEndpointDownFast": "docker compose restart crm-api",
    "MyNewAlert": "docker compose restart my-service",  # ← Add here
}
```

2. **Add annotation** to alert rule:
```yaml
annotations:
  summary: "My service is down"
  autoheal: "true"  # ← Enable auto-remediation
```

3. **Test in dev** profile:
```bash
# Start with autoheal enabled (dev mode)
docker compose --profile dev up -d
docker exec -it aether-autoheal sh -c "sed -i 's/AUTOHEAL_ENABLED=false/AUTOHEAL_ENABLED=true/' .env"
docker compose --profile dev restart autoheal

# Simulate failure
docker compose stop my-service

# Watch logs
docker logs aether-autoheal --tail 50 -f
```

4. **Verify in CI** - ensure policy guard passes

### Runbook Development

All alerts should reference runbooks:

```yaml
annotations:
  runbook_url: "docs/runbooks/ALERTS_CRM_FINANCE.md#tcp-endpoint-down"
```

**Runbook sections**:
- **Symptoms**: What operators see
- **Impact**: Business/user consequences
- **Investigation**: Diagnostic commands
- **Mitigation**: Fix steps
- **Prevention**: Long-term solutions

## Troubleshooting

### Problem: Tests failing locally

**Solution**: Ensure Docker Desktop is running:
```bash
docker ps  # Should show containers
```

### Problem: Autoheal not triggering

**Checklist**:
1. Is autoheal service running? `docker ps | grep autoheal`
2. Is AUTOHEAL_ENABLED=true? `Invoke-RestMethod http://localhost:9009/`
3. Does alert have `autoheal: "true"` annotation?
4. Is alertname in ACTIONS allowlist?
5. Has 120s cooldown passed since last run?

### Problem: CI blocking legitimate changes

**Solution**: Ensure docker-compose.yml has:
```yaml
environment:
  AUTOHEAL_ENABLED: "false"  # Must be false for main branch
```

## Related Documentation

- [Alert Runbooks](./runbooks/ALERTS_CRM_FINANCE.md)
- [SLO Documentation](./SLO_METRICS.md)
- [Monitoring Architecture](./ARCHITECTURE.md)
- [Makefile Commands](../Makefile)

---

**Last Updated**: 2025-11-03
**Maintained By**: DevOps Team
**Review Cadence**: Quarterly
