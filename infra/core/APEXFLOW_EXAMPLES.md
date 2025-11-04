# 📘 ApexFlow CRM - API Examples

Complete examples for using the ApexFlow CRM v1 API.

---

## 🔑 Authentication

All endpoints (except `/healthz`, `/readyz`, `/metrics`) require:
- **Header**: `x-tenant-id` (your tenant identifier)
- **JWT** (in production): `Authorization: Bearer <token>`

For MVP testing, JWT is optional (Gateway validates, ApexFlow trusts Gateway).

---

## 🚀 Quick Start Examples

### **1. Create a Lead**

```powershell
$leadPayload = @{
    name = "John Roof"
    source = "Inbound"
    phone = "763-280-1272"
    email = "john@roofing.com"
    notes = "Interested in roof replacement"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body $leadPayload
```

**Expected Response:**
```json
{
  "ok": true,
  "lead": {
    "id": 1,
    "tenant": "acme",
    "name": "John Roof",
    "source": "Inbound",
    "phone": "763-280-1272",
    "email": "john@roofing.com",
    "notes": "Interested in roof replacement"
  }
}
```

---

### **2. List All Leads**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Method Get `
    -Headers @{"x-tenant-id" = "acme"}
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "tenant": "acme",
    "name": "John Roof",
    "source": "Inbound",
    "phone": "763-280-1272",
    "email": "john@roofing.com"
  }
]
```

---

### **3. Get Specific Lead**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads/1" `
    -Method Get `
    -Headers @{"x-tenant-id" = "acme"}
```

---

### **4. Create a Job (from Lead)**

```powershell
$jobPayload = @{
    lead_id = 1
    title = "Roof Replacement - John Roof"
    status = "Scheduled"
    description = "Full tear-off and shingle replacement"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/jobs" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body $jobPayload
```

**Expected Response:**
```json
{
  "ok": true,
  "job": {
    "id": 1,
    "tenant": "acme",
    "lead_id": 1,
    "title": "Roof Replacement - John Roof",
    "status": "Scheduled",
    "description": "Full tear-off and shingle replacement"
  }
}
```

---

### **5. List All Jobs**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/jobs" `
    -Method Get `
    -Headers @{"x-tenant-id" = "acme"}
```

---

### **6. Create an Appointment**

```powershell
$apptPayload = @{
    job_id = 1
    scheduled_at = "2025-11-05T10:00:00Z"
    type = "Inspection"
    notes = "Initial roof assessment"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/appointments" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body $apptPayload
```

**Expected Response:**
```json
{
  "ok": true,
  "appointment": {
    "id": 1,
    "tenant": "acme",
    "job_id": 1,
    "scheduled_at": "2025-11-05T10:00:00Z",
    "type": "Inspection",
    "notes": "Initial roof assessment"
  }
}
```

---

### **7. List All Appointments**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/appointments" `
    -Method Get `
    -Headers @{"x-tenant-id" = "acme"}
```

---

## 🧪 Multi-Tenant Testing

### **Create Data for Multiple Tenants**

```powershell
# Tenant: acme
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body '{"name":"John Acme","source":"Website"}'

# Tenant: beta-corp
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "beta-corp"} `
    -Body '{"name":"Jane Beta","source":"Referral"}'

# List leads for each tenant
Write-Host "Acme leads:"
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Headers @{"x-tenant-id" = "acme"}

Write-Host "`nBeta Corp leads:"
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Headers @{"x-tenant-id" = "beta-corp"}
```

**Result**: Each tenant sees only their own data (tenant isolation verified).

---

## 📊 Metrics

### **Check Prometheus Metrics**

```powershell
# Get raw metrics
Invoke-WebRequest -Uri "http://apexflow.aetherlink.local/metrics" -UseBasicParsing

# Parse specific metric
$metrics = Invoke-WebRequest -Uri "http://apexflow.aetherlink.local/metrics" -UseBasicParsing
$metrics.Content -split "`n" | Select-String "apexflow_requests_total"
```

**Example Metrics:**
```
apexflow_requests_total{method="POST",path="/leads",tenant="acme"} 5.0
apexflow_requests_total{method="GET",path="/leads",tenant="acme"} 12.0
apexflow_requests_total{method="POST",path="/jobs",tenant="acme"} 3.0
```

---

## 🔧 Error Handling

### **Missing Tenant Header**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" -Method Get
```

**Response:**
```json
{
  "detail": "x-tenant-id header required"
}
```
**Status**: 400 Bad Request

---

### **Lead Not Found**

```powershell
Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads/999" `
    -Headers @{"x-tenant-id" = "acme"}
```

**Response:**
```json
{
  "detail": "Lead not found"
}
```
**Status**: 404 Not Found

---

## 🧩 Complete Workflow Example

### **Lead → Job → Appointment Pipeline**

```powershell
# Step 1: Create lead
$lead = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body '{"name":"Sarah Window","source":"Google Ads","phone":"555-1234"}'

$leadId = $lead.lead.id
Write-Host "✅ Lead created: ID $leadId"

# Step 2: Create job
$job = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/jobs" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body (@{lead_id=$leadId; title="Window Replacement"; status="Pending"} | ConvertTo-Json)

$jobId = $job.job.id
Write-Host "✅ Job created: ID $jobId"

# Step 3: Schedule appointment
$appt = Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/appointments" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{"x-tenant-id" = "acme"} `
    -Body (@{job_id=$jobId; scheduled_at="2025-11-06T14:00:00Z"; type="Consultation"} | ConvertTo-Json)

$apptId = $appt.appointment.id
Write-Host "✅ Appointment created: ID $apptId"

# Step 4: Retrieve full pipeline
Write-Host "`n📊 Complete Pipeline:"
Write-Host "Lead: $(Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/leads/$leadId" -Headers @{"x-tenant-id"="acme"} | ConvertTo-Json -Compress)"
Write-Host "Job: $(Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/jobs/$jobId" -Headers @{"x-tenant-id"="acme"} | ConvertTo-Json -Compress)"
Write-Host "Appointment: $(Invoke-RestMethod -Uri "http://apexflow.aetherlink.local/appointments/$apptId" -Headers @{"x-tenant-id"="acme"} | ConvertTo-Json -Compress)"
```

---

## 🔗 Related Docs

- **Deployment**: `infra/core/README.md`
- **API Contract**: `libs/contracts/openapi/apexflow-v1.yaml` (future)
- **Monitoring**: Grafana at http://grafana.aetherlink.local

---

**Status**: MVP (In-Memory Storage)  
**Next Upgrade**: PostgreSQL models + Alembic migrations → say "**DB me**"
