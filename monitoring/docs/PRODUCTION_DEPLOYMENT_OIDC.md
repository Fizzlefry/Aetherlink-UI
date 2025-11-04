# Production Deployment Guide - Autoheal with OIDC

## Overview

This guide covers deploying the production-hardened Autoheal service with:
- ✅ OIDC/JWT authentication for `/audit`, `/console`, and `/ack` endpoints
- ✅ Production resource limits and restart policies
- ✅ Automated audit trail rotation (14-day retention)
- ✅ Next.js Command Center ops dashboard
- ✅ Canary and production deployment modes

---

## Prerequisites

### 1. OIDC Provider Configuration

You need an OIDC-compliant identity provider (Auth0, Okta, Azure AD, Keycloak, etc.) configured with:

```bash
# Required OIDC endpoints:
https://YOUR_DOMAIN/.well-known/openid-configuration
https://YOUR_DOMAIN/.well-known/jwks.json
```

### 2. Environment Variables

Create or update your `.env` file:

```bash
# OIDC Configuration (Required for production)
OIDC_ENABLED=true
OIDC_ISSUER=https://YOUR_DOMAIN/.well-known/openid-configuration
OIDC_AUDIENCE=peakpro-api
# Optional: Override JWKS URI if not discoverable
OIDC_JWKS_URI=https://YOUR_DOMAIN/.well-known/jwks.json

# Autoheal Configuration
AUTOHEAL_ENABLED=true
AUTOHEAL_DRY_RUN=true  # Start in canary mode, flip to false for production
AUTOHEAL_PUBLIC_URL=https://autoheal.yourdomain.com
```

**PowerShell Example:**
```powershell
$env:OIDC_ENABLED="true"
$env:OIDC_ISSUER="https://YOUR_DOMAIN/.well-known/openid-configuration"
$env:OIDC_AUDIENCE="peakpro-api"
```

---

## Deployment Phases

### Phase 1: Canary Deployment (DRY_RUN=true)

**Objective:** Validate production configuration with no actual remediation actions.

```powershell
# 1. Set environment variables
$env:OIDC_ENABLED="true"
$env:OIDC_ISSUER="https://YOUR_DOMAIN/.well-known/openid-configuration"
$env:OIDC_AUDIENCE="peakpro-api"
$env:AUTOHEAL_DRY_RUN="true"  # Canary mode

# 2. Rebuild autoheal container with OIDC auth
cd monitoring
docker compose build autoheal

# 3. Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Validation:**
```powershell
# Health check (public endpoint, no auth required)
Invoke-RestMethod 'http://localhost:9009/'

# Protected endpoints require Bearer token
$Headers = @{ Authorization = "Bearer YOUR_JWT_TOKEN" }

# Test OIDC protection
Invoke-RestMethod 'http://localhost:9009/audit?n=10' -Headers $Headers
Invoke-WebRequest 'http://localhost:9009/console' -Headers $Headers -UseBasicParsing

# Verify dry-run mode
$health = Invoke-RestMethod 'http://localhost:9009/'
if ($health.dry_run -ne $true) {
    Write-Error "Expected dry_run=true (canary mode)"
}
```

**Expected Behavior:**
- ✅ All services start successfully
- ✅ `/audit` and `/console` return 401 without valid token
- ✅ `/audit` and `/console` return 200 with valid token
- ✅ Events logged with `kind=action_dry_run`
- ✅ No `action_ok` or `action_fail` events (dry-run mode)

**Canary Duration:** 24-48 hours minimum

---

### Phase 2: Production Rollout (DRY_RUN=false)

**Objective:** Enable full auto-remediation with authentication protection.

```powershell
# 1. Backup audit trail before production switch
.\monitoring\scripts\backup\backup-autoheal.ps1

# 2. Update environment variable
$env:AUTOHEAL_DRY_RUN="false"  # Production mode

# 3. Recreate autoheal container
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# 4. Verify production mode
$health = Invoke-RestMethod 'http://localhost:9009/'
if ($health.dry_run -ne $false) {
    Write-Error "Expected dry_run=false (production mode)"
}
```

**Post-Deployment Monitoring (72 hours):**
```powershell
# Monitor action success/failure rates
watch -n 30 'curl -s "http://localhost:9009/audit?n=50" | jq ".events[] | {ts, kind, alertname, result}" | head -20'

# Check action success rate (target: >95%)
$Headers = @{ Authorization = "Bearer YOUR_JWT_TOKEN" }
$audit = Invoke-RestMethod 'http://localhost:9009/audit?n=1000' -Headers $Headers
$actions = $audit.events | Where-Object { $_.kind -match "action_(ok|fail)" }
$successRate = ($actions | Where-Object { $_.kind -eq "action_ok" }).Count / $actions.Count * 100
Write-Host "Action success rate: $successRate%"
```

---

## Production Configuration Reference

### docker-compose.prod.yml

```yaml
services:
  autoheal:
    environment:
      - AUTOHEAL_ENABLED=true
      - AUTOHEAL_DRY_RUN=false              # Canary: true, Production: false
      - OIDC_ENABLED=${OIDC_ENABLED:-false}
      - OIDC_ISSUER=${OIDC_ISSUER}
      - OIDC_AUDIENCE=${OIDC_AUDIENCE}
    restart: unless-stopped
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 512M }

  autoheal-logrotate:
    image: alpine:3.20
    command: ["/bin/sh","-c","crond -f -l 8"]
    volumes:
      - ./monitoring/data/autoheal:/data
      - ./monitoring/logrotate/audit.conf:/etc/logrotate.d/audit.conf:ro
      - ./monitoring/logrotate/crontab:/etc/crontabs/root:ro
    restart: unless-stopped
```

### Audit Trail Rotation

**Configuration:** `monitoring/logrotate/audit.conf`
- Daily rotation at 02:10 AM
- 14-day retention
- Gzip compression
- Copytruncate (safe for append-only logging)

**Manual Rotation:**
```bash
docker exec autoheal-logrotate logrotate -f /etc/logrotate.d/audit.conf
```

---

## Security Features

### Protected Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/` | GET | ❌ No | Health check |
| `/metrics` | GET | ❌ No | Prometheus metrics |
| `/events` | GET | ❌ No | SSE event stream (for proxies) |
| `/audit` | GET | ✅ Yes | Filtered audit trail |
| `/console` | GET | ✅ Yes | Web console (static files) |
| `/ack` | GET | ✅ Yes | Create Alertmanager silence |
| `/alert` | POST | ❌ No | Alertmanager webhook |

### Token Validation

The OIDC middleware validates:
1. **Token Presence:** Bearer token in `Authorization` header
2. **Signature:** RSA signature verification with JWKS public key
3. **Expiration:** `exp` claim must be in the future
4. **Audience:** `aud` claim must match `OIDC_AUDIENCE`
5. **Issuer:** `iss` claim must match `OIDC_ISSUER`

### Obtaining Tokens

**Option 1: OAuth2 Client Credentials Flow (M2M)**
```bash
curl -X POST https://YOUR_DOMAIN/oauth/token \
  -H 'Content-Type: application/json' \
  -d '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "audience": "peakpro-api",
    "grant_type": "client_credentials"
  }'
```

**Option 2: User Authentication Flow**
Use your OIDC provider's authentication flow to obtain user JWT tokens.

---

## Command Center Integration

### Next.js Ops Dashboard

**File:** `apps/command-center/app/ops/autoheal/page.tsx`

**Features:**
- 🔴 Live event stream via SSE
- 🔍 Filterable audit trail with Boolean queries
- 📊 Quick links to Grafana dashboard, audit JSON, health check
- 🎨 Dark theme matching VS Code

**Filter Syntax:**
```
kind=action_fail OR alertname=HighCPU
kind=action_ok AND alertname=TcpEndpointDownFast
```

**API Proxy Endpoints (to implement in PeakPro API):**
```typescript
// apps/command-center/app/api/ops/autoheal/route.ts
export async function GET(req: Request) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/ops/autoheal', '');

  // Get token from session/auth
  const token = await getServerToken();

  // Proxy to Autoheal with authentication
  const response = await fetch(`http://autoheal:9009${path}${url.search}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers
  });
}
```

---

## Monitoring & Alerts

### Key Metrics

```promql
# Autoheal enabled status
autoheal_enabled

# Action success/failure counters
autoheal_actions_total{alertname="TcpEndpointDownFast", result="executed"}
autoheal_actions_total{alertname="TcpEndpointDownFast", result="failed"}

# Cooldown remaining
autoheal_cooldown_remaining_seconds{alertname="TcpEndpointDownFast"}

# Event counters by kind
autoheal_event_total{kind="action_ok"}
autoheal_event_total{kind="action_fail"}
autoheal_event_total{kind="action_dry_run"}

# Audit write latency (SLO-4)
histogram_quantile(0.95, rate(autoheal_audit_write_seconds_bucket[10m]))
```

### Alert Rules

See `monitoring/prometheus-alerts.yml` for complete alert definitions:
- `AutohealServiceDown` (critical)
- `AutohealHeartbeatSLOBreach` (critical)
- `AutohealFailureRateSLOBreach` (critical)
- `AutohealAuditWriteLatencySLOBreach` (warning)

---

## Troubleshooting

### Issue: "Missing bearer token" on /audit

**Cause:** OIDC protection is enabled but no token provided.

**Solution:**
```powershell
# Option 1: Obtain valid token from OIDC provider
$token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
$Headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod 'http://localhost:9009/audit' -Headers $Headers

# Option 2: Disable OIDC for testing (NOT recommended for production)
$env:OIDC_ENABLED="false"
docker compose up -d autoheal
```

### Issue: "Invalid signature" or "Token expired"

**Cause:** Token is invalid, expired, or wrong audience/issuer.

**Solution:**
1. Verify `OIDC_ISSUER` and `OIDC_AUDIENCE` match token claims
2. Check token expiration: `jwt.io` to decode and inspect
3. Ensure JWKS is accessible from container:
   ```bash
   docker exec autoheal curl -s $OIDC_JWKS_URI
   ```

### Issue: "OIDC discovery failed"

**Cause:** Cannot reach OIDC provider's `.well-known/openid-configuration` endpoint.

**Solution:**
1. Test from host:
   ```powershell
   Invoke-RestMethod $env:OIDC_ISSUER
   ```
2. Test from container:
   ```bash
   docker exec autoheal curl -s $OIDC_ISSUER
   ```
3. Check network connectivity, DNS resolution, firewall rules

### Issue: Logrotate not rotating audit files

**Cause:** Cron not running or misconfigured.

**Solution:**
```bash
# Check cron logs
docker logs autoheal-logrotate

# Manually trigger rotation (force)
docker exec autoheal-logrotate logrotate -f /etc/logrotate.d/audit.conf

# Verify rotation status
docker exec autoheal-logrotate cat /tmp/logrotate.status
```

---

## Rollback Procedures

### Emergency Rollback (disable autoheal)

```powershell
# 1. Disable autoheal immediately
docker compose stop autoheal

# 2. Verify no actions are executed
curl http://localhost:9009/
# (should fail or show offline)

# 3. Check recent audit trail for issues
Get-Content .\monitoring\data\autoheal\audit.jsonl | Select-Object -Last 50
```

### Rollback to Canary Mode

```powershell
# 1. Switch back to dry-run
$env:AUTOHEAL_DRY_RUN="true"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# 2. Verify dry-run mode active
$health = Invoke-RestMethod 'http://localhost:9009/'
Write-Host "Dry-run: $($health.dry_run)"  # Should be true
```

### Rollback to Previous Version

```powershell
# 1. Stop services
docker compose down autoheal

# 2. Checkout previous commit
git log --oneline monitoring/autoheal/
git checkout <previous-commit> monitoring/autoheal/

# 3. Rebuild and restart
docker compose build autoheal
docker compose up -d autoheal
```

---

## Success Metrics (30-Day Target)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | >99.9% | `up{job="autoheal"}` |
| Action Success Rate | >95% | `action_ok / (action_ok + action_fail)` |
| Heartbeat Age p95 | <5m | `autoheal:heartbeat:age_seconds` |
| Audit Write Latency p95 | <200ms | SLO-4 metric |
| Security: OIDC Enforced | 100% | Manual audit of protected endpoints |
| Audit Retention | 14 days | Check rotated files in `/data/` |

---

## Support & Escalation

### Documentation
- **Autoheal Integration:** `monitoring/docs/AUTOHEAL_INTEGRATION_SUMMARY.md`
- **SLO Framework:** `monitoring/docs/PRODUCTION_DEPLOYMENT_GUIDE.md`
- **Production Readiness:** `monitoring/docs/PRODUCTION_READINESS_SUMMARY.md`

### Runbooks
- All alerts include `runbook_url` annotations
- Example: `https://wiki.aetherlink.io/runbooks/autoheal-service-down`

### Contact
- **Ops Team:** #aetherlink-ops (Slack)
- **On-Call:** PagerDuty escalation policy
- **Escalation:** Director of Engineering

---

## Quick Reference Commands

```powershell
# Check production status
docker compose ps autoheal
Invoke-RestMethod 'http://localhost:9009/'

# View live events (requires OIDC token)
$Headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod 'http://localhost:9009/audit?n=50' -Headers $Headers

# Check Prometheus metrics
Invoke-RestMethod 'http://localhost:9009/metrics' | Select-String "autoheal"

# View audit trail (last 100 lines)
Get-Content .\monitoring\data\autoheal\audit.jsonl -Tail 100

# Backup audit trail
.\monitoring\scripts\backup\backup-autoheal.ps1

# View Grafana dashboard
Start-Process "http://localhost:3000/d/AETHERLINK_AUTOHEAL"

# Manual silence (requires OIDC token)
$params = @{
    labels = '{"alertname":"TcpEndpointDownFast"}'
    duration = '1h'
    comment = 'Manual maintenance window'
}
Invoke-RestMethod 'http://localhost:9009/ack' -Method Get -Headers $Headers -Body $params
```

---

**Deployment Approval:**
- [ ] OIDC provider configured and tested
- [ ] Environment variables set correctly
- [ ] Canary deployment validated (24-48h)
- [ ] Security audit passed (OIDC protection on all sensitive endpoints)
- [ ] Monitoring dashboards reviewed
- [ ] Runbooks updated
- [ ] Stakeholders notified
- [ ] Rollback plan confirmed

**Production Go-Live Date:** ________________

**Deployment Lead:** ________________

**Approval Signature:** ________________
