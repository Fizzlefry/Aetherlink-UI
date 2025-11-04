# Quick Reference: CRM Events Visualization

> **Goal:** Add Grafana panels + Prometheus alert for CRM Events Sink metrics

## 🚀 TL;DR - Copy/Paste Commands

```powershell
# 1. Navigate to monitoring
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\monitoring

# 2. Edit files (use your editor or Copilot)
# - Add panels 20 & 21 to: grafana/dashboards/crm_events_pipeline.json
# - Add CrmEventsSinkDown alert to: prometheus-crm-events-rules.yml
# (See full runbook for JSON snippets)

# 3. Restart services
docker compose restart grafana prometheus

# 4. Generate test data
$tok = (irm -Method Post "http://localhost:8180/realms/aetherlink/protocol/openid-connect/token" -ContentType "application/x-www-form-urlencoded" -Body "grant_type=password&client_id=aetherlink-gateway&username=demo&password=demo").access_token
1..5 | % { $body = @{name="Test $_";email="test$_@x.com";source="test"}|ConvertTo-Json; irm "http://localhost/leads" -Method Post -Headers @{"Authorization"="Bearer $tok";"Host"="apexflow.aetherlink.local";"Content-Type"="application/json"} -Body $body | Out-Null }

# 5. Verify
docker logs aether-crm-events-sink --tail 10
curl http://localhost:9105/metrics | Select-String 'crm_events_ingested_total'

# 6. Open dashboard
Start-Process "http://localhost:3000/d/crm-events-pipeline"
```

## 📊 Panel Queries

**Panel 20 (Timeseries):**
```promql
sum by (topic) (rate(crm_events_ingested_total[5m]))
```

**Panel 21 (Table):**
```promql
topk(10, sum by (tenant_id) (rate(crm_events_ingested_total[5m])))
```

## 🚨 Alert Rule

```yaml
- alert: CrmEventsSinkDown
  expr: up{job="crm-events-sink"} == 0
  for: 2m
  labels:
    severity: warning
```

## ✅ Success Checklist

- [ ] Panel 20 shows lines for `apexflow.leads.created` and `apexflow.jobs.created`
- [ ] Panel 21 shows tenant "acme" with events/sec > 0
- [ ] Alert `CrmEventsSinkDown` visible in Prometheus (not firing)
- [ ] Sink logs show "Received lead.created for tenant acme"
- [ ] Metrics endpoint returns `crm_events_ingested_total{...} N.0`

## 🔗 Full Details

See: `RUNBOOK_CRM_EVENTS_VISUALIZATION.md`

## 📦 What This Adds

```
Before: ApexFlow → Kafka → Sink → Prometheus
After:  ApexFlow → Kafka → Sink → Prometheus → Grafana Dashboard
                                             ↘ Alertmanager (if down)
```

**Time to complete:** ~5 minutes  
**Dependencies:** CRM Events Sink running, Prometheus scraping `:9105`
