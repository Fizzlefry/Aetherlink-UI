# ✅ Post-Deployment Checklist - Phase 2

## 🎯 Immediate Actions

### 1. **Rebuild ApexFlow** (Fix healthcheck)
The Dockerfile was updated to include `curl` for health checks.

```powershell
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\infra\core
docker compose --env-file .env -f docker-compose.core.yml up -d --build apexflow
```

**Expected**: Container will now pass health checks

---

### 2. **Add DNS Entry for ApexFlow**
Required to access via `apexflow.aetherlink.local` (Traefik routing).

```powershell
# Option A: Run as Administrator
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1 apexflow.aetherlink.local"

# Option B: Manual edit (Notepad as Admin)
# C:\Windows\System32\drivers\etc\hosts
# Add line: 127.0.0.1 apexflow.aetherlink.local
```

**Test**:
```powershell
curl http://apexflow.aetherlink.local/healthz
```

---

### 3. **Restart Prometheus** (Enable metrics scraping)
Prometheus needs to reload config to scrape ApexFlow.

```powershell
cd monitoring
docker compose restart prometheus

# Verify targets
Start-Process "http://localhost:9090/targets"
# Look for: "apexflow" job with state=UP
```

---

## 🧪 Smoke Tests

### Test 1: Direct Port Access (No DNS required)

```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8080/healthz"
# Expected: "ok"

# Create lead
$body = @{
    name = "Sarah Window"
    source = "Google Ads"
    phone = "555-1234"
    email = "sarah@example.com"
} | ConvertTo-Json

$lead = Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body $body

Write-Host "✅ Lead created: ID $($lead.lead.id)"

# List leads
$leads = Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Headers @{"x-tenant-id" = "acme"}

Write-Host "✅ Found $($leads.Count) lead(s)"
```

---

### Test 2: Multi-Tenant Isolation

```powershell
# Create lead for tenant "acme"
Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body '{"name":"John Acme","source":"Website"}'

# Create lead for tenant "beta-corp"
Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "beta-corp"} `
    -Body '{"name":"Jane Beta","source":"Referral"}'

# Verify isolation - each tenant sees only their data
$acmeLeads = Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Headers @{"x-tenant-id" = "acme"}

$betaLeads = Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Headers @{"x-tenant-id" = "beta-corp"}

Write-Host "Acme leads: $($acmeLeads.Count)" # Should be 1
Write-Host "Beta leads: $($betaLeads.Count)" # Should be 1
```

---

### Test 3: Complete Workflow (Lead → Job → Appointment)

```powershell
# Step 1: Create lead
$lead = Invoke-RestMethod -Uri "http://localhost:8080/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body '{"name":"Mike Roof","source":"Inbound","phone":"763-280-1272"}'

$leadId = $lead.lead.id
Write-Host "✅ Lead created: ID $leadId"

# Step 2: Create job
$job = Invoke-RestMethod -Uri "http://localhost:8080/jobs" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body (@{lead_id=$leadId; title="Roof Replacement"; status="Pending"} | ConvertTo-Json)

$jobId = $job.job.id
Write-Host "✅ Job created: ID $jobId"

# Step 3: Schedule appointment
$appt = Invoke-RestMethod -Uri "http://localhost:8080/appointments" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body (@{job_id=$jobId; scheduled_at="2025-11-06T10:00:00Z"; type="Inspection"} | ConvertTo-Json)

$apptId = $appt.appointment.id
Write-Host "✅ Appointment created: ID $apptId"

# Verify complete pipeline
Write-Host "`n📊 Complete Pipeline:"
Invoke-RestMethod -Uri "http://localhost:8080/leads/$leadId" -Headers @{"x-tenant-id"="acme"} | Format-List
Invoke-RestMethod -Uri "http://localhost:8080/jobs/$jobId" -Headers @{"x-tenant-id"="acme"} | Format-List
Invoke-RestMethod -Uri "http://localhost:8080/appointments/$apptId" -Headers @{"x-tenant-id"="acme"} | Format-List
```

---

### Test 4: Metrics Endpoint

```powershell
# Check Prometheus metrics
$metrics = Invoke-WebRequest -Uri "http://localhost:8080/metrics" -UseBasicParsing
$metrics.Content -split "`n" | Select-String "apexflow_requests_total"

# Expected output (example):
# apexflow_requests_total{path="/leads",method="POST",tenant="acme"} 5.0
# apexflow_requests_total{path="/leads",method="GET",tenant="acme"} 3.0
```

---

### Test 5: Error Handling

```powershell
# Test missing tenant header
try {
    Invoke-RestMethod -Uri "http://localhost:8080/leads"
} catch {
    Write-Host "✅ Expected 400: x-tenant-id header required"
}

# Test non-existent lead
try {
    Invoke-RestMethod -Uri "http://localhost:8080/leads/999" `
        -Headers @{"x-tenant-id" = "acme"}
} catch {
    Write-Host "✅ Expected 404: Lead not found"
}
```

---

## 📊 Monitoring Validation

### Check Prometheus Scrape Status

```powershell
# Open Prometheus targets page
Start-Process "http://localhost:9090/targets"

# Verify all jobs are UP:
# ✅ aether-core (gateway:8000, tenancy:8001)
# ✅ apexflow (apexflow:8080)
```

### Query Metrics

```powershell
# Open Prometheus query interface
Start-Process "http://localhost:9090/graph"

# Run these queries:
# 1. Request rate by tenant:
#    rate(apexflow_requests_total[5m])
#
# 2. Total requests by path:
#    sum by (path) (apexflow_requests_total)
#
# 3. Tenant activity:
#    sum by (tenant) (apexflow_requests_total)
```

---

## 🔧 Troubleshooting Commands

### Container Issues

```powershell
# Check all Aetherlink containers
docker ps --filter "name=aether-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View ApexFlow logs
docker logs -f aether-apexflow

# Restart ApexFlow
docker restart aether-apexflow

# Force rebuild
cd infra/core
docker compose --env-file .env -f docker-compose.core.yml up -d --build --force-recreate apexflow
```

### Database Issues

```powershell
# Check database health
docker logs aether-apexflow-db

# Connect to database
docker exec -it aether-apexflow-db psql -U postgres -d apexflow

# Inside psql:
# \dt           # List tables (none yet - in-memory MVP)
# \q            # Quit
```

### Network Issues

```powershell
# Check Docker network
docker network inspect aether-core_aether

# Test connectivity from ApexFlow to database
docker exec aether-apexflow ping -c 2 db-apexflow

# Test connectivity from Gateway
docker exec aether-gateway ping -c 2 apexflow
```

### Traefik Routing Issues

```powershell
# Check Traefik dashboard
Start-Process "http://localhost:8088/dashboard/"

# Verify ApexFlow is registered
# Look for "apexflow@docker" router with rule Host(`apexflow.aetherlink.local`)

# Check labels on container
docker inspect aether-apexflow --format '{{range $key, $value := .Config.Labels}}{{$key}}: {{$value}}{{"\n"}}{{end}}' | Select-String "traefik"
```

---

## ✅ Success Criteria

Mark each as complete:

- [ ] ApexFlow container healthy (not "unhealthy" status)
- [ ] DNS entry added for apexflow.aetherlink.local
- [ ] Prometheus scraping ApexFlow metrics
- [ ] Health check returns "ok"
- [ ] Can create leads via POST /leads
- [ ] Can list leads via GET /leads
- [ ] Multi-tenant isolation works (acme vs beta-corp)
- [ ] Complete workflow works (Lead → Job → Appointment)
- [ ] Metrics visible in Prometheus
- [ ] Traefik routing configured

---

## 📋 Phase 2 Complete When...

**All of the following are true**:

1. ✅ All 8 containers running
2. ✅ ApexFlow passes health checks
3. ✅ Smoke tests pass
4. ✅ Prometheus scraping metrics
5. ✅ DNS entry working (or direct port access confirmed)
6. ✅ Documentation reviewed

---

## 🚀 Ready for Phase 3?

Once all checks pass, choose your next move:

### **Option A: Database Persistence** → Say "**DB me**"
- PostgreSQL models with SQLAlchemy
- Alembic migrations
- Foreign key relationships
- Persistent storage

### **Option B: Event-Driven Architecture** → Say "**Ship events**"
- Kafka producer integration
- LeadCreated, JobCreated events
- AsyncAPI envelope pattern
- Event-driven workflows

### **Option C: CRM Analytics** → Say "**Add dashboard**"
- Grafana dashboard panels
- Conversion metrics
- Pipeline visualization
- Tenant activity tracking

### **Option D: Next Service** → Say "**Deploy billing**" (or files, customer_ops, etc.)
- Invoice management
- QBO/Stripe integration
- Payment webhooks
- Billing dashboard

---

**Status**: Phase 2 operational, awaiting final validations
**Next**: Complete checklist → Choose Phase 3 direction
