# ⚡ QUICK START - Production GO

## 🚀 Deploy NOW (One Command)

```powershell
.\scripts\go.ps1
```

This single command:
- ✅ Validates all configs (lint)
- ✅ Hot-reloads Prometheus & Alertmanager
- ✅ Verifies 6 recording rules loaded
- ✅ Confirms 4 alerts have traffic guards
- ✅ Checks Grafana auto-provisioning
- ✅ Opens all monitoring interfaces
- ✅ Displays summary + next steps

---

## 🛡️ What Changed (Traffic Guards)

### Before (Noisy)
```yaml
expr: aether:cache_hit_ratio:5m < 30
# Problem: Fires on NaN when no traffic
```

### After (Quiet)
```yaml
expr: (aether:cache_hit_ratio:5m < 30) and sum(rate(aether_cache_requests_total[5m])) > 0
# Solution: Only fires when traffic exists
```

**Result:** Zero false alerts! 🎉

---

## 📋 Manual Validation (Optional)

```powershell
# Lint configs
promtool check config monitoring\prometheus-config.yml
promtool check rules monitoring\prometheus-recording-rules.yml
promtool check rules monitoring\prometheus-alerts.yml
amtool check-config monitoring\alertmanager.yml

# Hot-reload
curl.exe -s -X POST http://localhost:9090/-/reload
curl.exe -s -X POST http://localhost:9093/-/reload

# Open interfaces
Start-Process "http://localhost:9090/rules"
Start-Process "http://localhost:9090/alerts"
Start-Process "http://localhost:9093/#/status"
Start-Process "http://localhost:3000/dashboards"
```

---

## 🧪 Test Traffic

```powershell
$env:API_ADMIN_KEY = "admin-secret-123"
.\scripts\tenant-smoke-test.ps1
```

Wait 15-30s, then check:
- **Prometheus Rules:** http://localhost:9090/rules (should show values)
- **Grafana Dashboard:** http://localhost:3000/dashboards (gauges move)

---

## 🔔 Enable Slack (2 Minutes)

```powershell
# Set webhook
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/XXX/YYY/ZZZ"

# Restart stack
.\scripts\start-monitoring.ps1 -Restart

# Verify
Start-Process "http://localhost:9093/#/status"
```

---

## 🔄 Rollback (If Needed)

```powershell
# Revert configs
git checkout -- monitoring\prometheus-alerts.yml

# Hot-reload
curl.exe -s -X POST http://localhost:9090/-/reload
```

---

## ✅ Production GO Criteria

**READY IF:**
- ✅ `.\scripts\go.ps1` completes with no errors
- ✅ All 6 recording rules loaded
- ✅ All 4 alerts have traffic guards
- ✅ Grafana dashboard auto-provisioned

**NOT READY IF:**
- ❌ Config syntax errors
- ❌ Recording rules missing
- ❌ Alerts missing traffic guards

---

## 📚 Full Documentation

- **Quick Start:** This file
- **Complete Guide:** `monitoring/PRODUCTION_GO.md`
- **Summary:** `monitoring/PRE_PROD_GO_SUMMARY.md`
- **Hardening:** `monitoring/PRODUCTION_HARDENED.md`

---

**Production-ready in one command!** 🚀

```powershell
.\scripts\go.ps1
```
