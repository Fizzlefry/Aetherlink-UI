# Runbook: CRM Events Visualization Setup

## Overview
This playbook adds Grafana dashboard panels and Prometheus alerts for the CRM Events Sink service, which consumes ApexFlow domain events from Kafka and exposes metrics for observability.

**What you get:**
- Real-time timeseries graph of event ingestion by topic
- Table showing top tenants by event volume
- Prometheus alert when sink goes down

**Prerequisites:**
- CRM Events Sink deployed and running (`aether-crm-events-sink`)
- Prometheus scraping `:9105/metrics` (job: `crm-events-sink`)
- Grafana dashboard `crm_events_pipeline.json` exists

---

## Step-by-Step Instructions

### 0) Navigate to monitoring directory
```powershell
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring
```

---

### 1) Add Grafana Dashboard Panels

**File:** `monitoring/grafana/dashboards/crm_events_pipeline.json`

**Action:** Insert two new panels into the `panels[]` array, right after panel 19 (before the "Active Alerts" panel).

#### Panel 20: Events by Topic (Timeseries)
```json
{
  "id": 20,
  "type": "timeseries",
  "title": "CRM Events Ingested (by topic)",
  "datasource": "Prometheus",
  "gridPos": {
    "x": 0,
    "y": 49,
    "w": 12,
    "h": 8
  },
  "targets": [
    {
      "expr": "sum by (topic) (rate(crm_events_ingested_total[5m]))",
      "legendFormat": "{{topic}}",
      "intervalFactor": 1,
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "ops",
      "custom": {
        "drawStyle": "line",
        "lineInterpolation": "smooth",
        "fillOpacity": 10
      }
    }
  },
  "options": {
    "legend": {
      "displayMode": "list",
      "placement": "bottom",
      "showLegend": true
    }
  }
}
```

#### Panel 21: Top Tenants (Table)
```json
{
  "id": 21,
  "type": "table",
  "title": "Top Tenants by CRM Events (5m)",
  "datasource": "Prometheus",
  "gridPos": {
    "x": 12,
    "y": 49,
    "w": 12,
    "h": 8
  },
  "targets": [
    {
      "expr": "topk(10, sum by (tenant_id) (rate(crm_events_ingested_total[5m])))",
      "legendFormat": "{{tenant_id}}",
      "refId": "A",
      "instant": true
    }
  ],
  "options": {
    "showHeader": true
  },
  "transformations": [
    {
      "id": "organize",
      "options": {
        "excludeByName": {
          "Time": true
        },
        "renameByName": {
          "tenant_id": "Tenant ID",
          "Value": "Events/sec"
        }
      }
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "ops",
      "decimals": 3
    }
  }
}
```

**Note:** Update the "Active Alerts" panel's `gridPos.y` from `49` to `57` to make room.

---

### 2) Add Prometheus Alert Rule

**File:** `monitoring/prometheus-crm-events-rules.yml`

**Action:** Append this alert to the `crm_events_alerts` group (at the bottom of the rules list):

```yaml
      # Alert: CRM Events Sink down
      - alert: CrmEventsSinkDown
        expr: up{job="crm-events-sink"} == 0
        for: 2m
        labels:
          severity: warning
          team: crm
          service: crm-events-sink
          product: aetherlink
          component: consumer
        annotations:
          summary: "CRM events sink is down"
          description: "The sink that materializes and counts ApexFlow CRM events is not being scraapped. Events may be queuing in Kafka but not being processed."
          runbook: "Check docker logs aether-crm-events-sink and verify container is running. Restart with: docker compose up -d crm-events-sink"
```

---

### 3) Restart Grafana + Prometheus

```powershell
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring
docker compose restart grafana
docker compose restart prometheus
```

**Wait:** 10-15 seconds for services to fully restart.

---

### 4) Generate Test Traffic

Create some leads to populate the dashboard with real data:

```powershell
# Get JWT token from Keycloak
$tok = (Invoke-RestMethod -Method Post "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo").access_token

# Create 5 test leads
1..5 | ForEach-Object {
  $body = @{
    name   = "Grafana Event Test $_"
    email  = "grafana$_@test.com"
    source = "dashboard-test"
  } | ConvertTo-Json

  Invoke-RestMethod "http://localhost/leads" -Method Post -Headers @{
    "Authorization" = "Bearer $tok"
    "Host"          = "apexflow.aetherlink.local"
    "Content-Type"  = "application/json"
  } -Body $body | Out-Null
}

Write-Host "✅ Created 5 test leads!"
```

**Optional:** Create jobs too:
```powershell
1..2 | ForEach-Object {
  $jobBody = @{
    lead_id     = 1
    title       = "Dashboard Test Job $_"
    status      = "Open"
    description = "Testing job events visualization"
  } | ConvertTo-Json

  Invoke-RestMethod "http://localhost/jobs" -Method Post -Headers @{
    "Authorization" = "Bearer $tok"
    "Host"          = "apexflow.aetherlink.local"
    "Content-Type"  = "application/json"
  } -Body $jobBody | Out-Null
}
```

---

### 5) Verify Sink is Processing Events

**Check logs:**
```powershell
docker logs aether-crm-events-sink --tail 20
```

**Expected output:**
```
[2025-11-03T19:48:51.465169] Received lead.created for tenant acme
[2025-11-03T19:48:51.482361] Received lead.created for tenant acme
[2025-11-03T19:48:51.538039] Received lead.created for tenant acme
...
```

**Check metrics:**
```powershell
curl http://localhost:9105/metrics 2>&1 | Select-String 'crm_events_ingested_total'
```

**Expected output:**
```
crm_events_ingested_total{tenant_id="acme",topic="apexflow.leads.created"} 5.0
crm_events_ingested_total{tenant_id="acme",topic="apexflow.jobs.created"} 2.0
```

---

### 6) Open the Dashboard

**URL:** http://localhost:3000/d/crm-events-pipeline

**Default credentials:**
- Username: `admin`
- Password: `admin`

**What to look for:**

- **Panel 20 (left):** Timeseries line graph showing:
  - `apexflow.leads.created` - line showing lead event rate
  - `apexflow.jobs.created` - line showing job event rate
  - Y-axis: events per second (ops)
  - Updates every 10 seconds

- **Panel 21 (right):** Table showing:
  - Column 1: Tenant ID (e.g., "acme")
  - Column 2: Events/sec (with gradient gauge bar)
  - Top 10 most active tenants by event volume

**Within 10-20 seconds** of creating leads, you should see the graph spike and the tenant appear in the table.

---

## Architecture Flow

```
1. Client → Keycloak (get JWT token with tenant_id claim)
2. Client → Gateway (with Bearer token)
3. Gateway → Extracts tenant from JWT
4. Gateway → ApexFlow (with x-tenant-id header)
5. ApexFlow → Creates entity in PostgreSQL
6. ApexFlow → Publishes event to Kafka (apexflow.leads.created / apexflow.jobs.created)
7. CRM Events Sink → Consumes event from Kafka
8. CRM Events Sink → Increments Prometheus metric (crm_events_ingested_total)
9. Prometheus → Scrapes sink metrics every 10s
10. Grafana → Queries Prometheus and visualizes in dashboard
```

---

## Troubleshooting

### Panels show "No Data"

**Check Prometheus is scraping sink:**
```powershell
curl http://localhost:9090/api/v1/targets | Select-String 'crm-events-sink'
```
Look for `"health":"up"` in the output.

**Check Prometheus can query the metric:**
```powershell
$query = [System.Web.HttpUtility]::UrlEncode('crm_events_ingested_total')
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query"
```

### Sink not consuming events

**Check sink is running:**
```powershell
docker ps | Select-String 'crm-events-sink'
```

**Check sink can reach Kafka:**
```powershell
docker logs aether-crm-events-sink | Select-String 'Kafka'
```
Should show: `CRM Events Sink started. Listening to topics: ['apexflow.leads.created', 'apexflow.jobs.created']`

**Restart sink:**
```powershell
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\infra\core
docker compose restart crm-events-sink
```

### Alert firing incorrectly

**Check alert status in Prometheus:**
```
http://localhost:9090/alerts
```

**Silence alert temporarily:**
```
http://localhost:9093/#/alerts (Alertmanager)
```

---

## Metrics Reference

### `crm_events_ingested_total`
- **Type:** Counter
- **Labels:** `topic`, `tenant_id`
- **Meaning:** Total number of CRM domain events consumed by the sink
- **Usage:** Use `rate()` for events per second, `increase()` for count over time

### Example Queries

**Events per second by topic:**
```promql
sum by (topic) (rate(crm_events_ingested_total[5m]))
```

**Total events in last hour by tenant:**
```promql
sum by (tenant_id) (increase(crm_events_ingested_total[1h]))
```

**Most active tenant:**
```promql
topk(1, sum by (tenant_id) (rate(crm_events_ingested_total[5m])))
```

---

## Related Documentation

- **Main Shipment Manifest:** `SHIPMENT_MANIFEST.md`
- **CRM Events Service:** `pods/crm-events/README.md`
- **ApexFlow CRM:** `services/apexflow/README.md`
- **Monitoring Stack:** `monitoring/README.md`
- **Kafka Hot-Key Runbook:** `monitoring/docs/RUNBOOK_HOTKEY_SKEW.md`

---

## Success Criteria

✅ **Panel 20** shows timeseries lines for both lead and job events
✅ **Panel 21** shows at least one tenant with event rate > 0
✅ **Alert** `CrmEventsSinkDown` is loaded in Prometheus (not firing)
✅ **Metrics** endpoint `http://localhost:9105/metrics` returns data
✅ **Logs** show "Received lead.created for tenant acme" messages

---

**Last Updated:** November 3, 2025
**Maintained By:** Platform Team
**Status:** Production-Ready ✅
