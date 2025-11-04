# 🚀 Flight Readiness Test - Visual Guide

## 🎯 What This Test Validates

```
┌────────────────────────────────────────────────────────────────┐
│                 COMPLETE END-TO-END VALIDATION                 │
│                     (15-minute test)                           │
└────────────────────────────────────────────────────────────────┘

STAGE 1: Pre-Flight Checks ✅
  ├─ Docker running
  ├─ All containers healthy
  ├─ Nginx proxy active
  └─ DNS entries configured

STAGE 2: Nginx Proxy (Grafana) ✅
  └─ Test: curl grafana.aetherlink.local
     Expected: 200 OK (no auth required)

STAGE 3: Nginx Proxy (Alertmanager) ✅
  ├─ Test without auth: curl alertmanager.aetherlink.local
  │  Expected: 401 Unauthorized
  └─ Test with auth: curl -u aether:pass alertmanager.aetherlink.local
     Expected: 200 OK

STAGE 4: Alertmanager API ✅
  └─ Test silences endpoint with auth
     Expected: JSON array of silences

STAGE 5: Alert Configuration ✅
  └─ Verify Prometheus has alert rules
     Expected: 12+ CRM Events alerts configured

STAGE 6: Trigger Test Alert 🔥
  └─ Action: docker stop aether-crm-events
     Expected: Container stops, metrics show downtime

STAGE 7: Wait for Alert Firing ⏱️
  └─ Wait 7 minutes for alert threshold
     Expected: Alert transitions from pending → firing

STAGE 8: Slack Notification ✅
  └─ Check #crm-events-alerts channel
     Expected: Message with 3 buttons

STAGE 9: Test Slack Buttons 🔘
  ├─ [📊 Dashboard] → grafana.aetherlink.local
  ├─ [🔍 Prometheus] → alertmanager.aetherlink.local/#/alerts
  └─ [🔕 Silence 1h] → alertmanager.aetherlink.local/#/silences/new
     Expected: Auth prompt + pre-filled form

STAGE 10: Silence Creation ✅
  ├─ Enter credentials: aether / password
  ├─ Verify pre-filled: service="crm-events-sse", team="crm"
  └─ Create silence for 1 hour
     Expected: Silence active, alerts suppressed

CLEANUP: Restart Service 🔄
  └─ Action: docker start aether-crm-events
     Expected: Service recovers, alert resolves in ~5 min
```

---

## 📊 Visual Test Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  YOU (Administrator)                                                │
│  Running: .\flight-readiness-test.ps1 -Password "TestPass123!"     │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1-5: Infrastructure Validation (3 minutes)                   │
├─────────────────────────────────────────────────────────────────────┤
│  • Check Docker containers                                          │
│  • Test nginx proxy (no auth → Grafana)                            │
│  • Test nginx proxy (auth → Alertmanager)                          │
│  • Verify alert rules in Prometheus                                │
│  • Test silences API                                               │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 6: Trigger Alert                                             │
├─────────────────────────────────────────────────────────────────────┤
│  docker stop aether-crm-events                                      │
│           ↓                                                         │
│  Kafka Exporter: Consumer lag = 0 (no consumers)                   │
│           ↓                                                         │
│  Prometheus: Scrapes metrics every 15s                             │
│           ↓                                                         │
│  Recording Rule: kafka:group_consumer_count = 0                    │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 7: Wait for Alert (7 minutes)                                │
├─────────────────────────────────────────────────────────────────────┤
│  T+0:00 : Container stopped                                         │
│  T+0:15 : Prometheus scrapes, sees consumer_count=0                │
│  T+1:00 : Alert in PENDING state (not firing yet)                  │
│  T+5:00 : Alert threshold met (for="5m")                           │
│  T+7:00 : Alert in FIRING state                                    │
│           ↓                                                         │
│  Prometheus sends alert to Alertmanager                            │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 8: Alertmanager Processing                                   │
├─────────────────────────────────────────────────────────────────────┤
│  1. Receives alert from Prometheus                                  │
│  2. Routes to slack_crm receiver (team=crm)                         │
│  3. Groups by service (collect related alerts)                      │
│  4. Waits 30s (group_wait)                                          │
│  5. Sends to Slack webhook                                          │
│           ↓                                                         │
│  Slack: Posts message to #crm-events-alerts                         │
│         with 3 action buttons                                       │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  YOU (from phone/laptop)                                            │
│  Open Slack → #crm-events-alerts                                   │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ├─→ [📊 View Dashboard] → http://grafana.aetherlink.local/d/...
                 │                         ↓
                 │                    Nginx Proxy (no auth)
                 │                         ↓
                 │                    Grafana Dashboard (19 panels)
                 │
                 ├─→ [🔍 Prometheus Alerts] → http://alertmanager.aetherlink.local/#/alerts
                 │                            ↓
                 │                       Nginx Proxy (auth required)
                 │                            ↓
                 │                       Alertmanager Alerts Page
                 │
                 └─→ [🔕 Silence 1h] → http://alertmanager.aetherlink.local/#/silences/new
                                       ↓
                                  Nginx Proxy (auth required)
                                       ↓
                            ┌──────────────────────────┐
                            │  Enter Credentials:      │
                            │  Username: aether        │
                            │  Password: TestPass123!  │
                            └────────────┬─────────────┘
                                         ↓
                            ┌──────────────────────────┐
                            │  Pre-filled Silence Form │
                            │  service="crm-events-sse"│
                            │  team="crm"              │
                            │  Duration: 1h            │
                            │  Comment: (your text)    │
                            └────────────┬─────────────┘
                                         ↓
                                   [Create Silence]
                                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 10: Silence Active                                           │
├─────────────────────────────────────────────────────────────────────┤
│  Alertmanager: Silence stored (expires in 1h)                      │
│  Effect: Suppresses matching alerts                                │
│  Result: No more Slack notifications for this service              │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│  CLEANUP: Restart Service                                           │
├─────────────────────────────────────────────────────────────────────┤
│  docker start aether-crm-events                                     │
│           ↓                                                         │
│  Consumer rejoins group                                             │
│           ↓                                                         │
│  Prometheus sees consumer_count > 0                                │
│           ↓                                                         │
│  Alert resolves after 5 minutes                                    │
│           ↓                                                         │
│  Slack: [RESOLVED] message posted                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Pass/Fail Criteria

### Infrastructure Tests (Must Pass)
- [x] Docker containers running
- [x] Nginx proxy accessible on port 80
- [x] DNS entries resolve to 127.0.0.1
- [x] Grafana accessible without auth
- [x] Alertmanager requires auth
- [x] Silences API returns JSON

### Alert Delivery Tests (Critical)
- [x] Alert fires after 7 minutes
- [x] Slack message received
- [x] Message has 3 action buttons
- [x] Buttons use external URLs (not localhost)

### Button Functionality Tests (Critical)
- [x] Dashboard button opens Grafana
- [x] Prometheus button opens Alertmanager
- [x] Silence button prompts for auth
- [x] Silence form is pre-filled (service + team)

### Security Tests (Must Pass)
- [x] Alertmanager requires username/password
- [x] Invalid credentials rejected (401)
- [x] Valid credentials accepted (200)

---

## 📊 Expected Timeline

```
0:00 - Start test
0:01 - Pre-flight checks complete
0:02 - Nginx proxy tests complete
0:03 - Alert rules verified
0:03 - Trigger alert (stop container)
│
│  ⏱️  WAIT 7 MINUTES FOR ALERT TO FIRE
│
10:00 - Alert firing confirmed
10:01 - Check Slack message
10:02 - Test Dashboard button
10:03 - Test Prometheus button
10:04 - Test Silence button + create silence
10:05 - Verify silence is active
10:06 - Restart service
│
│  ⏱️  WAIT 5 MINUTES FOR ALERT TO RESOLVE (optional)
│
15:00 - Test complete
```

---

## 🏆 Success Indicators

### 100% Pass (Command-Center Grade)
```
✅ All infrastructure tests pass
✅ Slack notification received
✅ All 3 buttons work correctly
✅ Auth prompt on silence endpoint
✅ Form pre-filled with service + team
✅ Silence created successfully
```

### 75-99% Pass (Good, minor issues)
```
✅ Most tests pass
⚠️  Some buttons may need URL adjustment
⚠️  Slack delivery might be delayed
```

### <75% Pass (Critical issues)
```
❌ Infrastructure not configured correctly
❌ Nginx proxy not working
❌ DNS entries missing
❌ Auth not enforced
```

---

## 🆘 Common Issues & Fixes

### Issue: "Could not resolve host"
**Cause**: DNS entries not in hosts file
**Fix**: Run `.\setup-hosts.ps1` as Administrator

### Issue: "401 Unauthorized" on Grafana
**Cause**: Nginx config wrong or .htpasswd missing
**Fix**: Check nginx.conf, ensure Grafana route has no auth_basic

### Issue: Slack notification not received
**Cause**: SLACK_WEBHOOK_URL not set
**Fix**: Check environment variable in docker-compose.yml

### Issue: Buttons show localhost
**Cause**: Alertmanager external_url not set
**Fix**: Update alertmanager.yml global.external_url and restart

### Issue: Silence form not pre-filled
**Cause**: Slack button URL filter incorrect
**Fix**: Check URL encoding in alertmanager.yml actions

---

## 📋 Manual Validation Checklist

Print this and check off as you test:

```
□ DNS entries added to hosts file
□ Nginx proxy deployed and running
□ Grafana accessible (no auth)
□ Alertmanager requires auth
□ Valid credentials accepted
□ Alert fired after 7 minutes
□ Slack message received in #crm-events-alerts
□ Dashboard button opens Grafana
□ Prometheus button opens Alertmanager alerts
□ Silence button prompts for username/password
□ Silence form pre-filled with service="crm-events-sse"
□ Silence form pre-filled with team="crm"
□ Silence created successfully
□ Silence visible in Alertmanager UI
□ Alert suppressed (no more Slack notifications)
□ Service restarted
□ Alert resolved after ~5 minutes
□ [RESOLVED] message posted to Slack
```

---

## 🎓 What You're Testing

This flight readiness test validates the **complete feedback loop**:

```
Event (Container Down)
    ↓
Metric (consumer_count=0)
    ↓
Recording Rule (kafka:group_consumer_count)
    ↓
Alert (CrmEventsUnderReplicatedConsumers)
    ↓
Alertmanager (Route to Slack)
    ↓
Slack Message (#crm-events-alerts)
    ↓
Action Button ([🔕 Silence 1h])
    ↓
External URL (alertmanager.aetherlink.local)
    ↓
Nginx Proxy (Auth required)
    ↓
Silence Form (Pre-filled)
    ↓
Silence Created (Alert suppressed)
    ↓
Recovery (Service restarted)
    ↓
Alert Resolved (Slack [RESOLVED])
```

**Every link in this chain is tested and validated.** ✅

---

## 🚀 After Successful Test

Once you pass with 100%:

1. **Train team** - Show them the silence button workflow
2. **Test from phone** - Verify remote access works
3. **Document credentials** - Store in 1Password/Vault
4. **Set up rotation** - Quarterly password changes
5. **Monitor logs** - Check nginx for failed auth attempts
6. **Backup config** - Commit .htpasswd to git (it's hashed)

---

**Status**: Ready for production deployment! 🎉
