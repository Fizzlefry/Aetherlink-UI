# Autoheal Dry-Run + Cooldown + Ack Links - Deployment Summary

**Deployed:** November 2, 2025
**Status:** ✅ Complete - All Tests Passing

## What Was Shipped

### 1. Dry-Run Mode (Safe by Default)
**File:** `monitoring/autoheal/main.py`

**New Configuration:**
- `AUTOHEAL_DRY_RUN=true` (default) - Logs actions without executing
- `AUTOHEAL_ENABLED=false` - Master kill switch
- Both must be enabled to execute real actions

**Benefit:** Safe testing in production - see what would happen without risk

---

### 2. Per-Alert Cooldowns
**Configuration:** Environment variables in `docker-compose.yml`

**Cooldown Settings:**
- `DEFAULT_COOLDOWN_SEC: 600` (10 minutes)
- `COOLDOWN_TCP_DOWN_SEC: 600`
- `COOLDOWN_UPTIME_FAIL_SEC: 600`
- `COOLDOWN_SCRAPE_STALE_SEC: 600`

**New Metrics:**
```
autoheal_cooldown_remaining_seconds{alertname}  # Seconds until next action allowed
autoheal_action_last_timestamp{alertname}       # Unix timestamp of last action
autoheal_actions_total{alertname, result}       # Counter by result type
```

**Result Types:**
- `executed` - Action ran successfully
- `failed` - Action ran but returned error
- `dry_run` - Dry-run mode (logged only)
- `cooldown_skip` - Skipped due to cooldown
- `error` - Exception during execution

**Benefit:** Prevents flapping storms - max 1 action per alert per 10 minutes

---

### 3. Slack Ack Links (No Slack App Required)
**Files:**
- `monitoring/alert-templates.tmpl` (template updated)
- `monitoring/autoheal/main.py` (new `/ack` endpoint)

**How It Works:**
Slack alerts now include clickable links:
```
Acknowledge:
• 30m | 2h | 24h
```

Clicking a link:
1. Calls `http://localhost:9009/ack?labels={...}&duration=30m`
2. Creates exact-match silence in Alertmanager
3. Returns silence ID

**Benefit:** One-click acknowledge from Slack without UI context switching

---

### 4. Prometheus Recording Rules
**File:** `monitoring/prometheus-recording-rules.yml`

**New Rules:**
```yaml
autoheal:cooldown_active          # Any alert with cooldown remaining > 0
autoheal:actions:rate_5m          # Action rate (5m window)
```

**Usage:**
- Dashboard: Show which alerts are in cooldown
- Alerts: Detect if autoheal is stuck/flapping
- Metrics: Track automation activity over time

---

### 5. Enhanced Observability
**New Endpoint:** `http://localhost:9009/`

**Response:**
```json
{
  "status": "ok",
  "enabled": false,
  "dry_run": true,
  "actions": ["CrmMetricsScrapeStale", "TcpEndpointDownFast", "UptimeProbeFailing"],
  "public_base_url": "http://localhost:9009"
}
```

**Prometheus Metrics Endpoint:** `http://localhost:9009/metrics`

**New Series:**
- `autoheal_enabled` - 1 if enabled, 0 if disabled
- `autoheal_actions_total{alertname, result}` - Total actions by result
- `autoheal_action_last_timestamp{alertname}` - Last action epoch
- `autoheal_cooldown_remaining_seconds{alertname}` - Cooldown remaining

---

## Configuration

### Environment Variables (docker-compose.yml)
```yaml
AUTOHEAL_ENABLED: "false"              # Master kill switch
AUTOHEAL_DRY_RUN: "true"               # Safe mode (default)
ALERTMANAGER_URL: "http://alertmanager:9093"
AUTOHEAL_PUBLIC_URL: "http://localhost:9009"
AUTOHEAL_DEFAULT_COOLDOWN_SEC: "600"   # 10 minutes
COOLDOWN_TCP_DOWN_SEC: "600"
COOLDOWN_UPTIME_FAIL_SEC: "600"
COOLDOWN_SCRAPE_STALE_SEC: "600"
```

### Action Mapping (Per Alert)
```python
"CrmMetricsScrapeStale" → "docker restart crm-api"
"TcpEndpointDownFast"   → "docker restart crm-api"
"UptimeProbeFailing"    → "docker compose restart grafana prometheus"
```

---

## Validation Results

### ✅ All Tests Passing
```
[Test 1: Service Health]
  Status: ok ✅
  Enabled: False ✅
  Dry-Run: True ✅
  Actions: 3 ✅

[Test 2: Metrics Endpoint]
  autoheal_enabled: OK ✅
  autoheal_actions_total: OK ✅
  autoheal_cooldown_remaining_seconds: OK ✅

[Test 3: Prometheus Recording Rules]
  autoheal:cooldown_active: OK ✅
  autoheal:actions:rate_5m: OK ✅

[Test 4: Ack Endpoint]
  Silence created: 6e30f97f... ✅
  OK: true ✅
  Cleaned up test silence ✅

[Test 5: Cooldown Configuration]
  COOLDOWN_TCP_DOWN_SEC: 600s ✅
  COOLDOWN_SCRAPE_STALE_SEC: 600s ✅
  COOLDOWN_UPTIME_FAIL_SEC: 600s ✅
  AUTOHEAL_DEFAULT_COOLDOWN_SEC: 600s ✅

[Test 6: Alert Webhook Dry-Run]
  Webhook received: OK ✅
  Result: dry_run ✅
  Dry-run mode: WORKING ✅
```

---

## How to Use

### Check Autoheal Status
```powershell
# Service health
Invoke-RestMethod 'http://localhost:9009/'

# Metrics
Invoke-RestMethod 'http://localhost:9009/metrics' | Select-String autoheal

# Recording rules
Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=autoheal:cooldown_active'
```

### Test Ack Endpoint
```powershell
# Create 30m silence for test alert
Invoke-RestMethod 'http://localhost:9009/ack?labels=%7B%22alertname%22%3A%22TestAlert%22%7D&duration=30m&comment=Test'

# List silences
Invoke-RestMethod 'http://localhost:9093/api/v2/silences'
```

### Run Smoke Test
```powershell
cd C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring
.\scripts\autoheal-smoke.ps1
```

### Enable Autoheal (Production)
```powershell
# Step 1: Keep dry-run ON, enable autoheal
docker compose --profile dev down autoheal
# Edit docker-compose.yml: AUTOHEAL_ENABLED: "true"
docker compose --profile dev up -d autoheal

# Step 2: Monitor dry-run logs for 24h
docker logs aether-autoheal --tail 100

# Step 3: If confident, disable dry-run
# Edit docker-compose.yml: AUTOHEAL_DRY_RUN: "false"
docker compose --profile dev restart autoheal
```

---

## Safety Features

### 🛡️ Triple Safety Gates
1. **Opt-in Required:** Alert must have `autoheal: "true"` annotation
2. **Allowlist:** Alert must be in `PER_ALERT_COOLDOWN_SEC` map
3. **Cooldown:** 10 minutes between actions per alert (configurable)

### 🔍 Full Observability
- Every action logged with result type
- Cooldown remaining exposed as metric
- Prometheus alerts can detect stuck/flapping automation
- Grafana dashboards can show action history

### 🎯 Dry-Run Mode
- Default: `AUTOHEAL_DRY_RUN=true`
- Logs exactly what would happen
- No actions executed
- Same code path as real mode
- Perfect for testing in production

---

## What This Unlocks

### 🎫 One-Click Acknowledgment
- Team clicks "30m" in Slack
- Silence created instantly
- No UI navigation needed
- Works from mobile

### 📊 Observable Automation
- See what would run (dry-run)
- See what did run (metrics)
- See what's in cooldown (recording rules)
- Alert on automation issues

### 🚦 Progressive Rollout
```
Phase 1: ENABLED=false, DRY_RUN=true  (current)
  → Log only, no actions

Phase 2: ENABLED=true, DRY_RUN=true
  → Metrics track "would execute", log actions

Phase 3: ENABLED=true, DRY_RUN=false
  → Full automation with cooldowns
```

---

## Next Steps

**Optional Enhancements:**
1. Add Grafana panels for autoheal metrics
2. Create alert for stuck autoheal (no actions in 24h while enabled)
3. Add per-alert cooldown adjustment via Slack commands
4. Implement silence comment with runbook link

**Suggested Next Pack:** "Real-time Event Stream + Audit Trail"
- Autoheal action history in postgres
- Event stream for all automation
- Audit log with who/what/when
- Rollback capability

---

## Files Changed

**Modified:**
- `monitoring/autoheal/main.py` - Complete rewrite with new features
- `monitoring/autoheal/requirements.txt` - Added `requests==2.31.0`
- `monitoring/docker-compose.yml` - Added 8 new environment variables
- `monitoring/alert-templates.tmpl` - Added Ack links
- `monitoring/prometheus-recording-rules.yml` - Added 2 autoheal rules

**Created:**
- `monitoring/scripts/autoheal-smoke.ps1` - Comprehensive test suite

**Dependencies:**
- prometheus-client==0.20.0 ✅
- fastapi==0.115.5 ✅
- uvicorn==0.32.0 ✅
- requests==2.31.0 ✅ (new)

---

## Current State

```
✅ Dry-run mode: Active
✅ Cooldowns: 600s per alert
✅ Metrics: Exposed and scraped
✅ Recording rules: Active (39 total)
✅ Ack endpoint: Working
✅ Slack links: Ready (in template)
✅ Smoke tests: All passing
```

**Production Ready:** Yes (in dry-run mode)
**Automation Ready:** Yes (flip DRY_RUN=false when confident)
