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

### v1.11.0 - M6: Security Audit Logging
**Released:** November 2025
**Focus:** Security monitoring & operational visibility

**Problem Statement:**
- No visibility into who accesses what
- Authorization failures (401/403) go untracked
- Can't identify usage patterns or suspicious activity
- No audit trail for security compliance

**Solution: Security Audit Middleware**

**Backend Implementation:**

**Audit Middleware:**
- Shared audit module: `services/common/audit.py` (replicated per service)
- FastAPI HTTP middleware logs every request
- Captures: timestamp, service, path, method, user roles, status code, client IP
- Logs to stdout (Docker logs capture for centralization)
- In-memory statistics tracking

**Audit Statistics:**
- Total request count
- 401 unauthorized attempts
- 403 forbidden attempts
- Top 10 paths by usage
- Status code breakdown

**New Endpoints:**

`GET /audit/stats` (all services)
- Real-time audit statistics
- RBAC-protected (operator/admin for command-center, agent/operator/admin for ai-orchestrator)
- Response structure:
  ```json
  {
    "total_requests": 150,
    "denied_401_unauthorized": 5,
    "denied_403_forbidden": 3,
    "by_path": {
      "/ops/health": 50,
      "/orchestrate": 30,
      "/ping": 25
    },
    "by_status": {
      "200": 140,
      "401": 5,
      "403": 3,
      "502": 2
    }
  }
  ```

**Services Updated:**
- **Command Center** (`services/command-center`)
  - Added `audit.py` middleware
  - Added `/audit/stats` endpoint (operator/admin)
  - Updated Dockerfile to copy audit.py

- **AI Orchestrator** (`services/ai-orchestrator`)
  - Added `audit.py` middleware
  - Added `/audit/stats` endpoint (agent/operator/admin)
  - Updated Dockerfile to copy audit.py

- **Auto-Heal** (`services/auto-heal`)
  - Added `audit.py` middleware
  - Added `/audit/stats` endpoint (no RBAC for monitoring)
  - Updated Dockerfile to copy audit.py

**Audit Log Format:**
```json
{
  "ts": "2025-11-04T15:14:23.000000",
  "service": "AetherLink Command Center",
  "path": "/ops/health",
  "method": "GET",
  "roles": "operator",
  "status": 200,
  "client_ip": "172.17.0.1"
}
```

**Testing:**

**New Test File:** `tests/audit-logging.spec.ts`
- Audit stats endpoint validation (3 tests)
- 401 unauthorized tracking (1 test)
- 403 forbidden tracking (1 test)
- Path usage tracking (1 test)
- Status code breakdown (1 test)
- RBAC enforcement audit (1 test)
- **8 new tests total**

**Test Coverage:**
- All three services expose /audit/stats
- Audit tracks authorization failures
- Path and status breakdowns populate correctly
- RBAC violations are logged

**CI Integration:**
- 60 total Playwright tests (52 → 60, +8 new)
- 55 passing tests in current state
- Automated in GitHub Actions

**Security Benefits:**

**Operational Visibility:**
- "Who keeps hitting /ops/health without operator?" → Check denied_401 + by_path
- "Are we getting lots of 403s?" → Check denied_403_forbidden
- "What's the actual usage of the orchestrator?" → Check by_path breakdown
- "Which endpoints are failing?" → Check by_status

**Audit Trail:**
- Every request logged to stdout
- Docker logs capture for centralization
- Can pipe to Splunk, ELK, or other SIEM
- Timestamp + roles + status = security audit trail

**Compliance:**
- Track who accessed what and when
- Authorization failure visibility
- Role-based access logging
- Client IP tracking for forensics

**Implementation Pattern:**
- Copy audit.py per service (same pattern as rbac.py)
- Single line to add middleware: `app.middleware("http")(audit_middleware)`
- Automatic request/response interception
- Zero impact on existing endpoints

**Benefits:**
- **Security monitoring:** Know who hits what, when, and with what result
- **Compliance ready:** Full audit trail for sensitive endpoints
- **Ops intelligence:** Usage patterns, top paths, failure rates
- **Debug-friendly:** Client IP + roles + status in every log
- **Low overhead:** In-memory stats, async logging, minimal latency impact

**User Impact:**
> "We want to know who hit what and whether it was allowed or denied"

**User Impact:**
> "We want to know who hit what and whether it was allowed or denied"

Every request to sensitive services is now tracked, logged, and aggregated into real-time statistics. Operators can identify suspicious activity, track usage patterns, and meet security compliance requirements.

### v1.12.0 - Phase IV: Production Packaging
**Released:** November 2025
**Focus:** Turnkey deployment for any machine or cloud

**Problem Statement:**
- AetherLink proven in dev, but no clean deployment path
- Manual Docker commands error-prone
- No template for production configuration
- Missing deployment documentation
- Hard to share/deploy to new environments

**Solution: Production Packaging**

**Deployment Files:**

**1. Production Compose: `deploy/docker-compose.prod.yml`**
- Multi-service orchestration (Command Center, AI Orchestrator, Auto-Heal, UI)
- Health checks for all services (30s interval, 3 retries)
- Restart policies (`unless-stopped`)
- Docker socket volume for Auto-Heal
- Bridge network (`aetherlink`)
- TAG environment variable support for versioned images
- Centralized config via `../config/.env.prod`

**Services Defined:**
- `command-center` → port 8010
- `ai-orchestrator` → port 8011
- `auto-heal` → port 8012
- `ui` → port 5173

**2. Configuration Template: `config/.env.prod.template`**
- Complete template with all Phase I-III variables
- Placeholder values for secrets (`REPLACE_ME`)
- Comments explaining each section
- Ready for copy → fill → deploy workflow

**Configuration Sections:**
- Core service URLs (internal Docker networking)
- Health endpoint mappings
- Auto-Heal service list & check interval
- AI Orchestrator provider order & URLs
- RBAC defaults (operator, admin roles)
- Audit logging config (enabled, buffer limit)
- Optional metrics (Grafana, Prometheus)

**3. Install Guide: `docs/INSTALL.md`**
- Complete step-by-step deployment guide
- Prerequisites checklist (Docker, Compose, permissions)
- Environment preparation instructions
- Image build/push options (local & registry)
- Service verification commands
- Auto-Heal behavior explanation
- Security/audit endpoint usage
- Stop/update procedures
- Production hardening notes (TLS, secrets, logging)

**Deployment Workflow:**

**Quick Start:**
```bash
# 1. Prepare config
cp config/.env.prod.template config/.env.prod
vim config/.env.prod  # fill in your values

# 2. Build images (if local)
docker build -t aetherlink/command-center:latest services/command-center
docker build -t aetherlink/ai-orchestrator:latest services/ai-orchestrator
docker build -t aetherlink/auto-heal:latest services/auto-heal
docker build -t aetherlink/ui:latest services/ui

# 3. Start everything
cd deploy
docker compose -f docker-compose.prod.yml up -d

# 4. Verify
curl http://localhost:8010/ops/ping
curl http://localhost:8011/ping
curl http://localhost:8012/ping
curl http://localhost:5173/health.json
```

**Verification Endpoints:**
- Command Center: `/ops/ping`, `/ops/health`
- AI Orchestrator: `/ping`, `/providers/health`
- Auto-Heal: `/ping`, `/autoheal/status`
- UI: `/health.json`

**Production Notes:**
- Use Nginx/Traefik for TLS termination
- Store secrets in Vault or AWS Secrets Manager
- Push images to registry (not local builds on prod)
- Hook Docker logs to ELK/Splunk (audit logs ready)
- Set resource limits in Compose (memory, CPU)

**Benefits:**
- **Portability:** Deploy to any Docker host in minutes
- **Repeatability:** Same config structure for dev/staging/prod
- **Documentation:** Complete guide for new team members
- **Versioning:** TAG variable for controlled rollouts
- **Best practices:** Health checks, restart policies, centralized config

**Phase IV Complete:**
AetherLink is now production-ready with clean packaging, documented deployment, and flexible configuration for any environment.

### v1.13.0 - Phase V: Service Registry & Protocols
**Released:** November 2025
**Focus:** Dynamic service discovery and standardized inter-service protocols

**Problem Statement:**
- Services hardcoded in environment variables
- No dynamic service discovery
- No standardized protocol documentation
- Hard to add new services to the mesh
- Manual configuration for each new service

**Solution: Service Registry + Protocol Standardization**

**Backend Enhancements:**

**Service Registry (Command Center):**
- In-memory service registry for dynamic discovery
- Services can self-register at startup
- Automatic `health_url` defaulting to `/ping`
- Last seen timestamp tracking

**New Endpoints:**

`POST /ops/register` (RBAC: operator/admin)
- Register a service with the Command Center
- Upsert behavior: update if exists, insert if new
- Tracks: name, url, health_url, version, roles_required, tags, last_seen
- Request body:
  ```json
  {
    "name": "aether-ai-orchestrator",
    "url": "http://aether-ai-orchestrator:8011",
    "health_url": "http://aether-ai-orchestrator:8011/ping",
    "version": "v1.10.0",
    "roles_required": ["agent", "operator", "admin"],
    "tags": ["ai", "routing"]
  }
  ```

`GET /ops/services` (RBAC: operator/admin)
- List all registered services
- Returns count and service details array
- Shows last_seen timestamps for monitoring

`DELETE /ops/services/{name}` (RBAC: operator/admin)
- Remove a service from registry
- Returns 404 if service not found
- Useful for cleaning up stale registrations

**Protocol Documentation:**

**1. AetherLink Protocols v1.0** (`docs/AETHERLINK_PROTOCOLS.md`)
- Service identity requirements (GET /ping mandatory)
- Auth/RBAC header standard (X-User-Roles)
- Audit logging requirements
- Health model (ok/degraded/down)
- Auto-Heal integration contract
- Service registration guidelines
- Error response format
- Timeout standards
- Protocol compliance checklist

**2. Event Schema Registry** (`docs/EVENT_SCHEMA_REGISTRY.md`)
- Event-driven architecture documentation
- Standard event envelope structure
- Registered event types:
  - lead.created (CRM)
  - ai.summary.created (AI Orchestrator)
  - ops.autoheal.performed (Auto-Heal)
  - ops.service.registered (Command Center)
  - security.rbac.violation (Security)
- Versioning rules (never break consumers)
- Topic naming convention (aetherlink.<domain>.<entity>.<action>)
- Producer/consumer contracts

**3. AI Provider Capability Descriptor** (`config/ai-providers.yaml`)
- YAML-based provider configuration
- Capability-based routing (summarize_activity, extract_lead, classify_intent, etc.)
- Provider metadata (vendor, tier, model)
- Fallback order specification
- Timeout and weight configuration
- Circuit breaker settings
- Health check intervals
- Ready for AI Orchestrator v3 capability-based routing

**Testing:**

`tests/service-registry.spec.ts` - 12 comprehensive tests:
- POST /ops/register without roles → 401 (1 test)
- POST /ops/register with operator role (1 test)
- Upsert behavior (update existing service) (1 test)
- GET /ops/services without roles → 401 (1 test)
- GET /ops/services with operator role (1 test)
- Service details validation (1 test)
- DELETE /ops/services/{name} without roles → 401 (1 test)
- DELETE /ops/services/{name} removes service (1 test)
- DELETE non-existent service → 404 (1 test)
- Default health_url to /ping (1 test)
- Admin role support (1 test)
- Last seen timestamp updates (1 test)
- **12 new tests total**

**Test Coverage:**
- 72 total Playwright tests (60 → 72, +12 new)
- 67 passing tests in current state

**CI Integration:**
- Service registry tests in GitHub Actions
- RBAC protection verified
- Upsert behavior validated
- Default values tested

**Benefits:**
- **Dynamic discovery:** Services announce themselves instead of hardcoded lists
- **Standardized protocols:** Clear contracts for all inter-service communication
- **Event-driven ready:** Schema registry prepared for async workflows
- **Capability routing:** AI providers described by capabilities, not just names
- **Developer experience:** Clear checklist for adding new services
- **Operational visibility:** See which services are registered and when
- **Future-proof:** Ready for 10-12+ services without config explosion

**User Impact:**
> "No more editing docker-compose every time we add a service"

Services can now join the mesh dynamically. Protocol docs ensure new services integrate correctly. Event schema registry prepares for async event-driven workflows. AI providers described by capabilities for smarter routing.

**Phase V Foundation:**
This release completes the "protocol layer" - the standardization that makes AetherLink ready to scale from 4 services to dozens without breaking existing patterns.

### v1.14.0 - Phase V Part 2: Registry-Driven Ops Loop
**Released:** November 2025
**Focus:** Living registry with self-registration and dynamic discovery

**Problem Solved:**
v1.13.0 created the registry infrastructure, but services didn't use it yet. This release wires the protocol layer into actual service behavior, creating a full ops loop.

**Quote:**
> "The biggest win now is to wire the protocol we just created into the services we already have so you don't end up with 'nice doc, nobody uses it.'"

**Features:**

**1. Auto-Heal Registry Integration** (`services/auto-heal/main.py`)
- `fetch_registered_services()` - Async function pulls GET `/ops/services` from Command Center
- **Service Merge Logic:** Configured services (env) + Registry services (dynamic API fetch)
- **Async Conversion:** `loop_once()` converted from sync to async for non-blocking registry fetch
- **Auto-Population:** Registry `health_url` automatically added to `HEALTH_ENDPOINTS` dict
- **Configuration:** `AUTOHEAL_PULL_FROM_REGISTRY` env var (default: `"true"`)
- **Main Loop:** Converted to `asyncio.run()` with `asyncio.sleep()`

**2. AI Orchestrator Self-Registration** (`services/ai-orchestrator/main.py`)
- `_register_with_command_center()` - Async function POSTs to `/ops/register` on startup
- **Startup Event Handler:** `@app.on_event("startup")` triggers registration
- **Protocol-Compliant:** Uses `X-User-Roles: operator` header per AetherLink Protocols v1.0
- **Non-Blocking:** Registration failure doesn't crash service startup
- **Comprehensive Metadata:** Sends name, url, health_url, version, roles_required, tags

**3. Integration Testing** (`tests/registry-driven-autoheal.spec.ts`)
- 6 comprehensive tests covering full loop:
  1. Auto-Heal can fetch services from registry without errors
  2. Auto-Heal history endpoint works with registry integration
  3. Auto-Heal stats endpoint works with registry integration
  4. AI Orchestrator registers itself and appears in Command Center
  5. Registry services have valid health URLs for Auto-Heal
  6. Command Center provides registry and auto-heal data for reconciliation

**Reconciliation View:** Test demonstrates operational visibility - shows registered vs monitored services to identify gaps

**Architecture:**

```
AI Orchestrator Startup
  ↓
POST /ops/register → Command Center
  ↓
Stored in registry (in-memory dict)
  ↓
Auto-Heal fetches GET /ops/services
  ↓
Merged into services_to_check set
  ↓
health_url added to HEALTH_ENDPOINTS
  ↓
Automatic health monitoring begins
  ↓
If unhealthy → restart (existing logic)
  ↓
Healing logged in /autoheal/history
```

**Design Decisions:**
1. **Additive, Not Replacement:** Registry services merge with env-configured services (backward compatible)
2. **Async Conversion:** Auto-Heal loop converted to async/await for non-blocking registry fetch
3. **Protocol Compliance:** All registry calls use `X-User-Roles: operator` header
4. **Graceful Degradation:** Registry fetch failure returns empty list, healing continues
5. **Automatic Health Mapping:** health_url from registry auto-populates HEALTH_ENDPOINTS

**Live Verification:**
AI Orchestrator successfully self-registered and appears in GET `/ops/services`:
```json
{
  "name": "aether-ai-orchestrator",
  "url": "http://aether-ai-orchestrator:8011",
  "health_url": "http://aether-ai-orchestrator:8011/ping",
  "version": "v1.10.0",
  "roles_required": ["agent", "operator", "admin"],
  "tags": ["ai", "orchestrator", "phase-ii"],
  "last_seen": "2025-11-04T22:56:37.420702+00:00"
}
```

**Benefits:**
- **Dynamic Discovery:** Services appear without editing configs
- **Automatic Monitoring:** Auto-Heal picks up registered services automatically
- **Living Registry:** Real-time service mesh state visible via GET `/ops/services`
- **Self-Organizing:** Services join mesh on startup
- **Backward Compatible:** Env-configured services still work
- **Operational Visibility:** Reconciliation view shows registered vs monitored gaps
- **Protocol Adoption:** Actual usage of AetherLink Protocols v1.0 (not just documentation)

**User Impact:**
> "Make these 3 things true:
> 1. If a service shows up → Command Center knows. ✅
> 2. If Command Center knows → Auto-heal can monitor. ✅
> 3. If Auto-heal heals → it gets logged and visible in Command Center. ✅"

**Testing:** +6 tests (all passing)

**Phase V Complete:**
Protocol layer is now CONSUMED, not just documented:
- **Registry Provider:** Command Center ✅
- **Registry Publishers:** AI Orchestrator ✅
- **Registry Consumers:** Auto-Heal ✅
- **Full Loop:** Operational ✅

**Future Work:**
- Add self-registration to Command Center, UI, Auto-Heal itself
- Create UI reconciliation panel (show registered vs monitored comparison)
- Fix COMMAND_CENTER_URL port config (8000 → 8010)
- Migrate from deprecated `@app.on_event("startup")` to lifespan event handlers

### v1.18.0 - Phase VII M2: Event Retention & Archival
**Released:** November 2025
**Focus:** Automated event pruning to keep database lean and performant

**Problem Solved:**
Event Control Plane (v1.15.0-v1.17.0) created a "chatty" system: Auto-Heal, AI Orchestrator, Command Center, and alerts all emit events continuously. Without retention, the SQLite database would grow indefinitely, degrading performance and consuming disk space.

**Features:**

**1. Automated Event Pruning** (`event_store.prune_old_events()`):
- Deletes events older than configurable retention window
- Default: 30 days (via `EVENT_RETENTION_DAYS`)
- Runs automatically via background worker
- Manual trigger available via API endpoint

**2. Background Retention Worker** (`retention_worker()` in `main.py`):
- Runs every `EVENT_RETENTION_CRON_SECONDS` (default: 3600s / 1 hour)
- Non-blocking async task (like alert evaluator)
- Starts automatically on Command Center startup
- Emits `ops.events.pruned` event for observability

**3. Optional Archival to NDJSON**:
- Archive events before deletion when `EVENT_ARCHIVE_ENABLED=true`
- NDJSON format (newline-delimited JSON) for easy S3/MinIO upload
- Stored in `EVENT_ARCHIVE_DIR` (default: `/app/data/archive`)
- Filename pattern: `events-YYYY-MM-DD.ndjson`
- Graceful degradation: continues pruning even if archival fails

**4. Ops-Visible Endpoints**:
- `GET /events/retention` - View current retention configuration
- `POST /events/prune` - Manually trigger pruning (operator/admin only)
- Returns: cutoff timestamp, pruned count, archived count, strategy

**5. Observability Events**:
- `ops.events.pruned` emitted after each prune operation
- Severity: `info`
- Payload: pruned_count, cutoff, retention_days, archived, strategy
- Visible in EventStream UI
- Can trigger alerts if pruning fails in future

**Architecture:**
```
retention_worker (background task)
    ↓
Every EVENT_RETENTION_CRON_SECONDS
    ↓
event_store.prune_old_events()
    ↓
[Optional] Archive to NDJSON
    ↓
DELETE events older than retention window
    ↓
Emit ops.events.pruned event
    ↓
Ops sees pruning in EventStream UI ✅
```

**Configuration** (added to `.env.prod.template`, `.env.docker`):
```bash
EVENT_RETENTION_DAYS=30                 # How long to keep events
EVENT_RETENTION_CRON_SECONDS=3600       # How often to prune (1 hour)
EVENT_ARCHIVE_ENABLED=false             # Enable archival before deletion
EVENT_ARCHIVE_DIR=/app/data/archive     # Where to store archives
```

**Testing:**
- Manual prune via `POST /events/prune` returns summary
- Retention settings visible via `GET /events/retention`
- `ops.events.pruned` events created and queryable
- Confirmed 0 events pruned (all events recent in dev)
- Background worker starts automatically (logged)

**Benefits:**
- **Database Performance**: Keeps SQLite fast as event volume grows
- **Disk Space Management**: Prevents unbounded growth
- **Compliance Ready**: Archival enables audit trails for regulated industries
- **Configurable**: Adjust retention per environment
- **Non-Blocking**: Pruning doesn't impact event ingestion
- **Observable**: Pruning operations visible as events

---

### v1.19.0 - Phase VII M3: Tenant-Aware Events (Multi-Tenant SaaS)
**Released:** November 2025
**Focus:** Transform Event Control Plane from single-tenant ops tool into multi-tenant SaaS platform

**Problem Solved:**
Previous Event Control Plane (v1.15.0-v1.18.0) treated all events as global: any operator could see events from all workloads, alert rules applied globally, and there was no tenant data isolation. For SaaS deployments, this creates:
- **Data Leakage Risk**: Tenant A could see Tenant B's events
- **Alert Noise**: Alert rules fire across all tenants indiscriminately
- **Operational Overhead**: Manual filtering required to isolate tenant issues

**Features:**

**1. Tenant Context Middleware** (`TenantContextMiddleware` in `main.py`):
- Extracts `X-Tenant-ID` from request headers
- Stores in `request.state.tenant_id` for downstream handlers
- Applied globally to all endpoints
- Single source of truth for tenant context

**2. Auto-Injection on Event Publish** (`POST /events/publish`):
- Checks `request.state.tenant_id` from middleware
- Injects `tenant_id` into event payload if missing
- Fallback to `"default"` if no header present
- Producer code doesn't need to include tenant_id manually

**3. Tenant-Scoped Event Filtering** (`event_store.py`):
- `list_recent()`, `count_events()`, `get_event_stats()` accept `tenant_id` parameter
- SQL pattern: `WHERE (tenant_id = ? OR tenant_id IS NULL)`
- Includes system events (tenant_id=NULL) in all tenant views
- Example: `GET /events/recent?tenant_id=tenant-1`

**4. Role-Based Access Control** (`routers/events.py`):
- **Admin/Operator with `tenant_id` param**: Can override to see specific tenant
- **Admin/Operator without param**: Uses header tenant or sees all
- **Non-Admin**: Locked to `X-Tenant-ID` from header (future enforcement)
- Pattern:
  ```python
  header_tenant = getattr(request.state, "tenant_id", None)
  is_admin = any(r in ("admin", "operator") for r in user_roles)
  effective_tenant = tenant_id if (is_admin and tenant_id) else header_tenant
  ```

**5. Tenant-Scoped Alert Rules** (`alert_store.py`, `alert_evaluator.py`):
- Added `tenant_id` column to `alert_rules` table (with migration)
- `create_rule()` accepts `tenant_id` parameter (from `request.state.tenant_id`)
- Alert evaluator filters events by `rule.tenant_id` when checking thresholds
- Rules with `tenant_id=NULL` apply globally (admin rules)
- Example: Alert for "autoheal.failed >= 3 in 5min for tenant-acme only"

**6. UI Tenant Selector** (`EventStream.tsx`):
- Added tenant state: `useState<string | null>(null)`
- Dropdown selector: "All tenants", "tenant-1", "tenant-2", "tenant-acme", "tenant-demo"
- Appends `&tenant_id=${tenant}` to API calls when selected
- Re-fetches events when tenant filter changes
- Future: Dynamic tenant list from API

**Architecture:**
```
Client sends X-Tenant-ID: tenant-1
    ↓
TenantContextMiddleware extracts header
    ↓
request.state.tenant_id = "tenant-1"
    ↓
POST /events/publish → Auto-injects tenant_id into event
GET /events/recent → Filters by effective_tenant (RBAC)
GET /events/stats → Returns tenant-scoped stats
POST /alerts/rules → Binds rule to tenant-1
    ↓
alert_evaluator → Counts events WHERE tenant_id = "tenant-1"
    ↓
ops.alert.raised event has tenant_id = "tenant-1"
```

**Database Changes:**
```sql
-- Migration applied in alert_store.init_db()
ALTER TABLE alert_rules ADD COLUMN tenant_id TEXT;

-- Event queries now support tenant filtering
SELECT * FROM events
WHERE (tenant_id = 'tenant-1' OR tenant_id IS NULL)
ORDER BY id DESC LIMIT 50;
```

**Testing Results:**
- ✅ Tenant filtering works: `GET /events/recent?tenant_id=tenant-1` returns only tenant-1 events + system events
- ✅ Stats endpoint tenant-aware: `GET /events/stats?tenant_id=tenant-acme` returns correct counts
- ✅ Admin view (no filter): Returns all events across tenants
- ✅ UI tenant selector: Dropdown filter working in EventStream component
- ✅ Alert rules: Created with tenant_id, evaluator filters events by rule.tenant_id

**Benefits:**
- **SaaS-Ready**: Proper tenant data isolation for multi-tenant deployments
- **Scalable**: Each tenant sees only their events (reduces UI noise)
- **Flexible**: Admin roles can cross tenant boundaries for support
- **Secure**: Prevents accidental data leakage between tenants
- **Operational**: Tenant-scoped alerts reduce false positive noise
- **Future-Proof**: Foundation for per-tenant billing, quotas, RBAC policies

---

### v1.20.0 - Phase VII M4: Per-Tenant Retention Policies
**Released:** November 2025
**Focus:** Fine-grained event data lifecycle management per tenant

**Problem Solved:**
Previous retention (v1.18.0) used a single global `EVENT_RETENTION_DAYS` setting for all events. In multi-tenant SaaS deployments (v1.19.0), this creates operational challenges:
- **Premium tenants** may need longer retention (90+ days for compliance/audit trails)
- **Test/QA tenants** produce high event volume but need short retention (1-7 days)
- **Basic tier tenants** default to standard retention (30 days)
- **System events** need separate lifecycle from tenant events

Without per-tenant policies, operators must choose between:
- Short global retention → Premium customers lose audit history
- Long global retention → Database bloat from noisy test tenants

**Features:**

**1. Tenant Retention Table** (`event_store.py`):
- New SQLite table: `tenant_retention (tenant_id PRIMARY KEY, retention_days, created_at, updated_at)`
- Stores per-tenant retention overrides
- Tenants without override use global `EVENT_RETENTION_DAYS` default

**2. Per-Tenant Pruning Logic** (`prune_old_events_with_per_tenant()`):
- Prunes system events (tenant_id=NULL) using global retention
- Gets distinct tenant_ids from active events
- Looks up each tenant's retention policy (override or global default)
- Prunes each tenant's events separately with appropriate cutoff
- Returns list of results (one per scope: system + tenants)

**3. Tenant Retention Management Functions**:
- `get_tenant_retention_map()` - Returns {tenant_id: retention_days} for all overrides
- `set_tenant_retention(tenant_id, retention_days)` - Upsert tenant policy
- `delete_tenant_retention(tenant_id)` - Revert tenant to global default

**4. Updated Retention Worker** (`main.py`):
- Switched from `prune_old_events()` to `prune_old_events_with_per_tenant()`
- Emits separate `ops.events.pruned` event for each scope
- Each pruned event tagged with appropriate tenant_id
- Operators see per-tenant pruning in EventStream UI

**5. Tenant Retention API Endpoints** (`routers/events.py`):
- `GET /events/retention/tenants` - List all tenant policies + global default
- `PUT /events/retention/tenants/{tenant_id}?retention_days=N` - Set tenant policy
- `DELETE /events/retention/tenants/{tenant_id}` - Revert to global default

**6. Updated Manual Prune** (`POST /events/prune`):
- Now uses per-tenant retention instead of global-only
- Returns `{total_pruned, scopes: [{scope, pruned_count, retention_days, cutoff}]}`
- Emits ops.events.pruned per scope for observability

**Architecture:**
```
retention_worker() runs every 3600s
    ↓
prune_old_events_with_per_tenant()
    ↓
1) Prune system events (tenant_id=NULL) → global retention (30d)
2) Get active tenant_ids from events
3) For each tenant:
   - Look up retention override OR use global default
   - Prune that tenant's events with specific cutoff
4) Return results array (one per scope)
    ↓
Emit ops.events.pruned for each scope
    ↓
Operators see: "tenant-qa pruned 15 events (1d retention)"
               "tenant-premium pruned 0 events (90d retention)"
```

**Database Schema:**
```sql
-- New table for tenant-specific retention policies
CREATE TABLE IF NOT EXISTS tenant_retention (
    tenant_id TEXT PRIMARY KEY,
    retention_days INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**API Examples:**
```bash
# Set aggressive retention for test tenant
PUT /events/retention/tenants/tenant-qa?retention_days=1

# Premium customer gets 90-day retention
PUT /events/retention/tenants/tenant-premium?retention_days=90

# Enterprise customer with compliance requirements
PUT /events/retention/tenants/tenant-acme?retention_days=60

# List all policies
GET /events/retention/tenants
# Returns:
{
  "tenant_policies": {
    "tenant-qa": 1,
    "tenant-premium": 90,
    "tenant-acme": 60
  },
  "global_default_days": 30
}

# Revert tenant to global default
DELETE /events/retention/tenants/tenant-qa
```

**Testing Results:**
- ✅ Set tenant-qa=1d, tenant-premium=90d, tenant-acme=60d via API
- ✅ Published 2-day-old event for tenant-qa
- ✅ Triggered manual prune: 1 event pruned from tenant-qa (verified 1d policy)
- ✅ tenant-premium events retained (90d policy)
- ✅ ops.events.pruned emitted per-tenant with correct scope tagging
- ✅ Per-scope results visible in EventStream UI

**Benefits:**
- **SaaS-Grade Lifecycle**: Each tenant gets appropriate retention for their tier
- **Cost Optimization**: Aggressive pruning for noisy test/QA tenants
- **Compliance Ready**: Premium/enterprise tenants get extended retention
- **Operational Visibility**: Per-tenant pruning visible via ops.events.pruned
- **Backward Compatible**: Tenants without override use global default
- **No Downtime**: Policies can be adjusted via API without restart

**Docker Changes:**
- No Dockerfile updates needed (uses existing event_store.py)
- Environment variables propagated via docker-compose.yml

**Result:**
The Event Control Plane now "ages gracefully":
1. Services emit events continuously (Phase VI M4)
2. Alert rules detect patterns (Phase VI M6)
3. Webhooks notify teams instantly (Phase VII M1)
4. **Old events auto-prune to keep database lean** (Phase VII M2) ✅

Your event database stays small and performant, even with high-frequency emissions. The system can now run indefinitely without manual cleanup. 🗑️

### v1.17.0 - Phase VII M1: Alert Notifications
**Released:** November 2025
**Focus:** Webhook-based alert delivery for real-time team notifications

**Problem Solved:**
Alert thresholds (v1.16.0) created `ops.alert.raised` events, but they stayed in the database. Operators had to manually check for alerts. No real-time notifications to Slack, Teams, or other chat platforms.

**Features:**

**1. Webhook Notification Dispatcher** (`notification_dispatcher.py`):
- Delivers `ops.alert.raised` events to configured webhooks in real time
- Supports Slack incoming webhooks (formatted messages)
- Compatible with Teams, Discord, and generic HTTP endpoints
- Non-blocking delivery (failures don't stop alerting)
- Configurable timeout (5 seconds default)
- Delivery tracking (success/failure counts)

**2. Slack-Friendly Formatting**:
- Human-readable alert messages with emoji indicators
- Rule name, severity, threshold, and matched count
- Filter details (event type, source, severity)
- Timestamp for correlation
- Works with Discord/Teams (similar JSON format)

**3. Environment-Based Configuration**:
- New env var: `ALERT_WEBHOOKS` (comma-separated URLs)
- Example Slack: `https://hooks.slack.com/services/T000/B000/XXX`
- Example Teams: `https://outlook.office.com/webhook/XXX`
- Example Discord: `https://discord.com/api/webhooks/XXX`
- Leave empty to disable notifications (graceful no-op)

**4. Integration with Alert Evaluator**:
- Webhook dispatch happens immediately after threshold breach
- Both background evaluator (15s interval) and manual `/alerts/evaluate` trigger delivery
- Non-fatal on webhook failure (logged and tracked)
- Alert event always saved first (delivery is best-effort)

**5. Production Configuration**:
- Updated `docker-compose.prod.yml` with `ALERT_WEBHOOKS` environment variable
- Updated `.env.prod.template` with webhook documentation and examples
- Updated `docker-compose.dev.yml` for development testing

**Architecture:**
```
alert_evaluator detects threshold breach
    ↓
ops.alert.raised event stored in database
    ↓
notification_dispatcher.dispatch_alert() called
    ↓
HTTP POST to configured webhooks (Slack/Teams/Discord)
    ↓
Ops team receives instant notification in chat ✅
```

**Example Webhook Payload (Slack):**
```json
{
  "text": ":rotating_light: *AetherLink Alert Triggered*\n\n*Rule:* `autoheal-failures-spike`\n*Severity:* `CRITICAL`\n*Source:* `aether-command-center`\n*Threshold:* 3/2 events in 300s\n\n*Filters:*\n  • Event Type: `autoheal.failed`\n  • Source: `aether-auto-heal`\n  • Severity: `error`\n\n*Timestamp:* 2025-11-05T00:58:25Z"
}
```

**Testing:**
- Created test webhook server (`test_webhook_server.py`) for development
- Published test events to trigger alert thresholds
- Verified webhook delivery with local HTTP endpoint
- Confirmed non-blocking behavior (failures logged, not fatal)
- Tested with 7+ webhook deliveries successfully

**Benefits:**
- **Real-Time Awareness**: Team gets notified instantly when alerts fire
- **Multi-Platform**: Works with Slack, Teams, Discord, custom webhooks
- **Non-Breaking**: Webhook failures don't impact alert creation
- **Zero Database**: No separate notification storage needed
- **Configurable**: Enable/disable per environment
- **Observable**: Delivery tracked in Command Center logs

**Result:**
The Event Control Plane now completes the full observability loop:
1. Services emit operational events (Phase VI M4)
2. Alert rules detect patterns (Phase VI M6)
3. Webhooks notify your team instantly (Phase VII M1) ✅

Your ops team no longer needs to poll dashboards - the platform tells them when something's wrong. 🚨

### v1.15.0 - Phase VI M1+M2: Event Control Plane
**Released:** November 2025
**Focus:** Unified event pipeline with persistent storage and live streaming

**Problem Solved:**
Platform events were scattered across logs, Kafka topics, and ad-hoc implementations. No unified way to publish, query, or stream operational events. No historical event analytics.

**Features:**

**1. Event Schema Registry** (`docs/EVENT_CONTROL_PLANE.md`)
- Standardized event envelope: event_type, source, timestamp, payload, tenant_id, severity
- 6 registered event types:
  - `service.registered` - Service joins registry
  - `service.health.failed` - Health check failure
  - `autoheal.attempted` - Container restart attempt
  - `autoheal.succeeded` - Restart successful
  - `autoheal.failed` - Restart failed
  - `ai.fallback.used` - AI provider fallback

**2. Event Publish API** (`services/command-center/routers/events.py`)
- `POST /events/publish` - Publish event with schema validation
- `GET /events/schema` - List all event schemas
- `GET /events/schema/{event_type}` - Get specific schema
- Event normalization (timestamp, event_id auto-generation)
- Protocol-compliant (X-User-Roles RBAC)

**3. Persistent Event Storage** (`services/command-center/event_store.py`)
- SQLite database (`/app/data/events.db`)
- Indexed by event_type, source, tenant_id, timestamp
- Survives container restarts (Docker volume)
- Queryable event history

**4. Event Query API**
- `GET /events/recent` - Retrieve recent events
- Optional filters: event_type, source, limit
- Returns events with full metadata and audit trail

**5. Live Event Streaming** (Server-Sent Events)
- `GET /events/stream` - Real-time SSE endpoint
- Fan-out architecture (asyncio.Queue per subscriber)
- UI can connect for live operational visibility
- Auto-cleanup on client disconnect

**Architecture:**
```
Service → POST /events/publish
          ↓
    Command Center:
    1. Validate schema
    2. Normalize (timestamp, event_id, defaults)
    3. Save to SQLite
    4. Broadcast to SSE subscribers
          ↓
    Consumers:
    - UI Event Viewer (SSE stream)
    - Historical queries (GET /events/recent)
    - Audit trail
    - Future: Anomaly detection, ML
```

**Docker Changes:**
- Added `command-center-data` volume for event persistence
- Set `EVENT_DB_PATH=/app/data/events.db` environment variable

**Benefits:**
- **Unified Pipeline**: Single endpoint for all platform events
- **Schema Enforcement**: Consistent event structure across services
- **Persistent History**: Events survive restarts, queryable for debugging
- **Real-Time Visibility**: Live event stream for operators
- **Operational Intelligence**: Foundation for anomaly detection, ML
- **Audit Trail**: All events timestamped with client IP and received_at
- **Multi-Tenant Ready**: tenant_id field for future isolation

**Testing:**
- Manual testing via PowerShell/curl
- Event publish: 200 OK with event_id
- Event fetch: Returns persisted events
- Event stream: SSE connection working

**Future Work (M3+M4):**
- React EventStream UI component
- Tenant-aware filtering (X-Tenant-ID header)
- Time-range queries
- Event aggregation and analytics
- Auto-Heal and AI Orchestrator event integration

**Command Center is now a true Control Plane:**
- Service registry (Phase V) ✅
- Event pipeline (Phase VI M1+M2) ✅
- Live operational visibility ✅

### v1.16.0 - Phase VI Complete: Event Control Plane + Alerting
**Released:** November 2025
**Focus:** Service instrumentation, severity analytics, and alert thresholds

**Problem Solved:**
Event control plane existed but services didn't emit events automatically. No way to filter by severity or trigger alerts on patterns. Operators had to manually check for problems.

**Features:**

**1. Service Instrumentation (M4)**
- Auto-Heal emits events on every action:
  - `autoheal.attempted` - Before restart (severity: warning)
  - `autoheal.succeeded` - After successful restart (severity: info)
  - `autoheal.failed` - After failed restart (severity: error)
- AI Orchestrator emits events on provider behavior:
  - `ai.provider.used` - Successful provider call (severity: info)
  - `ai.fallback.used` - Fallback succeeds after failures (severity: warning)
  - `ai.fallback.failed` - All providers fail (severity: error)
- Command Center emits registry events:
  - `service.registered` - Service joins (severity: info)
  - `service.unregistered` - Service removed (severity: warning)
- All services use non-blocking event publishing (silent failures)

**2. Severity Filtering & Analytics (M5)**
- Enhanced `GET /events/recent` with new parameters:
  - `severity=info|warning|error|critical` - Filter by severity level
  - `since=<ISO timestamp>` - Time-range filtering
  - Chainable with existing filters (event_type, source, tenant_id)
- New `GET /events/stats` endpoint:
  - Total event count
  - Last 24h event count
  - Breakdown by severity level
  - Operational dashboard data
- UI severity filter buttons (All, Info, Warnings, Errors, Critical)
- Color-coded event display in Command Center

**3. Alert Threshold System (M6)**
- Alert rule engine (`services/command-center/alert_store.py`):
  - Create rules with threshold conditions
  - Rule schema: name, severity, event_type, source, window_seconds, threshold, enabled
  - SQLite storage alongside events
- Alert evaluator (`services/command-center/alert_evaluator.py`):
  - Background task runs every 15 seconds
  - Evaluates enabled rules against event store
  - Counts matching events within time windows
  - Emits `ops.alert.raised` events when thresholds exceeded
- Alert Rules API (`/alerts/rules`):
  - `POST /alerts/rules` - Create alert rule (RBAC: operator/admin)
  - `GET /alerts/rules` - List all rules
  - `GET /alerts/rules/{id}` - Get specific rule
  - `DELETE /alerts/rules/{id}` - Remove rule
  - `PATCH /alerts/rules/{id}/enabled` - Enable/disable rule
  - `POST /alerts/evaluate` - Manual evaluation trigger (for testing/CI)
- Alerts-as-events pattern:
  - `ops.alert.raised` is a normal event (severity: critical)
  - Stored in event database
  - Visible in `/events/recent`
  - Streams via SSE
  - Filterable by severity

**Architecture Evolution:**
```
Before M4: Manual event publishing via curl
After M4:  Services auto-emit on every operational action

Before M5: View all events only
After M5:  Filter by severity, analyze trends, operational stats

Before M6: React to problems manually
After M6:  System proactively alerts on threshold violations
```

**Example Alert Rule:**
```json
{
  "name": "autoheal-failures-spike",
  "severity": "error",
  "event_type": "autoheal.failed",
  "window_seconds": 300,
  "threshold": 3,
  "enabled": true
}
```
**Meaning:** Alert if 3+ container restart failures occur in 5 minutes

**Benefits:**
- **Automatic Instrumentation**: No manual event publishing needed
- **Actionable Filtering**: Triage events by importance (severity)
- **Operational Analytics**: Quick insights (total, 24h, by severity)
- **Proactive Alerting**: System tells you when it's bad
- **Rule-Based**: Define once, evaluate automatically
- **Testable**: Manual evaluation endpoint for CI
- **Non-Breaking**: Alert failures don't impact services

**Testing:**
- Manual testing via PowerShell
- Created alert rule for autoheal failures
- Published test events
- Verified alert triggered and `ops.alert.raised` emitted
- Tested severity filtering (warning, error, critical)
- Validated stats endpoint

**Docker Changes:**
- Updated Command Center Dockerfile to include:
  - `alert_store.py` - Alert rule storage
  - `alert_evaluator.py` - Background evaluator
  - `routers/alerts.py` - Alert API endpoints

**Result:**
Command Center is now the **operational nervous system**:
- Service registry (Phase V) ✅
- Event pipeline with instrumentation (Phase VI M1-M4) ✅
- Severity analytics (Phase VI M5) ✅
- Alert thresholds (Phase VI M6) ✅
- Proactive operational awareness ✅

**Phase VI Complete:** Event control plane transforms from passive logging to active alerting. The platform now observes itself, analyzes patterns, and notifies operators when thresholds are exceeded.

---

## Release Tag Timeline

```
v1.0.0 ──► v1.1.0 ──► v1.2.0 ──► v1.3.0 ──► v1.4.0 ──► v1.5.0 ──► v1.6.0 ──► v1.7.0 ──► v1.8.0 ──► v1.9.0 ──► v1.10.0 ──► v1.11.0 ──► v1.12.0
```

---

## Release Tag Timeline

```
v1.0.0 ──► v1.1.0 ──► v1.2.0 ──► v1.3.0 ──► v1.4.0 ──► v1.5.0 ──► v1.6.0 ──► v1.7.0 ──► v1.8.0 ──► v1.9.0 ──► v1.10.0 ──► v1.11.0 ──► v1.12.0 ──► v1.13.0 ──► v1.14.0 ──► v1.15.0 ──► v1.16.0 ──► v1.17.0 ──► v1.18.0
  │          │          │          │          │          │          │          │          │          │          │          │          │          │          │          │          │          │          │
Phase I   Phase I   Phase II   Phase II   Phase II   Phase II  Phase III Phase III Phase III Phase III Phase III Phase III Phase IV  Phase V  Phase V  Phase VI Phase VI Phase VII Phase VII
Backend     UI      Command     AI       RBAC     Auto-Heal   CI/CD    Centralized UI Health Command Ctr  AI Orch v2 Security Production Service  Registry   Event   Event+Alert  Webhook   Event
            Auth    Center   Orchestrator          Self-Heal   Pipeline    Config   Endpoint  Enrichment  Fallback   Audit   Packaging Registry  Loop    Control  Complete  Notifications Retention
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
| v1.11.0  | +8 audit    | ~60        | Security audit logging |
| v1.12.0  | +0 packaging| ~60        | Production deployment (no new tests) |
| v1.13.0  | +12 registry| ~72        | Service registry & protocols |
| v1.14.0  | +6 reg-loop | ~78        | Registry-driven ops loop |
| v1.15.0  | +0 events   | ~78        | Event control plane (manual testing) |

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
