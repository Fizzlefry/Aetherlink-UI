# Slack Alert Integration Guide

## 🔔 Overview

This guide shows how to enable instant Slack notifications for your CRM Events monitoring stack. Alerts will route to `#crm-events-alerts` channel with rich formatting based on your clean labels (`team=crm`, `service=crm-events-sse`, `product=aetherlink`).

---

## 🚀 Quick Setup (2 minutes)

### 1. Create Slack Incoming Webhook

1. Navigate to: https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. App Name: `AetherLink Monitoring`
4. Workspace: Your workspace
5. Click **"Incoming Webhooks"** → **"Activate Incoming Webhooks"**
6. Click **"Add New Webhook to Workspace"**
7. Select channel: `#crm-events-alerts` (create if needed)
8. Copy the webhook URL (looks like: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`)

### 2. Configure Alertmanager

**Option A: Environment Variable (Recommended)**

```yaml
# In docker-compose.yml
services:
  alertmanager:
    environment:
      - SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Option B: Direct Configuration**

```yaml
# In monitoring/alertmanager.yml (line 56)
# Replace ${SLACK_WEBHOOK_URL} with your actual webhook URL
api_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### 3. Restart Alertmanager

```powershell
cd C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring
docker compose restart alertmanager
```

### 4. Test the Integration

```powershell
# Trigger a test alert by stopping the consumer
docker stop aether-crm-events

# Wait 7 minutes for CrmEventsUnderReplicatedConsumers alert
# Check #crm-events-alerts channel in Slack

# Restore consumer
docker start aether-crm-events

# Wait 2 minutes for resolution notification
```

---

## 📊 Alert Message Format

### Firing Alert Example

```
🚨 CrmEventsHotKeySkewHigh

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: FIRING

🔥 WARNING — Hot-key skew detected in CRM Events consumer

Skew ratio exceeded 4x threshold for 12 minutes. One partition is accumulating
significantly more lag than others.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline
📊 Dashboard: http://localhost:9090/alerts

---

Firing: 1 | Resolved: 0
```

**Color**: 🟡 Yellow (warning) or 🔴 Red (critical)

### Resolved Alert Example

```
✅ CrmEventsHotKeySkewHigh

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: RESOLVED

✅ WARNING — Hot-key skew detected in CRM Events consumer

Skew ratio returned below 4x threshold. Partition lag is now balanced.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline
📊 Dashboard: http://localhost:9090/alerts

---

Firing: 0 | Resolved: 1
```

**Color**: 🟢 Green (resolved)

---

## 🎯 Routing Logic

Alerts are routed based on your clean labels:

### Route 1: CRM Events (Highest Priority)
```yaml
matchers:
  - team="crm"
  - service="crm-events-sse"
```
- **Channel**: `#crm-events-alerts`
- **Group by**: `alertname`, `consumergroup`
- **Group wait**: 15s (fast initial notification)
- **Repeat interval**: 2h (don't spam)

**Alerts Routed**:
- `CrmEventsHotKeySkewHigh`
- `CrmEventsUnderReplicatedConsumers`
- `CrmEventsPartitionStuck`
- `CrmEventsServiceDown`
- `CrmEventsHighLag`
- All other alerts with `team=crm` + `service=crm-events-sse`

### Route 2: General CRM (Lower Priority)
```yaml
matchers:
  - team="crm"
```
- **Channel**: `#crm-events-alerts` (same channel)
- **Repeat interval**: 2h

**Alerts Routed**:
- All CRM service alerts (finance, API, etc.)

### Route 3: Default (All Other Alerts)
- **Receiver**: `agent` (webhook to aether-agent)
- **Purpose**: Learning/analysis, not user notifications

---

## 📋 Alert Label Reference

Every alert includes these labels for smart routing:

| Label | Example Value | Purpose |
|-------|---------------|---------|
| `team` | `crm` | Routes to team channel |
| `service` | `crm-events-sse` | Identifies specific service |
| `product` | `aetherlink` | Product context |
| `consumergroup` | `crm-events-sse` | Kafka consumer group |
| `alertname` | `CrmEventsHotKeySkewHigh` | Alert identifier |
| `severity` | `warning` or `critical` | Determines color/urgency |

---

## 🎨 Customization

### Change Slack Channel

```yaml
# In alertmanager.yml (line 54)
slack_configs:
  - channel: "#your-channel-name"
```

Common patterns:
- `#ops-alerts` - Operations team
- `#crm-monitoring` - CRM team only
- `#critical-alerts` - Critical severity only
- `@username` - Direct message

### Add Multiple Channels by Severity

```yaml
route:
  routes:
    # Critical alerts → escalation channel
    - matchers:
        - team="crm"
        - severity="critical"
      receiver: slack_crm_critical
      repeat_interval: 30m

    # Warning alerts → normal channel
    - matchers:
        - team="crm"
      receiver: slack_crm
      repeat_interval: 2h

receivers:
  - name: slack_crm_critical
    slack_configs:
      - channel: "#crm-critical"
        api_url: "${SLACK_WEBHOOK_URL}"
        send_resolved: true
        # ... rest of config

  - name: slack_crm
    slack_configs:
      - channel: "#crm-events-alerts"
        # ... rest of config
```

### Customize Message Template

```yaml
# In alertmanager.yml (line 59)
text: |-
  *🚨 {{ .CommonLabels.alertname }}*

  {{ range .Alerts -}}
  *Summary*: {{ .Annotations.summary }}
  *Details*: {{ .Annotations.description }}
  *Runbook*: {{ .Annotations.runbook_url }}

  *Prometheus*: http://localhost:9090/alerts
  *Grafana*: http://localhost:3000/d/crm-events-pipeline
  {{ end }}
```

### Add @mentions for Critical Alerts

```yaml
text: |-
  {{ if eq .CommonLabels.severity "critical" }}<!here> :rotating_light:{{ end }}

  *{{ .CommonLabels.alertname }}*
  {{ range .Alerts -}}
  {{ .Annotations.summary }}
  {{ end }}
```

**Mention Options**:
- `<!here>` - Notify active users
- `<!channel>` - Notify all users
- `<@U123456>` - Mention specific user (use Slack user ID)
- `@on-call` - Mention user group (configure in Slack first)

---

## 🧪 Testing

### Test Alert (Manual Trigger)

```powershell
# Send test alert via curl
$alertJson = @"
[
  {
    "labels": {
      "alertname": "TestAlert",
      "team": "crm",
      "service": "crm-events-sse",
      "severity": "warning",
      "consumergroup": "crm-events-sse"
    },
    "annotations": {
      "summary": "This is a test alert",
      "description": "Testing Slack integration"
    },
    "startsAt": "$(Get-Date -Format o)"
  }
]
"@

Invoke-RestMethod -Uri "http://localhost:9093/api/v1/alerts" `
  -Method POST `
  -ContentType "application/json" `
  -Body $alertJson

# Check #crm-events-alerts channel in Slack
```

### Test Real Alert (Hot-Key Skew)

```powershell
# Produce hot-key messages
$evt = '{"Type":"Test","Key":"HOTKEY"}'
1..300 | % { $evt | docker exec -i kafka rpk topic produce --key HOTKEY aetherlink.events }

# Wait 12 minutes for CrmEventsHotKeySkewHigh alert
# Check Prometheus: http://localhost:9090/alerts
# Check Slack: #crm-events-alerts

# Alert should appear with:
# - Title: 🚨 CrmEventsHotKeySkewHigh
# - Service: crm-events-sse
# - Status: FIRING
# - Runbook link
```

### Verify Routing

```powershell
# Check Alertmanager routing tree
curl.exe http://localhost:9093/api/v1/status | ConvertFrom-Json | ConvertTo-Json -Depth 10

# View current alerts
curl.exe http://localhost:9093/api/v1/alerts | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

## 🔍 Troubleshooting

### Slack Notifications Not Received

**1. Check webhook URL is set**:
```powershell
docker exec alertmanager printenv SLACK_WEBHOOK_URL
```
Expected: `https://hooks.slack.com/services/...`

**2. Check Alertmanager logs**:
```powershell
docker logs alertmanager --tail 50
```
Look for: `"msg"="Notifying Slack"` or `"err"="webhook returned HTTP error"`

**3. Test webhook directly**:
```powershell
$testPayload = @{
    text = "Test from AetherLink Monitoring"
} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_WEBHOOK_URL" `
  -Method POST `
  -ContentType "application/json" `
  -Body $testPayload
```
Expected: Message appears in Slack channel

**4. Verify route matching**:
```powershell
# Check if alert has correct labels
curl.exe http://localhost:9090/api/v1/rules | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Look for: team=crm, service=crm-events-sse
```

### Alerts Routed to Wrong Channel

**Check route order** (first match wins):
```yaml
# In alertmanager.yml
route:
  routes:
    - matchers:
        - team="crm"
        - service="crm-events-sse"
      receiver: slack_crm  # ✅ This matches first
      continue: true

    - matchers:
        - team="crm"
      receiver: slack_crm_general  # ⚠️ Won't match CRM Events (already matched)
      continue: true
```

**Solution**: Most specific routes first, general routes last.

### Too Many Notifications (Spam)

**Increase repeat interval**:
```yaml
# In alertmanager.yml (line 16)
routes:
  - matchers:
      - team="crm"
    receiver: slack_crm
    repeat_interval: 4h  # Changed from 2h
```

**Add grouping**:
```yaml
routes:
  - matchers:
      - team="crm"
    receiver: slack_crm
    group_by: ["alertname", "service"]  # Group related alerts
    group_wait: 30s      # Wait 30s for related alerts
    group_interval: 5m   # Send grouped updates every 5m
```

### Resolved Notifications Not Received

**Check send_resolved flag**:
```yaml
# In alertmanager.yml (line 102)
slack_configs:
  - channel: "#crm-events-alerts"
    api_url: "${SLACK_WEBHOOK_URL}"
    send_resolved: true  # ✅ Must be true
```

---

## 📊 Slack Notification Examples

### Example 1: Hot-Key Skew Alert

**Firing** (12:00 PM):
```
🚨 CrmEventsHotKeySkewHigh

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: FIRING

🔥 WARNING — Hot-key skew detected in CRM Events consumer

Skew ratio is 6.2x (threshold: 4.0x). Partition 2 has 850 messages
while partitions 0 and 1 have ~137 each.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline
📊 Dashboard: http://localhost:9090/alerts

Alert Name: CrmEventsHotKeySkewHigh | Service: crm-events-sse
Consumer Group: crm-events-sse         | Severity: WARNING

Firing: 1 | Resolved: 0
```
**Color**: 🟡 Yellow

**Resolved** (12:18 PM):
```
✅ CrmEventsHotKeySkewHigh

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: RESOLVED

✅ WARNING — Hot-key skew detected in CRM Events consumer

Skew ratio returned to 1.2x. Partition lag is now balanced.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline
📊 Dashboard: http://localhost:9090/alerts

Firing: 0 | Resolved: 1
```
**Color**: 🟢 Green

### Example 2: Under-Replicated Consumers

**Firing**:
```
🚨 CrmEventsUnderReplicatedConsumers

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: FIRING

🔥 WARNING — Consumer group under-replicated

Only 1 active consumer (threshold: 2). Single point of failure detected.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline

Action: Scale up consumers immediately
Command: docker compose up -d --scale crm-events=2

Firing: 1 | Resolved: 0
```
**Color**: 🟡 Yellow

### Example 3: Service Down (Critical)

**Firing**:
```
🚨 CrmEventsServiceDown

Service: crm-events-sse
Team: crm
Product: aetherlink
Consumer Group: crm-events-sse
Status: FIRING

🔥 CRITICAL — CRM Events service is down

No consumer heartbeat detected for 5 minutes. Service is offline.

📖 Runbook: http://localhost:3000/d/crm-events-pipeline

Action: Check container logs
Command: docker logs aether-crm-events --tail 50

Firing: 1 | Resolved: 0
```
**Color**: 🔴 Red

---

## 🎓 Best Practices

### 1. Channel Organization

**Option A: Single Channel (Recommended for Small Teams)**
```
#crm-events-alerts
  ├─ All CRM Events alerts
  ├─ Firing + Resolved notifications
  └─ Low noise (2h repeat interval)
```

**Option B: Split by Severity (Recommended for Large Teams)**
```
#crm-critical        → Critical alerts only (page on-call)
#crm-warnings        → Warning alerts (check during business hours)
#crm-info            → Info alerts (review weekly)
```

**Option C: Split by Component**
```
#crm-events-alerts   → Consumer/Kafka alerts
#crm-api-alerts      → API/service alerts
#crm-finance-alerts  → Finance/revenue alerts
```

### 2. Alert Fatigue Prevention

- ✅ Use `repeat_interval: 2h` or longer (don't spam)
- ✅ Set `group_by: ["alertname", "service"]` (combine related alerts)
- ✅ Enable `send_resolved: true` (know when issues are fixed)
- ✅ Use inhibition rules (prevent duplicate alerts)
- ❌ Avoid `repeat_interval: 5m` (creates alert fatigue)
- ❌ Don't route low-priority alerts to critical channels

### 3. On-Call Integration

**With PagerDuty**:
```yaml
receivers:
  - name: pagerduty_critical
    pagerduty_configs:
      - service_key: "${PAGERDUTY_SERVICE_KEY}"
        severity: "{{ .CommonLabels.severity }}"

route:
  routes:
    - matchers:
        - severity="critical"
      receiver: pagerduty_critical
      continue: true  # Also send to Slack
```

**With Opsgenie**:
```yaml
receivers:
  - name: opsgenie_critical
    opsgenie_configs:
      - api_key: "${OPSGENIE_API_KEY}"
        priority: "P1"

route:
  routes:
    - matchers:
        - severity="critical"
      receiver: opsgenie_critical
      continue: true
```

### 4. Testing in Dev

```yaml
# dev-alertmanager.yml (separate config for development)
route:
  receiver: slack_dev
  repeat_interval: 5m  # Faster in dev for testing

receivers:
  - name: slack_dev
    slack_configs:
      - channel: "#dev-alerts"  # Separate dev channel
        api_url: "${SLACK_WEBHOOK_URL_DEV}"
        title: "[DEV] {{ .CommonLabels.alertname }}"
        send_resolved: true
```

---

## 🔐 Security Considerations

### 1. Webhook URL Protection

**❌ Don't**:
```yaml
# Bad: Hardcoded in version control
api_url: "https://hooks.slack.com/services/T00/B00/XXX"
```

**✅ Do**:
```yaml
# Good: Environment variable
api_url: "${SLACK_WEBHOOK_URL}"
```

```powershell
# Set in docker-compose.yml or .env file
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SECRET/URL
```

### 2. Sensitive Data in Alerts

**Redact sensitive values**:
```yaml
# In prometheus-crm-events-rules.yml
annotations:
  description: |-
    Consumer {{ $labels.consumergroup }} has {{ $value }} consumers
    # ❌ Don't include: customer IDs, emails, tokens
```

### 3. Public Webhook URLs

- ✅ Use Slack's signed secrets (App-level tokens)
- ✅ Restrict webhook to specific channels
- ✅ Monitor webhook usage (Slack logs)
- ❌ Don't share webhook URLs in public repos

---

## 📈 Advanced Configuration

### Message Threading (Group Related Alerts)

```yaml
# Note: Requires Slack App with OAuth (not incoming webhook)
slack_configs:
  - channel: "#crm-events-alerts"
    api_url: "${SLACK_WEBHOOK_URL}"
    thread_ts: "{{ .GroupLabels.alertname }}"  # Thread by alert name
```

### Add Buttons (Actions)

```yaml
# Note: Requires Slack App with Interactive Components
slack_configs:
  - channel: "#crm-events-alerts"
    actions:
      - type: "button"
        text: "View Dashboard"
        url: "http://localhost:3000/d/crm-events-pipeline"
      - type: "button"
        text: "Silence 1h"
        url: "http://localhost:9093/#/silences/new"
```

### Conditional Formatting

```yaml
text: |-
  {{ if eq .CommonLabels.alertname "CrmEventsHotKeySkewHigh" }}
  :fire: *HOT-KEY SKEW DETECTED*

  Check Panel 17 for partition lag distribution.
  {{ else if eq .CommonLabels.alertname "CrmEventsServiceDown" }}
  :rotating_light: *SERVICE DOWN*

  Immediate action required!
  {{ else }}
  :warning: *{{ .CommonLabels.alertname }}*
  {{ end }}
```

---

## 🚀 Deployment Checklist

- [ ] Create Slack channel: `#crm-events-alerts`
- [ ] Create Slack Incoming Webhook
- [ ] Set `SLACK_WEBHOOK_URL` environment variable
- [ ] Update `alertmanager.yml` with webhook URL (if not using env var)
- [ ] Restart Alertmanager: `docker compose restart alertmanager`
- [ ] Test with manual alert (see Testing section)
- [ ] Verify alert appears in Slack
- [ ] Test resolved notification
- [ ] Document webhook URL in team wiki/vault
- [ ] Add on-call schedule to Slack channel description
- [ ] Set channel notification preferences (all messages vs mentions only)

---

## 📞 Support

**Slack Integration Issues**:
- Check: `docker logs alertmanager`
- Verify: Webhook URL is correct
- Test: Send test message to webhook URL directly

**Alert Not Firing**:
- Check: Prometheus rules are loaded (`http://localhost:9090/rules`)
- Verify: Alert condition is met
- Test: Query Prometheus directly with alert PromQL

**Documentation**:
- Runbook: `monitoring/docs/RUNBOOK_HOTKEY_SKEW.md`
- Quick Reference: `monitoring/QUICK_REFERENCE.md`
- Production Cert: `monitoring/PROD_READY.md`

---

**Status**: ✅ **READY FOR DEPLOYMENT**

Enable Slack notifications in 2 minutes:
```powershell
# 1. Get webhook URL from Slack
# 2. Set environment variable
$env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# 3. Restart Alertmanager
docker compose restart alertmanager

# 4. Test
docker stop aether-crm-events  # Trigger alert after 7 minutes
```
