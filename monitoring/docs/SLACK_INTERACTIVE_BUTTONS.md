# Slack Interactive Buttons - Alertmanager Silence API

## 🔘 Overview

This guide implements **interactive Slack buttons** that allow your team to silence alerts directly from Slack messages. No dashboard hopping required.

## 🎯 Features

- 🔘 **"Silence 1h" button** - Quick silence for acknowledged alerts
- 🔘 **"Silence 4h" button** - Extended silence for known issues
- 🔘 **"View Dashboard" button** - Direct link to Grafana
- 🔘 **"View in Prometheus" button** - Jump to alert in Prometheus
- ✅ **One-click actions** - No login required (internal network)

---

## 🏗️ Architecture

```
Slack Message → Button Click → Webhook Receiver → Alertmanager API → Alert Silenced
                                      ↓
                              Confirmation sent to Slack
```

**Components**:
1. **Slack Incoming Webhook** (already configured)
2. **Slack Interactive Components** (requires Slack App upgrade)
3. **Webhook Receiver** (lightweight Flask service)
4. **Alertmanager API** (silence endpoint)

---

## 🚀 Quick Implementation

### Option 1: URL Buttons (No OAuth - Recommended ✅)

**Simplest approach**: Use Slack message attachments with URL buttons. No custom receiver needed.

#### Update Alertmanager Configuration

```yaml
# monitoring/alertmanager.yml - Enhanced with URL buttons
receivers:
  - name: slack_crm
    slack_configs:
      - channel: "#crm-events-alerts"
        api_url: "${SLACK_WEBHOOK_URL}"
        send_resolved: true
        
        title: |-
          {{ if eq .Status "firing" }}🚨{{ else }}✅{{ end }} {{ .CommonLabels.service | default "CRM" }} Pipeline {{ if eq .Status "firing" }}{{ if gt (len .Alerts.Firing) 1 }}Issues ({{ len .Alerts.Firing }} alerts){{ else }}Issue{{ end }}{{ else }}Resolved{{ end }}
        
        text: |-
          *Service*: {{ .CommonLabels.service | default "unknown" }}
          *Team*: {{ .CommonLabels.team | default "unknown" }}
          *Status*: {{ .Status | upper }}
          {{ if gt (len .Alerts.Firing) 1 }}
          
          :warning: *Multiple alerts detected - grouped for clean feed*
          {{ end }}
          
          {{ range .Alerts -}}
          {{ if eq .Status "firing" }}🔥{{ else }}✅{{ end }} *{{ .Labels.severity | upper }}* — **{{ .Labels.alertname }}**
          
          {{ .Annotations.summary }}
          {{ .Annotations.description }}
          
          {{ if .Annotations.runbook_url }}📖 *Runbook*: {{ .Annotations.runbook_url }}{{ end }}
          
          ---
          {{ end }}
          
          *Firing*: {{ .Alerts.Firing | len }} | *Resolved*: {{ .Alerts.Resolved | len }}
        
        color: |-
          {{ if eq .Status "firing" }}{{ if eq .CommonLabels.severity "critical" }}danger{{ else }}warning{{ end }}{{ else }}good{{ end }}
        
        # ✅ Add action buttons (URLs)
        actions:
          - type: button
            text: "📊 View Dashboard"
            url: "http://localhost:3000/d/crm-events-pipeline"
          
          - type: button
            text: "🔍 View in Prometheus"
            url: "http://localhost:9090/alerts?search={{ .GroupLabels.alertname }}"
          
          - type: button
            text: "🔕 Silence 1h"
            url: "http://localhost:9093/#/silences/new?filter=%7Bservice%3D%22{{ .CommonLabels.service }}%22%7D"
          
          - type: button
            text: "🔕 Silence 4h"
            url: "http://localhost:9093/#/silences/new?filter=%7Bservice%3D%22{{ .CommonLabels.service }}%22%2Cduration%3D4h%7D"
```

**Benefits**:
- ✅ No custom receiver needed
- ✅ Works with incoming webhooks (no OAuth)
- ✅ 5-minute setup
- ⚠️ Opens browser (not true one-click)

---

### Option 2: Interactive Buttons (Full OAuth - Advanced)

**True one-click**: Buttons trigger webhook without opening browser. Requires Slack App upgrade.

#### Step 1: Upgrade Slack App to Interactive Components

1. Visit: https://api.slack.com/apps
2. Select your app: "AetherLink Monitoring"
3. Navigate to: **Interactivity & Shortcuts**
4. Enable **Interactivity**
5. Set **Request URL**: `http://YOUR_PUBLIC_IP:9095/slack/interactive`
6. Save changes

#### Step 2: Create Interactive Webhook Receiver

```python
# monitoring/slack-interactive-receiver.py
from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs

app = Flask(__name__)

ALERTMANAGER_URL = os.getenv('ALERTMANAGER_URL', 'http://alertmanager:9093')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

@app.route('/slack/interactive', methods=['POST'])
def handle_interaction():
    """Handle Slack button clicks"""
    
    # Parse Slack payload
    payload = json.loads(request.form.get('payload'))
    
    action = payload['actions'][0]
    action_name = action.get('name')
    action_value = action.get('value')
    user = payload['user']['name']
    
    # Parse alert details from action value
    alert_data = json.loads(action_value)
    
    if action_name == 'silence_1h':
        duration = '1h'
    elif action_name == 'silence_4h':
        duration = '4h'
    else:
        return jsonify({'text': 'Unknown action'}), 400
    
    # Create silence in Alertmanager
    silence_id = create_silence(
        alert_data['alertname'],
        alert_data['service'],
        duration,
        user
    )
    
    if silence_id:
        # Send confirmation to Slack
        message = f"✅ Alert silenced for {duration} by @{user}\n" \
                  f"Alert: {alert_data['alertname']}\n" \
                  f"Service: {alert_data['service']}\n" \
                  f"Silence ID: {silence_id[:8]}..."
        
        # Update original message
        return jsonify({
            'replace_original': False,
            'text': message
        })
    else:
        return jsonify({
            'text': '❌ Failed to create silence. Check Alertmanager logs.'
        }), 500

def create_silence(alertname, service, duration, creator):
    """Create silence in Alertmanager"""
    
    # Calculate end time
    hours = int(duration.rstrip('h'))
    start = datetime.utcnow()
    end = start + timedelta(hours=hours)
    
    # Build silence payload
    silence = {
        'matchers': [
            {'name': 'alertname', 'value': alertname, 'isRegex': False},
            {'name': 'service', 'value': service, 'isRegex': False}
        ],
        'startsAt': start.isoformat() + 'Z',
        'endsAt': end.isoformat() + 'Z',
        'createdBy': creator,
        'comment': f'Silenced from Slack for {duration}'
    }
    
    try:
        response = requests.post(
            f'{ALERTMANAGER_URL}/api/v2/silences',
            json=silence,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get('silenceID')
        
    except Exception as e:
        print(f"Error creating silence: {e}")
        return None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9095)
```

#### Step 3: Update Alertmanager Configuration

```yaml
# monitoring/alertmanager.yml - Interactive buttons
receivers:
  - name: slack_crm
    slack_configs:
      - channel: "#crm-events-alerts"
        api_url: "${SLACK_WEBHOOK_URL}"
        send_resolved: true
        
        # ... title and text (same as before)
        
        # ✅ Interactive action buttons
        actions:
          - type: button
            text: "🔕 Silence 1h"
            name: "silence_1h"
            value: '{"alertname":"{{ .GroupLabels.alertname }}","service":"{{ .CommonLabels.service }}"}'
          
          - type: button
            text: "🔕 Silence 4h"
            name: "silence_4h"
            value: '{"alertname":"{{ .GroupLabels.alertname }}","service":"{{ .CommonLabels.service }}"}'
          
          - type: button
            text: "📊 Dashboard"
            url: "http://localhost:3000/d/crm-events-pipeline"
          
          - type: button
            text: "🔍 Prometheus"
            url: "http://localhost:9090/alerts"
```

#### Step 4: Deploy Interactive Receiver

```yaml
# monitoring/docker-compose.yml
services:
  slack-interactive-receiver:
    build: ./slack-interactive-receiver
    container_name: aether-slack-interactive
    ports:
      - "9095:9095"
    environment:
      - ALERTMANAGER_URL=http://alertmanager:9093
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    restart: unless-stopped
    networks:
      - aether-monitoring
    depends_on:
      - alertmanager
```

#### Step 5: Create Dockerfile

```dockerfile
# monitoring/slack-interactive-receiver/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir flask requests

# Copy receiver script
COPY slack-interactive-receiver.py .

# Expose port
EXPOSE 9095

# Run receiver
CMD ["python", "slack-interactive-receiver.py"]
```

---

## 🎯 Recommended Approach: Hybrid Solution

**Best of both worlds**: URL buttons for dashboard links + Interactive buttons for silencing

```yaml
# monitoring/alertmanager.yml - Hybrid approach
receivers:
  - name: slack_crm
    slack_configs:
      - channel: "#crm-events-alerts"
        api_url: "${SLACK_WEBHOOK_URL}"
        send_resolved: true
        
        title: |-
          {{ if eq .Status "firing" }}🚨{{ else }}✅{{ end }} {{ .CommonLabels.service | default "CRM" }} Pipeline {{ if eq .Status "firing" }}Issues{{ else }}Resolved{{ end }}
        
        text: |-
          *Service*: {{ .CommonLabels.service | default "unknown" }}
          *Team*: {{ .CommonLabels.team | default "unknown" }}
          *Status*: {{ .Status | upper }}
          
          {{ range .Alerts -}}
          {{ if eq .Status "firing" }}🔥{{ else }}✅{{ end }} **{{ .Labels.alertname }}**
          {{ .Annotations.summary }}
          ---
          {{ end }}
          
          *Quick Actions*: Use buttons below ⬇️
        
        color: |-
          {{ if eq .Status "firing" }}warning{{ else }}good{{ end }}
        
        # Hybrid: URL buttons (no OAuth needed)
        actions:
          - type: button
            text: "📊 Dashboard"
            url: "http://localhost:3000/d/crm-events-pipeline"
            style: "primary"
          
          - type: button
            text: "🔍 Prometheus"
            url: "http://localhost:9090/alerts?search={{ .GroupLabels.alertname }}"
          
          - type: button
            text: "🔕 Silence"
            url: "http://localhost:9093/#/silences/new?filter=%7Bservice%3D%22{{ .CommonLabels.service }}%22%7D"
```

---

## 📊 Example Slack Message (With Buttons)

```
🚨 crm-events-sse Pipeline Issues (2 alerts)

Service: crm-events-sse
Team: crm
Status: FIRING

🔥 CrmEventsHotKeySkewHigh
Skew ratio exceeded 4x threshold
---
🔥 CrmEventsUnderReplicatedConsumers
Only 1 consumer active
---

Quick Actions: Use buttons below ⬇️

[📊 Dashboard] [🔍 Prometheus] [🔕 Silence]
    ↑               ↑               ↑
  Primary        Secondary      Silence UI
```

**Button Clicks**:
1. **Dashboard** → Opens Grafana in browser
2. **Prometheus** → Opens Prometheus alerts view
3. **Silence** → Opens Alertmanager silence form (pre-filled)

---

## 🧪 Testing

### Test URL Buttons

1. Trigger an alert (hot-key skew)
2. Wait for Slack message
3. Click **"📊 Dashboard"** button
4. Should open: `http://localhost:3000/d/crm-events-pipeline`

### Test Interactive Buttons (If Implemented)

1. Click **"🔕 Silence 1h"** button
2. Should see confirmation: "✅ Alert silenced for 1h by @yourname"
3. Verify in Alertmanager: `http://localhost:9093/#/silences`
4. Alert should be silenced with comment "Silenced from Slack for 1h"

---

## 🔒 Security Considerations

### URL Buttons (Simple)
- ✅ No secrets exposed (URLs are localhost)
- ⚠️ Requires VPN/internal network access
- ✅ No custom code to maintain

### Interactive Buttons (Advanced)
- ⚠️ Requires public endpoint for Slack webhooks
- ✅ Can validate Slack signatures (signing secret)
- ⚠️ Needs authentication layer for Alertmanager API

**Recommendation**: Use URL buttons for internal teams on VPN. Use interactive buttons only if you have public endpoint + proper auth.

---

## 📋 Comparison: URL vs Interactive

| Feature | URL Buttons | Interactive Buttons |
|---------|-------------|---------------------|
| **Setup Time** | 5 minutes | 30-60 minutes |
| **Slack App Type** | Incoming webhook | OAuth app |
| **Custom Code** | None | Flask receiver |
| **User Experience** | Opens browser | In-Slack action |
| **Network** | VPN required | Public webhook |
| **Maintenance** | Low | Medium |
| **Security** | Simple | Complex |

---

## 🎯 Recommendation: Start with URL Buttons

For **AetherLink's use case**, I recommend **URL Buttons** because:

1. ✅ **5-minute setup** (no custom code)
2. ✅ **No OAuth complexity** (incoming webhook sufficient)
3. ✅ **No public endpoint** needed (VPN access sufficient)
4. ✅ **Low maintenance** (Alertmanager native)
5. ✅ **Good UX** (one-click to dashboard/silence UI)

**Upgrade to Interactive later** if needed (when you have public endpoint + auth layer).

---

## 🚀 Quick Implementation (5 Minutes)

I'll update your alertmanager.yml with URL buttons now. This gives you one-click access to:
- 📊 Grafana Dashboard
- 🔍 Prometheus Alerts
- 🔕 Alertmanager Silence Form (pre-filled)

No custom receiver needed. Ready to proceed?
