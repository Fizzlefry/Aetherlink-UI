# AetherLink Release History

## Overview

AetherLink's evolution from basic CRM backend to production-ready, self-healing ops platform.

---

## Phase I: Foundation (v1.0.0 - v1.1.0)

### v1.0.0 - Backend Validation
**Released:** November 2025  
**Focus:** Core CRM functionality

**Features:**
- Customer Ops API (FastAPI)
- PostgreSQL with pgvector
- Redis queue
- MinIO object storage
- Lead management CRUD
- Activity tracking
- AI Summarization service
- Notification consumer
- Worker pod with metrics

**Validation:**
- End-to-end backend tests
- Docker Compose deployment
- Health check endpoints
- Grafana + Prometheus monitoring

### v1.1.0 - UI Auth Resilience
**Released:** November 2025  
**Focus:** Frontend authentication

**Features:**
- React UI with Keycloak integration
- Test mode (bypass auth for local dev)
- Auth token refresh
- Graceful auth failure handling
- Environment-based config

**Testing:**
- Playwright E2E tests
- Auth flow validation
- Test mode verification

---

## Phase II: Operational Intelligence (v1.2.0 - v1.5.0)

### v1.2.0 - M1: Command Center
**Released:** November 2025  
**Focus:** Real-time ops dashboard

**Features:**
- FastAPI service on port 8010
- `/ops/health` - Aggregate service health
- `/ops/ping` - Quick health check
- React CommandCenter component
- Auto-refresh (15s intervals)
- Tab navigation integration

**Services Monitored:**
- UI health
- AI Summarizer
- Notifications Consumer
- ApexFlow
- Kafka

**Testing:** 3 Playwright tests

### v1.3.0 - M2: AI Orchestrator
**Released:** November 2025  
**Focus:** Intelligent AI routing layer

**Features:**
- FastAPI service on port 8011
- Intent-based routing
- `/orchestrate` - Smart dispatch endpoint
- Latency tracking
- Grafana annotation hooks (optional)

**Supported Intents:**
- `extract-lead` → AI Summarizer
- `summarize-activity` → AI Summarizer

**Architecture:**
- Provider-agnostic design
- Extensible for multiple AI backends
- Request/response validation

**Testing:** 4 Playwright tests

### v1.4.0 - M3: RBAC
**Released:** November 2025  
**Focus:** Role-based access control

**Features:**
- Header-based authentication (`X-User-Roles`)
- FastAPI dependency injection
- Shared RBAC module

**Role Hierarchy:**
- `admin` - Full access
- `operator` - Ops endpoints only
- `agent` - CRM + AI features
- `viewer` - Read-only

**Protected Endpoints:**
- Command Center `/ops/health` → operator/admin
- AI Orchestrator `/orchestrate` → agent/operator/admin

**Error Responses:**
- 401 - Missing auth header
- 403 - Insufficient permissions
- 200 - Authorized

**Testing:** 11 Playwright tests (6 Command Center + 5 AI Orchestrator)

### v1.5.0 - M4: Auto-Heal
**Released:** November 2025  
**Focus:** Self-healing container management

**Features:**
- FastAPI service on port 8012
- Docker API integration
- Automated container restart
- Configurable check intervals
- Status reporting API

**Monitored Services:**
- aether-crm-ui
- aether-command-center
- aether-ai-orchestrator

**Endpoints:**
- `/ping` - Health check
- `/health` - Service status
- `/autoheal/status` - Monitoring report

**Configuration:**
- `AUTOHEAL_SERVICES` - JSON array of containers
- `AUTOHEAL_HEALTH_ENDPOINTS` - Health URL map
- `AUTOHEAL_INTERVAL_SECONDS` - Check frequency

**Command Center Integration:**
- Real-time auto-heal status display
- Recent healing attempts timeline
- Success/failure indicators

**Testing:** 5 Playwright tests

---

## Phase III: Hardening & Automation (v1.6.0+)

### v1.6.0 - M1: CI/CD Pipeline
**Released:** November 2025  
**Focus:** Automated testing & build validation

**Features:**
- GitHub Actions workflow
- Automated Phase II service testing
- Docker image build validation
- Playwright test suite execution
- Service readiness checks with retries

**Pipeline Jobs:**

**Phase II Services:**
- Start services via Docker Compose
- Wait for readiness (60s timeout per service)
- Run Command Center tests (3 tests)
- Run AI Orchestrator tests (4 tests)
- Run RBAC tests (11 tests)
- Run Auto-Heal tests (5 tests)
- Upload Playwright reports on failure
- Show service logs on failure

**Phase II Build Images:**
- Build command-center image
- Build ai-orchestrator image
- Build auto-heal image
- Test image execution
- GitHub Actions cache for layers

**Integration:**
- Runs after Phase I lint & unit tests
- Blocks merge if tests fail
- Parallel with smoke tests
- 20-minute timeout

**Documentation:**
- `docs/CI_CD.md` - Complete reference
- Local testing guide
- Debugging procedures
- Future roadmap

**Benefits:**
- Protects Phase II quality
- Catches regressions early
- Validates Docker builds
- Automated on every push
- PR checks before merge

---

## Release Tag Timeline

```
v1.0.0 ──► v1.1.0 ──► v1.2.0 ──► v1.3.0 ──► v1.4.0 ──► v1.5.0 ──► v1.6.0
  │          │          │          │          │          │          │
Phase I   Phase I   Phase II   Phase II   Phase II   Phase II  Phase III
Backend     UI      Command     AI       RBAC     Auto-Heal    CI/CD
            Auth    Center   Orchestrator          Self-Heal   Pipeline
```

---

## Test Coverage by Version

| Version | Tests Added | Cumulative |
|---------|-------------|------------|
| v1.0.0  | Backend E2E | ~10        |
| v1.1.0  | Auth flows  | ~13        |
| v1.2.0  | +3 (M1)     | ~16        |
| v1.3.0  | +4 (M2)     | ~20        |
| v1.4.0  | +11 (M3)    | ~31        |
| v1.5.0  | +5 (M4)     | ~36        |
| v1.6.0  | CI guards   | ~36 (automated) |

---

## Architecture Evolution

### Phase I: Monolithic Backend
```
┌─────────────┐
│   React UI  │
└──────┬──────┘
       │
┌──────▼──────────────────────┐
│  Customer Ops API (FastAPI) │
└──────┬──────────────────────┘
       │
┌──────▼──────┐
│  PostgreSQL │
└─────────────┘
```

### Phase II: Operational Intelligence
```
┌─────────────┐
│   React UI  │◄─────────┐
└──────┬──────┘          │
       │              ┌──▼────────────┐
┌──────▼──────────┐  │ Command Center│
│ Customer Ops API├──►│  (M1: v1.2.0) │
└──────┬──────────┘  └───────────────┘
       │                     ▲
       │              ┌──────┴──────────┐
       │              │   Auto-Heal     │
       │              │  (M4: v1.5.0)   │
       │              └─────────────────┘
       │
┌──────▼──────────┐
│ AI Orchestrator │──► [Claude Sonnet]
│  (M2: v1.3.0)   │
└─────────────────┘
       ▲
       │ RBAC (M3: v1.4.0)
       │ X-User-Roles header
```

### Phase III: Production Ready
```
┌──────────────────────────────┐
│      GitHub Actions CI       │
│  (M1: v1.6.0 - Automated)    │
└────┬─────────────────────┬───┘
     │                     │
     ▼                     ▼
[Test Suite]         [Docker Builds]
  23 tests           3 images validated
```

---

## Key Metrics

### Development Velocity
- Phase I: ~2 weeks (foundation)
- Phase II: ~1 week (4 milestones)
- Phase III M1: ~1 day (CI/CD)

### Code Quality
- All Playwright tests passing: ✅ 23/23
- Test coverage: >80% (Phase I pytest)
- Lint errors: 0 (ruff, pyright)
- Security scans: Pass (Trivy, Bandit)

### Service Reliability
- Health endpoints: 100%
- Auto-healing: Active monitoring
- Docker deployment: Standardized
- RBAC enforcement: Header-based

---

## Technology Stack

### Backend
- Python 3.11
- FastAPI 0.104.1
- Pydantic 2.4.2
- httpx 0.25.1 (async HTTP)
- docker-py (container management)

### Frontend
- React 18
- TypeScript
- Vite
- Keycloak auth

### Infrastructure
- Docker & Docker Compose
- PostgreSQL with pgvector
- Redis
- MinIO
- Grafana + Prometheus

### Testing
- Playwright 1.56.1
- pytest with coverage
- GitHub Actions CI

---

## Phase III Roadmap (Upcoming)

### M2: Centralized Configuration
- `config/` folder structure
- Environment-specific configs
- Portable deployments
- Documentation: `docs/DEPLOYMENT.md`

### M3: UI Health Endpoint
- React/Vite `/health` route
- Complete auto-heal coverage
- 100% service monitoring

### M4: Command Center Enrichment
- Last 10 auto-heal attempts display
- AI orchestration metrics
- Unified ops view

### M5: AI Orchestrator v2
- Multiple provider support
- Failover logic (Claude → Ollama → GPT-4)
- Provider health tracking

### M6: Security Audit Logging
- Role-based action logging
- 403 attempt tracking
- UI role-based visibility

---

## Migration Notes

### Breaking Changes
- **v1.4.0**: Added RBAC headers required for protected endpoints
- **v1.6.0**: CI pipeline blocks merges with failing tests

### Upgrade Path
```bash
# From v1.5.0 to v1.6.0
git pull origin master
git checkout v1.6.0

# CI runs automatically on push
# No service changes required
```

---

## Contributing

### Development Workflow
1. Create feature branch from `master`
2. Implement changes with tests
3. Run local test suite
4. Push to trigger CI
5. Await CI green checkmark
6. Request PR review
7. Merge to `master`

### Test Requirements
- All existing tests must pass
- New features require new tests
- Playwright for API/integration tests
- pytest for unit tests

### Commit Message Format
```
feat(Phase III-M2): Centralized configuration for all services
fix(M1): Command Center health check timeout
docs: Update CI/CD pipeline guide
```

---

## Support & Contact

- **Documentation**: `docs/` folder
- **CI/CD Guide**: `docs/CI_CD.md`
- **Architecture**: `docs/PHASE_II_ARCHITECTURE.md`
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

## Acknowledgments

Built with:
- FastAPI framework
- Playwright testing
- GitHub Actions
- Docker ecosystem
- VS Code + Copilot

**Current Status:** Phase III M1 Complete - CI/CD Pipeline Active ✅

**Next:** Phase III M2 - Centralized Configuration
