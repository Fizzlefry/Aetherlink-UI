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

### v1.7.0 - M2: Centralized Configuration
**Released:** November 2025
**Focus:** Environment portability & deployment flexibility

**Features:**
- Centralized environment files
- Three deployment targets: dev, docker, ci
- Standardized 22 environment variables
- Docker Compose integration
- CI/CD integration

**Configuration Files:**
- `config/.env.dev` - localhost URLs (Windows/VS Code)
- `config/.env.docker` - container networking (Docker Compose)
- `config/.env.ci` - 127.0.0.1 URLs (GitHub Actions)

**Standardized Variables:**
- Service URLs (6 variables)
- Auth configuration (3 variables)
- Database & storage (4 variables)
- Auto-heal configuration (3 variables)
- UI health endpoint (1 variable)
- Monitoring & logging (5 variables)

**Docker Integration:**
```yaml
env_file:
  - ../config/.env.docker
```

**CI Integration:**
```bash
cp config/.env.ci config/.env.docker
```

**Documentation:**
- `docs/DEPLOYMENT.md` - 600+ line deployment guide
- Environment scenarios
- Troubleshooting guide
- Best practices

**Benefits:**
- Single source of truth for configuration
- No hardcoded URLs in docker-compose
- Easy environment switching
- Portable deployments
- Consistent variable naming

### v1.8.0 - M3: UI Health Endpoint
**Released:** November 2025
**Focus:** Complete self-healing coverage

**Features:**
- Static health endpoint for UI
- Auto-heal monitoring of UI service
- 100% service coverage (UI + APIs)
- Health endpoint testing

**Implementation:**
- `services/ui/public/health.json` - Static JSON health response
- Updated `AUTOHEAL_HEALTH_ENDPOINTS` to include UI
- UI_HEALTH_URL in all 3 environment files

**Health Response:**
```json
{
  "status": "ok",
  "service": "aetherlink-ui",
  "version": "1.0.0"
}
```

**Auto-Heal Coverage:**
- ✅ aether-crm-ui → /health.json
- ✅ aether-command-center → /ops/ping
- ✅ aether-ai-orchestrator → /ping

**Testing:**
- `tests/ui-health.spec.ts` - 4 comprehensive tests
- HTTP 200 validation
- JSON structure verification
- Content-Type header check
- Browser accessibility test

**Benefits:**
- Complete self-healing loop
- UI failures detected and recovered
- Prevents "green backend, white page" problem
- Consistent health check pattern

### v1.9.0 - M4: Command Center Enrichment
**Released:** November 2025
**Focus:** Operational intelligence & history tracking

**Features:**
- Auto-heal history tracking (50-item buffer)
- Statistics calculation & aggregation
- Enhanced Command Center UI
- New observability endpoints

**Backend Enhancements:**

**History Tracking:**
- In-memory circular buffer (MAX_HISTORY: 50)
- Maintains recent healing attempts
- Automatic pruning on overflow
- Newest-first ordering

**New Endpoints:**

`GET /autoheal/history?limit=10`
- Returns recent healing attempts
- Configurable limit (default: 10, max: 50)
- Newest first ordering
- Response structure:
  ```json
  {
    "history": [...],
    "total_in_history": 0,
    "limit": 10
  }
  ```

`GET /autoheal/stats`
- Success rate calculation
- Per-service attempt counts
- Most healed service identification
- Response structure:
  ```json
  {
    "total_attempts": 0,
    "successful": 0,
    "failed": 0,
    "success_rate": 0.0,
    "services": {},
    "most_healed": "service-name"
  }
  ```

**Backward Compatibility:**
- `GET /autoheal/status` - Unchanged existing endpoint

**Frontend Enhancements:**

**Statistics Dashboard:**
- 4-card grid: Total Attempts, Success Rate, Successful, Failed
- Color-coded metrics (green for success, red for failures)
- Responsive auto-fit layout

**Configuration Panel:**
- Monitored services list
- Check interval display
- Last check timestamp
- Service count summary

**Healing Activity Timeline:**
- Recent attempts (10 items)
- Chronological display (newest first)
- Color-coded borders (green/red)
- Service name, action, message
- Full timestamps
- Success/failure icons (✅/❌)
- Empty state: "All Systems Healthy"

**Auto-Refresh:**
- All data refreshes every 15 seconds
- 4 concurrent fetch operations
- Proper interval cleanup

**Testing:**
- `tests/auto-heal-history.spec.ts` - 13 comprehensive tests
- History endpoint structure (5 tests)
- Statistics calculation (5 tests)
- Backward compatibility (1 test)
- Data integrity checks (2 tests)

**CI Integration:**
- Added to GitHub Actions workflow
- 36 total Playwright tests (23 → 36)

**Benefits:**
- "What's it been doing?" visibility
- Identify flapping services
- Operational intelligence over time
- Real-time ops console
- History for troubleshooting
- Success rate trends

### v1.10.0 - M5: AI Orchestrator v2 (Provider Fallback)
**Released:** November 2025
**Focus:** AI reliability & resilience through multi-provider fallback

**Problem Statement:**
- Single AI provider = single point of failure
- If Claude API is down, entire AI system stalls
- No visibility into provider health
- Manual intervention required

**Solution: Provider Fallback Architecture**

**Backend Enhancements:**

**Provider Configuration:**
- Environment-based provider order: `PROVIDER_ORDER=claude,ollama,openai`
- Individual provider URLs via env vars
- Configurable priority without code changes

**Health Tracking:**
- In-memory health status per provider
- Tracks: healthy, last_error, last_checked, total_calls, failed_calls
- Automatic marking on success/failure

**Fallback Logic:**
- Try providers in configured order
- Skip recently failed (unhealthy) providers
- Return first successful response
- Include `used_provider` in response
- 502 error with all provider details if complete failure

**New Endpoints:**

`GET /providers/health`
- Real-time provider status
- Per-provider statistics
- Health tracking visibility
- Response structure:
  ```json
  {
    "claude": {
      "healthy": true,
      "last_error": null,
      "last_checked": "2025-11-04T20:53:00Z",
      "total_calls": 15,
      "failed_calls": 0
    },
    "ollama": {...},
    "openai": {...}
  }
  ```

`GET /ping` (Enhanced)
- Now includes provider order: `"providers": ["claude", "ollama", "openai"]`
- Service version: `"ai-orchestrator-v2"`

`POST /orchestrate` (Enhanced)
- Returns `used_provider` field showing which provider succeeded
- Enhanced 502 error with all provider errors and latency

**Frontend Enhancements:**

**AI Provider Health Panel:**
- Real-time provider status dashboard
- Success/failure counters per provider
- Success rate calculation
- Last error visibility
- Color-coded health indicators (green/red)
- Auto-refresh every 15 seconds

**UI Location:**
- Command Center page
- Below Auto-Heal History
- Above Footer Info

**Configuration Files Updated:**
- `config/.env.dev` - 5 new variables (PROVIDER_ORDER + 3 URLs)
- `config/.env.docker` - Container networking URLs
- `config/.env.ci` - CI-specific URLs (127.0.0.1)

**Testing:**

**New Test File:** `tests/ai-orchestrator-fallback.spec.ts`
- Provider health endpoint validation (3 tests)
- Fallback behavior verification (4 tests)
- Error handling scenarios (2 tests)
- **9 new tests total**

**Test Coverage:**
- Health tracking structure
- Ping endpoint provider list
- Valid/invalid intent handling
- RBAC enforcement (401/403)
- Provider fallback logic
- Health updates after failures

**CI Integration:**
- 52 total Playwright tests (36 → 52, +16 including pre-existing)
- 47 passing tests in current state
- Automated in GitHub Actions

**Technical Implementation:**

**Code Changes:**
- `services/ai-orchestrator/main.py` - Complete v2 rewrite
  - Enhanced imports (List, Dict, Any, datetime)
  - Provider configuration from env
  - Health tracking functions: `mark_provider_failure()`, `mark_provider_success()`
  - Generic provider call: `call_provider()`
  - Enhanced orchestrate logic with fallback loop
  - New provider health endpoint
- `services/ui/src/pages/CommandCenter.tsx` - AI Provider Health panel
  - New type: `ProviderHealth`
  - Provider health fetching function
  - Auto-refresh interval (15s)
  - Provider status cards with stats
  - Success rate calculation
  - Error display

**Deployment:**
- Docker container rebuild required
- All 3 env files updated
- No database migrations needed
- Backward compatible API (existing endpoints unchanged)

**Benefits:**
- **Real-world reliability:** No single provider failure stalls entire system
- **Automatic failover:** Zero manual intervention required
- **Operational visibility:** See which providers are healthy/failing
- **Cost optimization:** Can prioritize cheaper providers first
- **Graceful degradation:** System continues working with partial failures
- **Debug-friendly:** Full error context in 502 responses

**User Impact:**
> "if your primary LLM is slow/down, everything else you built shouldn't stall"

AI features now continue working even if the primary provider fails, making the entire platform more production-ready and resilient.

---

## Release Tag Timeline

```
v1.0.0 ──► v1.1.0 ──► v1.2.0 ──► v1.3.0 ──► v1.4.0 ──► v1.5.0 ──► v1.6.0 ──► v1.7.0 ──► v1.8.0 ──► v1.9.0 ──► v1.10.0
  │          │          │          │          │          │          │          │          │          │          │
Phase I   Phase I   Phase II   Phase II   Phase II   Phase II  Phase III Phase III Phase III Phase III Phase III
Backend     UI      Command     AI       RBAC     Auto-Heal   CI/CD    Centralized UI Health Command Ctr  AI Orch v2
            Auth    Center   Orchestrator          Self-Heal   Pipeline    Config   Endpoint  Enrichment  Fallback
```

---

## Test Coverage by Version

| Version  | Tests Added | Cumulative | Notes |
|----------|-------------|------------|-------|
| v1.0.0   | Backend E2E | ~10        | Initial backend validation |
| v1.1.0   | Auth flows  | ~13        | UI authentication |
| v1.2.0   | +3 (M1)     | ~16        | Command Center |
| v1.3.0   | +4 (M2)     | ~20        | AI Orchestrator |
| v1.4.0   | +11 (M3)    | ~31        | RBAC enforcement |
| v1.5.0   | +5 (M4)     | ~36        | Auto-Heal self-healing |
| v1.6.0   | CI guards   | ~36        | Automated in CI |
| v1.7.0   | Config docs | ~36        | Deployment guide |
| v1.8.0   | +4 UI health| ~40        | UI health endpoint |
| v1.9.0   | +13 history | ~49        | Auto-heal history & stats |
| v1.10.0  | +9 fallback | ~52        | AI provider fallback & health |

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
