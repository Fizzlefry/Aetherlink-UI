# 🎯 One-Command Deployment Summary

## 🚀 Deploy Hardened Monitoring Stack

### Quick Deploy (5 minutes)

```powershell
# 1. Setup DNS (run as Administrator)
.\setup-hosts.ps1

# 2. Deploy Nginx reverse proxy
.\deploy-nginx-proxy.ps1 -Password "YourSecurePassword123"

# 3. Restart Alertmanager (pick up new external URLs)
docker compose restart alertmanager

# 4. Test everything
.\test-proxy.ps1 -Password "YourSecurePassword123"

# 5. Full end-to-end test (optional - 15 minutes)
.\flight-readiness-test.ps1 -Password "YourSecurePassword123"
```

---

## 📦 What You Get

### Security
- ✅ Alertmanager silence endpoint behind basic auth
- ✅ Tighter silence filters (service + team)
- ✅ External URLs (buttons work from anywhere)
- ✅ VPN/LAN-only access (firewall-ready)

### Slack Buttons
- `[📊 View Dashboard]` → `http://grafana.aetherlink.local/d/crm-events-pipeline`
- `[🔍 Prometheus Alerts]` → `http://alertmanager.aetherlink.local/#/alerts`
- `[🔕 Silence 1h]` → Pre-filled with service + team (auth required)

### Files Shipped
```
monitoring/
├── nginx/nginx.conf                    # Grafana open, AM behind auth
├── docker-compose.nginx.yml            # Nginx compose
├── docker-compose.traefik.yml          # Traefik (TLS)
├── docker-compose.caddy.yml            # Caddy (simplest TLS)
├── Caddyfile                           # Caddy config
├── setup-hosts.ps1                     # DNS setup (one command)
├── deploy-nginx-proxy.ps1              # Deploy proxy (one command)
├── test-proxy.ps1                      # Smoke tests
├── alertmanager.yml                    # ✅ Updated with external URLs
└── DEPLOY.md                           # Complete guide
```

---

## 🔐 Three Deployment Options

| Option | Use Case | TLS | Complexity | Deploy Time |
|--------|----------|-----|------------|-------------|
| **A: Nginx** | VPN/Internal team | No | Simple | 5 min |
| **B: Traefik** | Remote team | Yes (Let's Encrypt) | Medium | 15 min |
| **C: Caddy** | Remote team | Yes (automatic) | Simplest | 10 min |

**Recommendation**: Start with **Option A (Nginx)** for internal teams.

---

## 📋 Quick Reference

### Test URLs
```powershell
# Grafana (no auth)
http://grafana.aetherlink.local

# Alertmanager (basic auth: aether / YourPassword)
http://alertmanager.aetherlink.local

# Prometheus (optional)
http://prometheus.aetherlink.local
```

### Update Password
```powershell
# Generate new hash
docker run --rm httpd:2.4 htpasswd -nbB aether "NewPassword" > nginx/.htpasswd

# Restart nginx
docker compose -f docker-compose.nginx.yml restart
```

### View Logs
```powershell
docker logs -f aether-proxy           # Nginx
docker logs -f aether-alertmanager    # Alertmanager
```

---

## ✅ Success Criteria

Click Slack buttons from:
- [ ] Your laptop (not server)
- [ ] Team member's laptop
- [ ] Your phone
- [ ] All should work (not just localhost)

Silence button should:
- [ ] Prompt for username/password
- [ ] Pre-fill form with service + team
- [ ] Create silence successfully

---

## 🆘 Troubleshooting

### "Could not resolve host"
```powershell
# Add to hosts file (as Administrator)
.\setup-hosts.ps1
```

### "401 Unauthorized"
```powershell
# Check username/password
curl -u aether:YourPassword http://alertmanager.aetherlink.local
```

### "Slack buttons show localhost"
```powershell
# Restart Alertmanager
docker compose restart alertmanager
```

---

## 📚 Full Documentation

- **DEPLOY.md** - Complete deployment guide (this file)
- **PRODUCTION_HARDENING.md** - Security deep-dive
- **SLACK_INTERACTIVE_BUTTONS.md** - Button implementation guide
- **PROD_READY.md** - Production certification (10/10)

---

**Status**: ✅ **PRODUCTION READY**

One-click Slack → Action → Resolution. Zero SSH required.
