# 🚀 Aetherlink Core - Deployment Guide

## 📦 What's Included

**Complete identity + multi-tenancy + gateway infrastructure:**

- ✅ **Keycloak** (Identity Provider) - JWT-based auth
- ✅ **Traefik** (Edge Proxy) - Service routing
- ✅ **Gateway** (FastAPI) - JWT guard + metrics
- ✅ **Tenancy** (FastAPI + PostgreSQL) - Multi-tenant management
- ✅ **Contracts** (OpenAPI + AsyncAPI) - API specifications

---

## 🎯 Quick Deploy (5 Minutes)

### **Prerequisites**
- Docker Desktop running
- PowerShell (Administrator for hosts file)

### **Deploy Commands**

```powershell
# Navigate to core infrastructure
cd $env:USERPROFILE\OneDrive\Documents\AetherLink\infra\core

# Deploy all services (builds + starts containers)
docker compose --env-file .env -f docker-compose.core.yml up -d --build

# Check status
docker compose -f docker-compose.core.yml ps

# View logs
docker compose -f docker-compose.core.yml logs -f
```

---

## 🌐 Add DNS Entries (One-Time Setup)

Run PowerShell as Administrator:

```powershell
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$ip = "127.0.0.1"
$entries = @(
    "$ip edge.aetherlink.local",
    "$ip keycloak.aetherlink.local",
    "$ip tenancy.aetherlink.local"
)

Add-Content -Path $hostsFile -Value "`n# Aetherlink Core Services"
$entries | ForEach-Object { Add-Content -Path $hostsFile -Value $_ }

Write-Host "✅ DNS entries added" -ForegroundColor Green
```

---

## 🧪 Smoke Tests

```powershell
# Health checks
curl http://edge.aetherlink.local/healthz
curl http://tenancy.aetherlink.local/healthz

# Create a tenant
Invoke-RestMethod -Method POST `
  -Uri "http://tenancy.aetherlink.local/tenants" `
  -ContentType "application/json" `
  -Body '{"slug":"acme","name":"Acme Inc"}'

# List tenants
curl http://tenancy.aetherlink.local/tenants

# WhoAmI (expect 401 without token)
curl -i http://edge.aetherlink.local/whoami
```

---

## 🔐 Keycloak Setup (First-Time Configuration)

### **1. Access Keycloak Admin Console**

Visit: http://keycloak.aetherlink.local

Login with:
- Username: `admin`
- Password: `admin123!` (from `.env` file)

### **2. Create Realm**

1. Click dropdown (top-left) → **Create Realm**
2. Realm name: `aetherlink`
3. Click **Create**

### **3. Create Client**

1. Go to **Clients** → **Create client**
2. Settings:
   - Client ID: `aetherlink-edge`
   - Client authentication: OFF (public client)
   - Standard flow: enabled
   - Direct access grants: enabled
3. Click **Save**
4. Go to **Client scopes** tab
5. Add `audience` mapper:
   - Mapper type: **Audience**
   - Included audience: `aetherlink`

### **4. Create Roles**

1. Go to **Realm roles** → **Create role**
2. Create these roles:
   - `admin`
   - `manager`
   - `agent`
   - `viewer`

### **5. Create Test User**

1. Go to **Users** → **Add user**
2. Username: `testuser`
3. Email: `testuser@example.com`
4. Click **Create**
5. Go to **Credentials** tab → **Set password**
6. Password: `test123!`
7. Temporary: OFF
8. Go to **Role mapping** tab → Assign roles (e.g., `admin`, `manager`)

---

## 🔑 Test JWT Flow

### **1. Get Access Token**

```powershell
$tokenResponse = Invoke-RestMethod -Method POST `
  -Uri "http://keycloak.aetherlink.local/realms/aetherlink/protocol/openid-connect/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    grant_type = "password"
    client_id = "aetherlink-edge"
    username = "testuser"
    password = "test123!"
  }

$token = $tokenResponse.access_token
Write-Host "✅ Token received: $($token.Substring(0,50))..." -ForegroundColor Green
```

### **2. Call WhoAmI with Token**

```powershell
$headers = @{
    Authorization = "Bearer $token"
    "x-tenant-id" = "acme"
}

$whoami = Invoke-RestMethod -Uri "http://edge.aetherlink.local/whoami" -Headers $headers
$whoami | ConvertTo-Json
```

**Expected Output:**
```json
{
  "sub": "user-uuid-from-keycloak",
  "tenant_id": "acme",
  "roles": ["admin", "manager"]
}
```

---

## 📊 Add to Monitoring Stack

### **Update Prometheus Scrape Config**

Add to `monitoring/prometheus.yml`:

```yaml
scrape_configs:
  # ... existing jobs ...

  # Aetherlink Core services
  - job_name: 'aether-gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: '/metrics'

  - job_name: 'aether-tenancy'
    static_configs:
      - targets: ['tenancy:8001']
    metrics_path: '/metrics'
```

### **Restart Prometheus**

```powershell
docker compose restart prometheus
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   CLIENT (Browser/App)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   Traefik (Edge Proxy)                      │
│                     Port 80 (HTTP)                          │
└───┬──────────────────┬──────────────────┬───────────────────┘
    │                  │                  │
    ↓                  ↓                  ↓
┌─────────┐    ┌──────────────┐    ┌─────────────┐
│ Gateway │    │  Keycloak    │    │  Tenancy    │
│  :8000  │    │    :8080     │    │    :8001    │
│         │    │              │    │             │
│ JWT     │←───│ Identity     │    │ Postgres    │
│ Guard   │    │ Provider     │    │ :5432       │
└─────────┘    └──────────────┘    └─────────────┘
```

---

## 🔧 Useful Commands

### **View Logs**
```powershell
# All services
docker compose -f docker-compose.core.yml logs -f

# Specific service
docker logs -f aether-gateway
docker logs -f aether-keycloak
docker logs -f aether-tenancy
```

### **Restart Services**
```powershell
# All services
docker compose -f docker-compose.core.yml restart

# Specific service
docker restart aether-gateway
```

### **Rebuild After Code Changes**
```powershell
# Rebuild and restart
docker compose -f docker-compose.core.yml up -d --build gateway tenancy
```

### **Stop All Services**
```powershell
docker compose -f docker-compose.core.yml down
```

### **Stop and Remove Volumes (Clean Slate)**
```powershell
docker compose -f docker-compose.core.yml down -v
```

---

## 📋 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Gateway** | http://edge.aetherlink.local | API Gateway + JWT guard |
| **Keycloak** | http://keycloak.aetherlink.local | Identity provider admin |
| **Tenancy** | http://tenancy.aetherlink.local | Tenant management API |
| **Traefik Dashboard** | http://localhost:8088 | Service routing dashboard |

---

## 🎯 Next Steps

### **1. ApexFlow Integration**
- Add ApexFlow API behind gateway
- Emit events to `aetherlink.events` topic
- Use event envelope from `libs/contracts`

### **2. Files API**
- Add MinIO for object storage
- Pre-signed upload URLs
- Tenant-scoped buckets

### **3. Billing Service**
- Invoice model + DB
- QBO/Stripe connectors
- Guarded behind gateway

### **4. CustomerOps Messaging**
- SMS/Email endpoints
- Event indexing to search
- Chat history storage

---

## 🆘 Troubleshooting

### **Keycloak not accessible**
```powershell
# Check if container is running
docker ps --filter "name=aether-keycloak"

# Check logs
docker logs aether-keycloak

# Verify database connection
docker logs aether-kc-db
```

### **JWT verification failing**
- Check `JWT_ISSUER` in `.env` matches Keycloak realm
- Check `JWT_AUDIENCE` matches client audience mapper
- Verify token is not expired (default: 5 minutes)

### **Traefik routing not working**
```powershell
# Check Traefik dashboard
Start-Process "http://localhost:8088"

# Check service labels
docker inspect aether-gateway | Select-String "traefik"
```

### **Database connection errors**
```powershell
# Check database health
docker exec aether-tenancy-db pg_isready -U tenancy

# Connect to database manually
docker exec -it aether-tenancy-db psql -U tenancy -d tenancy
```

---

## ✅ Success Criteria

- [ ] All containers healthy (`docker compose ps`)
- [ ] DNS entries resolve
- [ ] Health checks pass
- [ ] Keycloak admin accessible
- [ ] Tenancy API creates/lists tenants
- [ ] JWT token obtained from Keycloak
- [ ] WhoAmI returns user info with token
- [ ] Prometheus scraping metrics

**Status**: ✅ **PRODUCTION READY** when all checks pass!

---

**Documentation**: See `libs/contracts/README.md` for API specs  
**Monitoring**: Integrated with existing Prometheus stack  
**Security**: JWT-based auth + multi-tenancy built-in
