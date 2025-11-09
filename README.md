# AetherLink ⚡

[![CI/CD](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/command-center-ci.yml/badge.svg)](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/command-center-ci.yml)
[![Monitoring](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/monitoring-smoke.yml/badge.svg)](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/monitoring-smoke.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-blue.svg)](https://kubernetes.io)

**Enterprise-grade Command Center for AI-driven operations, observability, and automation.**

AetherLink provides a unified platform for managing AI agents, monitoring system health, and orchestrating automated responses across distributed infrastructure. Built with FastAPI, React, and production-ready deployment patterns.

## � Recent Releases

### v0.2.0 - Phase XIV + XV: AccuLynx Integration & Enhanced Operations (November 2025)

**New Features:**
- **🔄 Real AccuLynx Integration**: Added production-ready AccuLynx API adapter with automatic stub/real mode switching based on API key configuration
- **⚡ Run-Now Endpoint**: New `/acculynx/run-now/{tenant}` endpoint for immediate import execution with UI integration
- **🔧 Configurable API Base**: Environment-driven API base URL configuration (`VITE_COMMAND_CENTER_URL`) for flexible deployments
- **📊 Enhanced Audit Logging**: Normalized operation names and enriched metadata for better observability
- **🏗️ DB Migration Prep**: Added PERSISTENCE-LAYER V1 markers throughout JSON storage for future database migration

**Technical Improvements:**
- **🔌 Async HTTP Client**: Integrated httpx for efficient AccuLynx API calls with proper timeout handling
- **🛡️ Backward Compatibility**: All existing endpoints, scheduler behavior, and JSON persistence maintained
- **📁 Modular Architecture**: Clean separation between stub and real API modes for development/production flexibility
- **🔍 Comprehensive Validation**: Both stub mode (no API key) and real mode (with API key) thoroughly tested

**Configuration:**
- New environment variables: `ACCULYNX_BASE_URL`, `ACCULYNX_API_KEY`, `ACCULYNX_TIMEOUT_SEC`
- UI configuration via `VITE_COMMAND_CENTER_URL` for multi-environment support

**Breaking Changes:** None - Full backward compatibility maintained

---

## �🚀 Quick Start (5 minutes)

### Option 1: Docker Compose (Development)
```bash
# Clone and start services
git clone https://github.com/YOUR_ORG_OR_USER/AetherLink.git
cd AetherLink
docker compose -f deploy/docker-compose.dev.yml up -d

# Access Command Center
open http://localhost:8010
```

### Option 2: Kubernetes + Helm (Production)
```bash
# Add Helm repo and install
helm install command-center ./helm/command-center \
  --set image.tag=latest \
  --set ingress.enabled=true

# Get service URL
kubectl get svc command-center
```

### Option 3: Local Development
```powershell
# Setup environment
.\dev_setup.ps1 -Watch

# Health check
.\makefile.ps1 health

# Access UI
open http://localhost:5173
```

### Option 4: Vertical Apps Suite (Docker)
```bash
# Start all vertical apps + UI dashboard
docker compose up -d

# Services available at:
# - PeakPro CRM: http://localhost:8021
# - RoofWonder: http://localhost:8022
# - PolicyPal AI: http://localhost:8023
# - Media Service: http://localhost:9109
# - UI Dashboard: http://localhost:5174
```

**Environment Configuration:**
- Shared config in `env/` directory
- Service-specific database paths
- Unified APP_KEY across all services
- Ready for multi-tenant API keys (next step)

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Documentation Hub](#-documentation-hub)
- [API Reference](#-api-reference)
- [Deployment](#-deployment)
- [Development](#-development)
- [Monitoring & Observability](#-monitoring--observability)
- [Testing](#-testing)
- [Contributing](#-contributing)

## 🎯 Overview

AetherLink Command Center is a comprehensive operations platform that provides:

- **Real-time Monitoring**: Live dashboards with Server-Sent Events
- **RBAC Security**: Role-based access control (Admin, Operator, Manager)
- **Event Streaming**: Real-time event processing and alerting
- **Auto-Healing**: Automated incident response and remediation
- **Multi-tenant Support**: Isolated operations per tenant
- **Production Deployment**: Docker, Kubernetes, and Helm-ready

### Key Components

- **Command Center API** (`services/command-center/`): FastAPI backend with observability
- **Operator Dashboard** (`services/ui/`): React frontend with real-time updates
- **Event Store**: SQLite-based event persistence with retention
- **Monitoring Stack**: Prometheus + Grafana dashboards
- **CI/CD Pipeline**: GitHub Actions with automated testing

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Operator UI   │    │ Command Center  │    │   Event Store   │
│    (React)      │◄──►│    (FastAPI)    │◄──►│    (SQLite)     │
│                 │    │                 │    │                 │
│ - Dashboards    │    │ - REST API      │    │ - 7-day retention│
│ - Real-time SSE │    │ - RBAC Auth     │    │ - Per-tenant    │
│ - Filter/Persist│    │ - Metrics       │    │ - Auto-cleanup  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │   Monitoring    │
                    │ (Prometheus +   │
                    │    Grafana)     │
                    └─────────────────┘
```

## ✨ Features

### Core Capabilities
- **🔐 RBAC Security**: Admin/Operator/Manager roles with header-based auth
- **📊 Real-time Dashboards**: Live operator interfaces with persistent filters
- **⚡ Event Streaming**: Server-Sent Events for instant updates
- **🔄 Auto-Healing**: Automated incident response workflows
- **🏢 Multi-tenant**: Isolated operations and data per tenant
- **📈 Observability**: Prometheus metrics and Grafana dashboards

### Production Ready
- **🐳 Containerized**: Multi-stage Docker builds with health checks
- **☸️ Kubernetes**: Helm charts with resource limits and probes
- **🔄 CI/CD**: GitHub Actions with automated testing
- **🧪 End-to-End Tests**: API + UI testing with pytest + Playwright
- **📝 Structured Logging**: JSON logs for log aggregation
- **🏥 Health Checks**: Kubernetes-ready health endpoints

## 📚 Documentation Hub

### 📖 Core Documentation
- **[Command Center Ops Runbook](docs/COMMAND_CENTER_OPS_RUNBOOK.md)** - Complete operations guide
- **[Quick Start Guide](docs/COMMAND_CENTER_QUICKSTART.md)** - 5-minute setup checklist
- **[API Developer Guide](docs/COMMAND_CENTER_API_GUIDE.md)** - Endpoint reference and examples

### 🔧 Service Documentation
- **[Command Center API](services/command-center/README.md)** - Backend service details
- **[Operator Dashboard](services/ui/README.md)** - Frontend application guide
- **[Monitoring & Observability](observability/README.md)** - Metrics and dashboards

### 🚀 Deployment Guides
- **[Docker Deployment](deploy/README.md)** - Container setup and configuration
- **[Kubernetes + Helm](helm/command-center/README.md)** - Production deployment
- **[CI/CD Pipeline](.github/workflows/command-center-ci.yml)** - Build and release automation

### 📈 Development Phases
- **[Phase XIII: Persistent State - Complete](docs/PHASE_XIII_COMPLETE_SUMMARY.md)** - Command Center v1.0 (Local Edition)
- **[Phase XIV: Operational Actions & Hardening](docs/PHASE_XIV_ROADMAP.md)** - Next phase roadmap

## 🔌 API Reference

### Core Endpoints
```bash
# Health & Discovery
GET  /ops/health       # System health status
GET  /ops/ping         # Simple ping check
GET  /ops/db           # Database connectivity check
GET  /healthz          # Kubernetes health check
GET  /meta             # Feature discovery
GET  /metrics          # Prometheus metrics

# Phase XIV + XV: AccuLynx Integration
POST /api/crm/import/acculynx/run-now           # Immediate import execution
GET  /api/crm/import/acculynx/schedule/status   # Scheduler status
POST /api/crm/import/acculynx/schedule          # Create/update schedule
DELETE /api/crm/import/acculynx/schedule        # Remove schedule
GET  /api/crm/import/acculynx/audit             # Import audit log

# Local Actions (Phase XIV)
POST /api/local/run     # Execute local actions
GET  /api/local/runs    # Local action history

# Alert Management
GET  /alerts/deliveries/history  # Delivery history with filters
POST /alerts/deliveries/{id}/replay  # Replay failed deliveries

# Auto-Healing
GET  /autoheal/rules   # View healing rules
POST /autoheal/clear_endpoint_cooldown  # Clear cooldowns

# Real-time Events
GET  /bus/events       # Event stream
GET  /analytics/audit  # Audit history
GET  /analytics/events/summary  # Event analytics
```

### Authentication
All endpoints require RBAC headers:
```
X-User-Roles: admin,operator
```

## 🚀 Deployment

### Production Deployment Options

#### Docker Compose (Simple)
```bash
docker compose -f deploy/docker-compose.prod.yml up -d
```

#### Kubernetes + Helm (Recommended)
```bash
# Install Command Center
helm install command-center ./helm/command-center \
  --set image.tag=v1.0.0 \
  --set ingress.enabled=true \
  --set ingress.host=command-center.yourdomain.com

# Install Monitoring Stack
helm install monitoring ./helm/monitoring
```

#### Cloud Platforms
- **AWS EKS**: Use provided Helm charts with ALB ingress
- **Google GKE**: Compatible with GKE ingress and Cloud Monitoring
- **Azure AKS**: Works with AGIC and Azure Monitor

### Configuration
```yaml
# values.yaml
image:
  tag: "latest"
ingress:
  enabled: true
  host: command-center.yourdomain.com
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

## 💻 Development

### Prerequisites
- Docker / Docker Compose
- Python 3.11+
- Node.js 18+ (for UI development)
- kubectl + Helm (for K8s development)

### Local Development Setup

```powershell
# Clone repository
git clone https://github.com/YOUR_ORG_OR_USER/AetherLink.git
cd AetherLink

# Start full development stack
.\dev_setup.ps1 -Watch

# Run tests
.\.venv\Scripts\python.exe -m pytest

# Access services
# Command Center API: http://localhost:8010
# Operator Dashboard: http://localhost:5173
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

### Development Scripts

```powershell
# Health checks
.\makefile.ps1 health

# Database operations
.\dev_migrate.ps1 -Seed    # Apply migrations + seed data
.\dev_reset_db.ps1         # Reset database

# Logs and monitoring
.\dev_logs.ps1             # Live service logs
.\dev_stop.ps1             # Stop all services
```

### Code Quality

```powershell
# Pre-commit checks
pre-commit run --all-files

# Type checking
mypy .

# Linting & formatting
ruff check .
ruff format .
```

## 📊 Monitoring & Observability

### Metrics Dashboard
Access Grafana at `http://localhost:3000` (admin/admin) to view:
- API request rates and latency
- Event processing throughput
- Error rates and system health
- Auto-healing success rates

### Key Metrics
- `command_center_uptime_seconds`: Service uptime
- `command_center_health`: Service health status (1=healthy, 0=unhealthy)
- `command_center_api_requests_total`: API request counts by endpoint
- `command_center_events_total`: Events processed by type

### Logging
All services emit structured JSON logs to stdout, compatible with:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Loki + Grafana
- CloudWatch Logs
- Datadog

## 🧪 Testing

### Test Coverage
- **API Tests**: pytest-based backend validation (9 test functions)
- **UI Tests**: Playwright-based frontend testing (10 test scenarios)
- **Integration Tests**: End-to-end service validation
- **Health Checks**: Automated monitoring validation

### Running Tests

```bash
# API Tests
cd services/command-center
python -m pytest tests/ -v

# UI Tests
cd services/ui
npm run test

# Full Test Suite (CI)
# Runs automatically on push/PR via GitHub Actions
```

### Test Categories
- Health checks and service discovery
- RBAC authentication and authorization
- Real-time event streaming
- Data persistence and filtering
- UI interactions and state management
- Cross-browser compatibility

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and add tests
4. Run full test suite (`make test`)
5. Submit a pull request

### Code Standards
- **Python**: Black formatting, mypy type checking, ruff linting
- **TypeScript**: ESLint, Prettier formatting
- **Documentation**: Clear, concise, and up-to-date
- **Testing**: 80%+ coverage, integration tests for new features

### Commit Convention
```
feat: add new dashboard filter
fix: resolve SSE connection issue
docs: update API reference
test: add RBAC validation tests
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support

- **Documentation**: See [Documentation Hub](#-documentation-hub) above
- **Issues**: [GitHub Issues](https://github.com/YOUR_ORG_OR_USER/AetherLink/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_ORG_OR_USER/AetherLink/discussions)

---
