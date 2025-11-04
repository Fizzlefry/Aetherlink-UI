# Autoheal Production Deployment Guide

**Status**: Ready for Canary Deployment  
**Version**: 1.0.0  
**Date**: 2025-11-02

---

## 🎯 Deployment Strategy

### Phase 1: Canary (24-48 hours)
- Deploy with `AUTOHEAL_DRY_RUN=true`
- Monitor all metrics and alerts
- Review audit trail for false positives
- Validate SLO compliance

### Phase 2: Production (After canary success)
- Flip `AUTOHEAL_DRY_RUN=false`
- Enable full auto-remediation
- Continue monitoring for 72 hours

---

## 📋 Pre-Deployment Checklist

### Infrastructure
- [ ] Docker Compose 2.x installed
- [ ] Prometheus 2.x+ running
- [ ] Grafana 9.x+ running
- [ ] Alertmanager 0.25+ running
- [ ] Minimum 2GB RAM available
- [ ] Minimum 20GB disk space for audit logs

### Configuration
- [ ] `docker-compose.prod.yml` reviewed
- [ ] Environment variables set
- [ ] OIDC configuration completed (if enabled)
- [ ] Backup directory created: `/backups/autoheal`
- [ ] Logrotate configured

### Security
- [ ] OIDC enabled for `/audit` and `/console` endpoints
- [ ] CORS origins whitelisted
- [ ] Rate limiting configured
- [ ] Secrets externalized (no plaintext in env files)

### Monitoring
- [ ] Prometheus alerts loaded
- [ ] Grafana dashboard imported
- [ ] Alertmanager routing tested
- [ ] Backup cron job configured

---

## 🚀 Deployment Commands

### 1. Canary Deployment (DRY-RUN Mode)

```bash
cd monitoring

# Pull latest code
git pull origin main

# Backup current state
./scripts/backup/prometheus-snapshot.sh

# Start with production overrides (canary mode)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal prometheus grafana alertmanager

# Verify health
sleep 10
curl -f http://localhost:9009/ || exit 1
curl -f http://localhost:9090/-/healthy || exit 1

# Check Prometheus targets
curl 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[] | select(.labels.job=="autoheal")'

# Verify metrics are flowing
curl http://localhost:9009/metrics | grep autoheal_enabled

# Generate test event
curl -X POST http://localhost:9009/alert \
  -H 'Content-Type: application/json' \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {"alertname": "TestAlert", "service": "test"},
      "annotations": {"autoheal_action": "echo test"}
    }]
  }'

# Check audit trail
curl 'http://localhost:9009/audit?n=10' | jq '.events[] | {ts, kind, alertname}'
```

### 2. Verify Canary Health (24-hour checkpoint)

```bash
# Check for firing alerts
curl 'http://localhost:9090/api/v1/query?query=ALERTS{alertname=~"Autoheal.*",alertstate="firing"}' | jq '.data.result'

# Verify audit write latency SLO
curl 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(autoheal_audit_write_seconds_bucket[10m]))' | jq '.data.result[0].value[1]'

# Check heartbeat age
curl 'http://localhost:9090/api/v1/query?query=autoheal:heartbeat:age_seconds' | jq '.data.result[0].value[1]'

# Review audit trail for unexpected events
./scripts/autoheal-audit.ps1

# Check action dry-run events (should see actions being evaluated)
curl 'http://localhost:9009/audit?kind=action_dry_run&n=50' | jq '.count'
```

### 3. Production Rollout (After successful canary)

```bash
cd monitoring

# Backup audit trail before production switch
./scripts/backup/backup-autoheal.sh

# Update environment variable (option 1: docker-compose.prod.yml)
# Edit docker-compose.prod.yml and set:
#   AUTOHEAL_DRY_RUN: "false"

# Recreate autoheal container
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# Verify production mode
curl http://localhost:9009/ | jq '.dry_run'  # Should return false

# Monitor closely for first hour
watch -n 30 'curl -s "http://localhost:9009/audit?n=10" | jq ".events[] | {ts, kind, alertname, result}"'
```

---

## 📊 Monitoring & Validation

### Key Metrics to Watch

#### SLO-1: Heartbeat Age (Target: <5m)
```bash
curl 'http://localhost:9090/api/v1/query?query=autoheal:heartbeat:age_seconds'
```
**Acceptable**: <300s  
**Warning**: >300s for >10m  
**Critical**: >900s for >10m

#### SLO-2: Action Failure Rate (Target: <0.05/s)
```bash
curl 'http://localhost:9090/api/v1/query?query=autoheal:action_fail_rate_15m'
```
**Acceptable**: <0.05/s  
**Warning**: >0.05/s for >15m  
**Critical**: >0.2/s for >10m

#### SLO-3: Service Availability (Target: >99.9%)
```bash
curl 'http://localhost:9090/api/v1/query?query=up{job="autoheal"}'
```
**Acceptable**: 1 (up)  
**Critical**: 0 (down) for >2m

#### SLO-4: Audit Write Latency (Target: p95 <200ms)
```bash
curl 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(autoheal_audit_write_seconds_bucket[10m]))'
```
**Acceptable**: <0.2s  
**Warning**: >0.2s for >10m

### Prometheus Alerts to Monitor

```bash
# Check for firing autoheal alerts
curl 'http://localhost:9090/api/v1/rules' | jq '.data.groups[] | select(.name | contains("autoheal")) | .rules[] | select(.state=="firing")'
```

Expected alerts during canary: **None**  
Expected alerts during production: **None** (unless actual issues occur)

### Audit Trail Validation

```bash
# Count events by kind
curl 'http://localhost:9009/audit?n=1000' | jq '.events | group_by(.kind) | map({kind: .[0].kind, count: length})'

# Expected distribution (canary):
# - webhook_received: High (all alerts)
# - decision_skip: Some (cooldowns, not_annotated)
# - action_dry_run: High (all would-be actions)
# - action_ok: 0 (dry-run mode)
# - action_fail: 0 (dry-run mode)

# Expected distribution (production):
# - webhook_received: High
# - decision_skip: Some
# - action_dry_run: 0 (production mode)
# - action_ok: Most actions
# - action_fail: <5% of actions
```

---

## 🔧 Configuration Reference

### Environment Variables (Production)

```yaml
# docker-compose.prod.yml
environment:
  # Core configuration
  AUTOHEAL_ENABLED: "true"                      # Enable auto-remediation
  AUTOHEAL_DRY_RUN: "false"                     # PRODUCTION: Set to false after canary
  AUTOHEAL_AUDIT_PATH: "/data/audit.jsonl"      # Persistent audit trail
  
  # Timeouts & cooldowns
  AUTOHEAL_DEFAULT_COOLDOWN_SEC: "600"          # 10 minutes default
  COOLDOWN_TCP_DOWN_SEC: "300"                  # 5 minutes for TCP issues
  COOLDOWN_UPTIME_FAIL_SEC: "600"               # 10 minutes for uptime probes
  COOLDOWN_SCRAPE_STALE_SEC: "900"              # 15 minutes for scrape issues
  
  # URLs
  ALERTMANAGER_URL: "http://alertmanager:9093"
  AUTOHEAL_PUBLIC_URL: "https://autoheal.aetherlink.io"
  
  # Security (optional, enable for production)
  AUTOHEAL_OIDC_ENABLED: "true"
  OIDC_ISSUER: "https://auth.aetherlink.io"
  OIDC_AUDIENCE: "autoheal-api"
  
  # CORS
  AUTOHEAL_CORS_ENABLED: "true"
  AUTOHEAL_CORS_ORIGINS: "https://command.aetherlink.io"
  
  # Rate limiting
  AUTOHEAL_RATE_LIMIT_ENABLED: "true"
  AUTOHEAL_RATE_LIMIT_REQUESTS: "100"           # 100 requests per window
  AUTOHEAL_RATE_LIMIT_WINDOW: "60"              # 60 seconds window
```

### Resource Limits (Production)

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'          # 1 CPU core max
      memory: 512M         # 512MB RAM max
    reservations:
      cpus: '0.5'          # 0.5 CPU core guaranteed
      memory: 256M         # 256MB RAM guaranteed
```

---

## 🛡️ Security Hardening

### OIDC Authentication

Protected endpoints:
- `/audit` - Requires `ops` or `admin` role
- `/console` - Requires `ops` or `admin` role
- `/ack` - Requires `ops` or `admin` role

Public endpoints:
- `/` - Health check (unauthenticated)
- `/metrics` - Prometheus metrics (unauthenticated)
- `/events` - SSE stream (token-based access)

### Secrets Management

**Do NOT store secrets in environment files!**

Use Docker secrets or Vault:

```bash
# Create Docker secret
echo "your-slack-webhook-url" | docker secret create slack_webhook_url -

# Reference in docker-compose:
secrets:
  - slack_webhook_url
environment:
  SLACK_WEBHOOK_URL_FILE: /run/secrets/slack_webhook_url
```

---

## 🔄 Backup & Disaster Recovery

### Automated Backups

```bash
# Linux/macOS cron (daily at 2 AM)
0 2 * * * /path/to/monitoring/scripts/backup/backup-autoheal.sh

# Windows Task Scheduler
schtasks /create /tn "Autoheal Backup" /tr "powershell.exe -File C:\path\to\backup-autoheal.ps1" /sc daily /st 02:00
```

### Manual Backup (Before major changes)

```bash
# Backup audit trail
./scripts/backup/backup-autoheal.ps1

# Backup Prometheus data
./scripts/backup/prometheus-snapshot.sh

# Tag release in Git
git tag -a ops-v1.0.0 -m "Production deployment - Autoheal v1.0.0"
git push origin ops-v1.0.0
```

### Disaster Recovery

```bash
# Restore audit trail from backup
cp /backups/autoheal/audit_20251102_020000.jsonl.gz /data/autoheal/
gunzip /data/autoheal/audit_20251102_020000.jsonl.gz
mv /data/autoheal/audit_20251102_020000.jsonl /data/autoheal/audit.jsonl

# Restore Prometheus snapshot
tar -xzf /backups/prometheus/snapshot_20251102_020000.tar.gz -C /tmp
docker cp /tmp/snapshot_20251102_020000 aether-prometheus:/prometheus/snapshots/
# Restart Prometheus with --storage.tsdb.snapshot flag
```

---

## 🚨 Rollback Procedure

### If canary fails SLO checks:

```bash
# 1. Disable autoheal immediately
docker compose stop autoheal

# 2. Check audit trail for root cause
./scripts/autoheal-audit.ps1

# 3. Review Prometheus alerts
curl 'http://localhost:9090/api/v1/rules' | jq '.data.groups[] | select(.name | contains("autoheal"))'

# 4. Fix issue and redeploy canary
```

### If production encounters issues:

```bash
# EMERGENCY: Flip back to dry-run mode
docker exec aether-autoheal sh -c 'export AUTOHEAL_DRY_RUN=true && kill -HUP 1'

# Or restart with dry-run
# Edit docker-compose.prod.yml: AUTOHEAL_DRY_RUN: "true"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# Verify dry-run mode active
curl http://localhost:9009/ | jq '.dry_run'  # Should return true
```

---

## 📞 Support & Escalation

### Runbooks
- Heartbeat SLO breach: `https://docs.aetherlink.io/runbooks/autoheal-heartbeat`
- Failure rate SLO breach: `https://docs.aetherlink.io/runbooks/autoheal-failures`
- Service down: `https://docs.aetherlink.io/runbooks/autoheal-down`
- Audit latency: `https://docs.aetherlink.io/runbooks/autoheal-audit-latency`

### Monitoring Dashboards
- Grafana: `http://localhost:3000/d/autoheal`
- SSE Console: `http://localhost:9009/console`
- Command Center: `http://localhost:8080/ops/autoheal`

### Logs
```bash
# Autoheal logs
docker logs aether-autoheal --tail 100 --follow

# Audit trail
tail -f /data/autoheal/audit.jsonl | jq '.'

# Prometheus logs
docker logs aether-prometheus --tail 50
```

---

## ✅ Post-Deployment Validation

### 24 Hours After Production Rollout

- [ ] All 4 SLOs green
- [ ] No autoheal alerts firing
- [ ] Audit trail shows successful actions
- [ ] No unexpected action failures
- [ ] Backup job ran successfully
- [ ] Logrotate working correctly
- [ ] Disk usage under control

### 7 Days After Production Rollout

- [ ] Review weekly audit report
- [ ] Analyze action success rates
- [ ] Review cooldown effectiveness
- [ ] Check for automation gaps
- [ ] Update runbooks based on incidents
- [ ] Schedule retrospective

---

## 📈 Success Metrics

**Target Metrics (First 30 Days)**:
- Service availability: >99.9%
- Action success rate: >95%
- Audit write latency p95: <200ms
- Heartbeat age p95: <5m
- False positive rate: <5%
- Mean time to remediation: <2m

---

**Deployment Owner**: Aetherlink Platform Team  
**Approval Required**: Ops Lead + Engineering Manager  
**Rollback Authority**: Ops Lead (immediate), On-call Engineer (emergency)
