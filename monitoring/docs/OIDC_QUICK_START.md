# Autoheal OIDC Production Deployment - Quick Start

## ⚡ TL;DR - Production Rollout

### 1. Set OIDC Environment Variables

```powershell
# PowerShell
$env:OIDC_ENABLED="true"
$env:OIDC_ISSUER="https://YOUR_DOMAIN/.well-known/openid-configuration"
$env:OIDC_AUDIENCE="peakpro-api"
$env:AUTOHEAL_DRY_RUN="true"  # Canary first!
```

### 2. Deploy Canary

```powershell
cd monitoring
docker compose build autoheal
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 3. Verify OIDC Protection

```powershell
# Should fail (401 Unauthorized)
Invoke-RestMethod 'http://localhost:9009/audit'

# Should succeed with valid token
$Headers = @{ Authorization = "Bearer YOUR_JWT_TOKEN" }
Invoke-RestMethod 'http://localhost:9009/audit?n=10' -Headers $Headers
```

### 4. Monitor Canary (24-48 hours)

```powershell
# Check health
Invoke-RestMethod 'http://localhost:9009/'

# View events (requires token)
Invoke-RestMethod 'http://localhost:9009/audit?n=100' -Headers $Headers
```

### 5. Flip to Production

```powershell
# Switch to production mode
$env:AUTOHEAL_DRY_RUN="false"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# Verify production mode
(Invoke-RestMethod 'http://localhost:9009/').dry_run  # Should be false
```

---

## 📋 What's Included

### Files Created

| File | Purpose |
|------|---------|
| `monitoring/autoheal/auth.py` | OIDC/JWT verification with JWKS discovery |
| `monitoring/autoheal/main.py` | Updated with OIDC middleware |
| `docker-compose.prod.yml` | Production overrides with resource limits |
| `monitoring/logrotate/crontab` | Daily audit rotation at 02:10 AM |
| `apps/command-center/app/ops/autoheal/page.tsx` | Next.js live ops dashboard |

### Protected Endpoints

- ✅ `/audit` - Filterable audit trail (OIDC required)
- ✅ `/console` - Web console (OIDC required)
- ✅ `/ack` - Create Alertmanager silence (OIDC required)
- 🌐 `/` - Health check (public)
- 🌐 `/metrics` - Prometheus metrics (public)
- 🌐 `/events` - SSE stream (public, for proxies)

### Features

- 🔒 **JWT Verification:** RSA signature, exp/aud/iss validation
- 🔄 **JWKS Discovery:** Automatic key rotation support
- 📊 **Resource Limits:** 1 CPU, 512MB RAM for autoheal
- 🗄️ **Audit Rotation:** 14-day retention, daily rotation
- 🚦 **Canary Mode:** Safe dry-run validation
- 🎨 **Ops Dashboard:** Live SSE, filterable events, Grafana embed

---

## 🔐 OIDC Token Examples

### Option 1: Client Credentials (M2M)

```bash
# Get token from Auth0/Okta/Azure AD
curl -X POST https://YOUR_DOMAIN/oauth/token \
  -H 'Content-Type: application/json' \
  -d '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "audience": "peakpro-api",
    "grant_type": "client_credentials"
  }'
```

### Option 2: Test with Mock Token (DEV ONLY)

```powershell
# Disable OIDC for local testing
$env:OIDC_ENABLED="false"
docker compose up -d autoheal

# Access endpoints without token
Invoke-RestMethod 'http://localhost:9009/audit?n=10'
```

---

## 🎯 Production Checklist

- [ ] OIDC provider configured (Auth0/Okta/Azure AD/Keycloak)
- [ ] Environment variables set (`OIDC_ISSUER`, `OIDC_AUDIENCE`)
- [ ] Canary deployment validated (DRY_RUN=true) for 24-48h
- [ ] Security audit: Protected endpoints return 401 without token
- [ ] Security audit: Protected endpoints return 200 with valid token
- [ ] Monitoring: SLO alerts configured and tested
- [ ] Backup: Audit trail backed up before production
- [ ] Documentation: Runbooks updated
- [ ] Stakeholders: Ops team notified
- [ ] Rollback: Plan confirmed and tested

---

## 🚨 Troubleshooting

### "Missing bearer token"

```powershell
# Get valid token from OIDC provider
$token = Invoke-RestMethod "https://YOUR_DOMAIN/oauth/token" -Method POST -Body @{
    client_id = "YOUR_CLIENT_ID"
    client_secret = "YOUR_CLIENT_SECRET"
    audience = "peakpro-api"
    grant_type = "client_credentials"
} | Select-Object -ExpandProperty access_token

# Use token in requests
$Headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod 'http://localhost:9009/audit' -Headers $Headers
```

### "Invalid signature" / "Token expired"

```powershell
# Check token claims at jwt.io
Write-Host "Token: $token"

# Verify OIDC configuration
Invoke-RestMethod $env:OIDC_ISSUER
Invoke-RestMethod $env:OIDC_JWKS_URI
```

### "OIDC discovery failed"

```bash
# Test from container
docker exec autoheal curl -s $OIDC_ISSUER
docker exec autoheal curl -s $OIDC_JWKS_URI

# Check network/DNS
docker exec autoheal nslookup YOUR_DOMAIN
```

---

## 📊 Monitoring Queries

```promql
# Action success rate (target: >95%)
sum(rate(autoheal_actions_total{result="executed"}[1h])) 
/ 
sum(rate(autoheal_actions_total[1h]))

# Audit write latency p95 (target: <200ms)
histogram_quantile(0.95, rate(autoheal_audit_write_seconds_bucket[10m]))

# Service availability (target: >99.9%)
avg_over_time(up{job="autoheal"}[30d])
```

---

## 🔗 Quick Links

- **Full Deployment Guide:** `monitoring/docs/PRODUCTION_DEPLOYMENT_OIDC.md`
- **Production Readiness:** `monitoring/docs/PRODUCTION_READINESS_SUMMARY.md`
- **Autoheal Integration:** `monitoring/docs/AUTOHEAL_INTEGRATION_SUMMARY.md`
- **Grafana Dashboard:** http://localhost:3000/d/AETHERLINK_AUTOHEAL
- **Prometheus Alerts:** http://localhost:9090/alerts
- **SSE Console:** http://localhost:9009/console (requires OIDC token)

---

## 🎓 Command Reference

```powershell
# Health check (no auth)
Invoke-RestMethod 'http://localhost:9009/'

# Audit trail (requires OIDC token)
$Headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod 'http://localhost:9009/audit?n=50' -Headers $Headers

# Filter audit events
Invoke-RestMethod 'http://localhost:9009/audit?kind=action_fail&n=20' -Headers $Headers

# Prometheus metrics (no auth)
Invoke-RestMethod 'http://localhost:9009/metrics' | Select-String "autoheal"

# View logs
docker logs autoheal --tail 50 -f

# Manual audit rotation
docker exec autoheal-logrotate logrotate -f /etc/logrotate.d/audit.conf

# Backup audit trail
.\monitoring\scripts\backup\backup-autoheal.ps1

# Production rollout
$env:AUTOHEAL_DRY_RUN="false"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d autoheal

# Emergency stop
docker compose stop autoheal
```

---

**Status:** ✅ READY FOR CANARY DEPLOYMENT

**Next Step:** Set OIDC environment variables and run canary deployment
