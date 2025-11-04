# 🚀 Aetherlink Services - Upgrade Zone

This directory contains all Aetherlink microservices that power the complete platform.

## 📦 Core Services (Active)

### **Gateway** (`gateway/`)
- **Purpose**: Edge API with JWT authentication
- **Port**: 8000
- **URL**: http://edge.aetherlink.local
- **Features**: JWT guard, tenant routing, Prometheus metrics
- **Status**: ✅ **ONLINE**

### **Tenancy** (`tenancy/`)
- **Purpose**: Multi-tenant management service
- **Port**: 8001
- **URL**: http://tenancy.aetherlink.local
- **Features**: Tenant CRUD, PostgreSQL backend
- **Status**: ✅ **ONLINE**

---

## 🧩 Business Services (Deployment Ready)

### **ApexFlow CRM** (`apexflow/`)
- **Purpose**: Lead → Job → Appointment lifecycle management
- **Port**: 8080
- **URL**: http://apexflow.aetherlink.local
- **Entities**: Leads, Jobs, Appointments
- **Features**:
  - Tenant-scoped data isolation
  - JWT authentication required
  - Event emission to `aetherlink.events`
  - Prometheus metrics
- **Status**: 🔄 **DEPLOYING**

### **Billing** (`billing/`) - *Future*
- **Purpose**: Invoice management + payment processing
- **Integrations**: QuickBooks Online, Stripe
- **Features**: Invoice CRUD, payment webhooks, QBO sync
- **Status**: ⏳ **STAGED**

### **Files** (`files/`) - *Future*
- **Purpose**: Document storage and pre-signed uploads
- **Backend**: MinIO (S3-compatible)
- **Features**: Tenant-scoped buckets, pre-signed URLs, CDN integration
- **Status**: ⏳ **STAGED**

### **CustomerOps** (`customer_ops/`) - *Future*
- **Purpose**: Messaging hub (SMS, Email, Chat)
- **Features**: Message history, AI chat, event indexing
- **Status**: ⏳ **STAGED**

### **Insights** (`insights/`) - *Future*
- **Purpose**: Analytics and business intelligence
- **Features**: Custom dashboards, KPI tracking, report generation
- **Status**: ⏳ **STAGED**

---

## 🏗️ Architecture Principles

All services follow the **Aetherlink Service Standard**:

1. **Multi-Tenancy**: Every request requires `x-tenant-id` header
2. **Authentication**: JWT validation via Keycloak
3. **Observability**: `/healthz`, `/readyz`, `/metrics` endpoints
4. **Event-Driven**: Emit events to Kafka (`aetherlink.events`)
5. **Contract-First**: OpenAPI specs in `libs/contracts/`
6. **Traefik Routing**: Auto-discovered via Docker labels

---

## 🚦 Service Status Legend

- ✅ **ONLINE**: Deployed and serving traffic
- 🔄 **DEPLOYING**: Build in progress
- ⏳ **STAGED**: Code ready, awaiting deployment
- 📝 **PLANNED**: Requirements defined, not implemented
- 🔧 **MAINTENANCE**: Temporarily offline for updates

---

## 📊 Monitoring

All services are automatically scraped by Prometheus:
- **Job**: `aether-core` (Gateway, Tenancy)
- **Job**: `apexflow` (ApexFlow CRM)
- **Grafana**: Dashboards auto-provision on startup

---

## 🔗 Related Documentation

- **Core Infrastructure**: `infra/core/README.md`
- **API Contracts**: `libs/contracts/README.md`
- **Monitoring Stack**: `monitoring/README.md`
- **Deployment Guide**: `infra/core/README.md`

---

**Last Updated**: November 3, 2025
**Platform Version**: v1.0 (Core + ApexFlow MVP)
