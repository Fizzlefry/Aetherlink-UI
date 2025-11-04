# AetherLink – Phase II Architecture

**Version**: Draft  
**Status**: Planning  
**Depends on**: v1.1.0 (UI auth resilience & Playwright tests)  
**Target**: Q1 2026

---

## 1. Objectives

- **Add intelligent, centralized operations** (Command Center)
- **Make AI features orchestrated** instead of siloed
- **Improve security posture** (RBAC / multi-tenant clarity)
- **Keep operators in control** (auto-heal + visibility)

---

## 2. High-Level Components

### 1. **Command Center (CC)**
- Single pane for operators
- **Shows**: service health, AI usage, rule hits, lead flow
- **Pulls from**: Prometheus, Grafana annotations, notifications-consumer
- **Tech**: React (extend existing UI) or FastAPI + templated view

### 2. **AI Orchestrator**
- Sits between UI/events and existing AI services (ai-summarizer)
- **Decides**: "summarize", "extract", or "route to LLM X"
- **Can downgrade** to local Ollama if external provider unavailable
- **Emits**: Grafana annotations on anomalies/high-latency

### 3. **RBAC / Tenant Guard**
- Formalize tenant claims in JWT
- **Map roles → allowed actions** (view leads, run AI, view ops)
- **Enforce** in UI and API gateway
- **Roles**: `operator`, `viewer`, `admin`, `agent`

### 4. **Auto-Heal + Alert Hooks**
- Detect unhealthy containers (like current PowerShell autoheal script, but built-in)
- **Emit** Grafana annotation on heal attempt
- **Optional**: notify Slack/webhook
- **Runs as**: dedicated Docker container

---

## 3. Current State (from v1.0 / v1.1)

### ✅ **What's Working**
- **Event-driven spine**: Kafka + consumers → READY
- **AI summarizer**: Extract/summarize → READY
- **Notifications/rules**: Hot-reload, 5 rules → READY
- **UI test mode**: `?test=true` bypass → READY (v1.1)
- **Playwright e2e**: Full flow testing → READY (v1.1)

### ⚠️ **Gaps Addressed by Phase II**
- **No central "operations brain"** to correlate metrics + events
- **Roles/tenants not enforced uniformly** across services
- **Health script is external** (`verify-health.ps1`), not part of platform
- **AI services are independent** – no intelligent routing/failover
- **Limited observability** – operators can't see AI usage patterns

---

## 4. Target Architecture (Phase II)

```
┌─────────────────────┐
│  UI / Operator      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Command Center UI (React)              │
│  - Service Health Dashboard             │
│  - AI Usage Analytics                   │
│  - Recent Events Stream                 │
│  - Auto-Heal History                    │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  AI Orchestrator (FastAPI)              │
│  - Intent routing                       │
│  - Provider selection & failover        │
│  - Grafana annotations                  │
│  - Audit logging                        │
└──────┬──────────────────────────────────┘
       │
       ├──► ai-summarizer :9108
       ├──► notifications-consumer :9107
       ├──► Grafana Annotations API
       └──► Kafka → sinks

┌─────────────────────────────────────────┐
│  Auto-Heal Container                    │
│  - Health checks (every 2 min)          │
│  - Docker restart on failure            │
│  - Grafana annotations                  │
│  - Slack notifications                  │
└─────────────────────────────────────────┘
```

---

## 5. Detailed Component Design

### 5.1 Command Center

**Tech Stack**: React (extend existing `services/ui`) or separate FastAPI + Jinja2

**Endpoints It Calls**:
```
GET /ops/health         → Aggregated health from all services
GET /ops/events/recent  → Last 50 events from notifications-consumer
GET /ops/ai/usage       → AI extraction/summary stats
GET /ops/autoheal       → Recent auto-heal attempts
```

**UI Features**:
- **Service Status Grid**: Visual indicators (🟢🟡🔴) for each service
- **Event Stream**: Real-time feed of notifications/rules firing
- **AI Analytics**: Charts showing extraction success rate, latency percentiles
- **Auto-Heal Log**: Timeline of service restarts with reasons

**Access Control**: Requires `operator` or `admin` role

---

### 5.2 AI Orchestrator

**Tech Stack**: FastAPI (to match ai-summarizer architecture)

**Core Endpoint**:
```python
POST /orchestrate
{
  "intent": "extract" | "summarize" | "route",
  "tenant_id": "the-expert-co",
  "payload": { "raw_text": "..." }
}
```

**Responsibilities**:
1. **Intent Detection**: Decide which AI service to call
2. **Provider Selection**: Choose Claude, Ollama, or OpenAI based on:
   - Current load
   - Provider availability
   - Cost constraints
   - Latency requirements
3. **Failover Logic**: 
   ```
   Try: Claude → Fallback: Ollama → Last resort: GPT-4
   ```
4. **Annotation**: POST to Grafana on:
   - High latency (>2s)
   - Provider failover event
   - Extraction failures
5. **Audit**: Write to Kafka topic `ai-orchestrator-audit`

**Configuration** (`config/orchestrator.yaml`):
```yaml
providers:
  - name: claude
    priority: 1
    max_latency_ms: 3000
  - name: ollama
    priority: 2
    local: true
  - name: openai
    priority: 3
    max_latency_ms: 5000
```

---

### 5.3 RBAC / Tenant Guard

**Current JWT** (from Keycloak):
```json
{
  "preferred_username": "operator@company.com",
  "tenant_id": "the-expert-co"
}
```

**Phase II Enhancement**:
```json
{
  "preferred_username": "operator@company.com",
  "tenant_id": "the-expert-co",
  "roles": ["operator", "admin"]
}
```

**Role Definitions**:
| Role | Can View Leads | Can Run AI | Can View Ops | Can Configure |
|------|----------------|------------|--------------|---------------|
| `viewer` | ✅ | ❌ | ❌ | ❌ |
| `agent` | ✅ | ✅ | ❌ | ❌ |
| `operator` | ✅ | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

**Enforcement Points**:
1. **UI**: Hide Command Center tab for non-operators
2. **API Gateway**: Middleware checks role before `/ops/*` endpoints
3. **AI Orchestrator**: Validates role for `/orchestrate` calls

**Implementation**:
```python
# middleware/rbac.py
def require_role(allowed_roles: list[str]):
    def decorator(func):
        async def wrapper(request: Request):
            token = request.headers.get("Authorization")
            claims = verify_jwt(token)
            if not any(role in claims["roles"] for role in allowed_roles):
                raise HTTPException(403, "Insufficient permissions")
            return await func(request)
        return wrapper
    return decorator

@app.get("/ops/health")
@require_role(["operator", "admin"])
async def get_health():
    ...
```

---

### 5.4 Auto-Heal Container

**Convert** `scripts/verify-health.ps1` → containerized service

**Tech Stack**: Python + Docker SDK or bash script in Alpine

**Core Logic**:
```python
# services/autoheal/main.py
import docker
import time
import requests

SERVICES = [
    {"name": "aether-ai-summarizer", "health_url": "http://localhost:9108/health"},
    {"name": "aether-notifications-consumer", "health_url": "http://localhost:9107/health"},
    # ... more services
]

def check_and_heal():
    client = docker.from_env()
    for service in SERVICES:
        try:
            resp = requests.get(service["health_url"], timeout=5)
            if resp.status_code != 200:
                restart_service(client, service["name"])
        except requests.exceptions.RequestException:
            restart_service(client, service["name"])

def restart_service(client, name):
    container = client.containers.get(name)
    container.restart()
    annotate_grafana(f"Auto-healed: {name}")
    print(f"✅ Restarted {name}")

while True:
    check_and_heal()
    time.sleep(120)  # Every 2 minutes
```

**Dockerfile**:
```dockerfile
FROM python:3.11-alpine
RUN pip install docker requests
COPY main.py /app/main.py
CMD ["python", "/app/main.py"]
```

**docker-compose.dev.yml**:
```yaml
  autoheal:
    build: ./services/autoheal
    container_name: aether-autoheal
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - GRAFANA_URL=http://grafana:3000
      - GRAFANA_API_KEY=${GRAFANA_API_KEY}
    restart: unless-stopped
```

---

## 6. Milestones

### **Milestone 1 – Ops Surface** (Week 1-2)
- [ ] Create `/ops/health` aggregator service
- [ ] Add Command Center UI page
- [ ] Show service status grid
- [ ] Display last 20 events from notifications
- [ ] **Deliverable**: Operators can see system health at a glance

**Effort**: 3-5 days  
**Risk**: Low (extends existing patterns)

---

### **Milestone 2 – AI Orchestrator** (Week 3-4)
- [ ] New service `pods/ai_orchestrator`
- [ ] Implement `/orchestrate` endpoint
- [ ] Add provider selection logic (Claude → Ollama)
- [ ] Integrate with ai-summarizer + notifications
- [ ] POST Grafana annotation on anomalies
- [ ] **Deliverable**: AI calls routed intelligently with failover

**Effort**: 1-2 weeks  
**Risk**: Medium (new service, Grafana integration)

---

### **Milestone 3 – RBAC** (Week 5-6)
- [ ] Expand JWT claims to include `roles` array
- [ ] Add role checks in UI (hide ops tabs)
- [ ] Add role checks in API (middleware)
- [ ] Update Keycloak client to include role mappings
- [ ] **Deliverable**: Multi-tenant security enforced uniformly

**Effort**: 1 week  
**Risk**: Medium (requires Keycloak reconfiguration)

---

### **Milestone 4 – Auto-Heal Container** (Week 7)
- [ ] Package `verify-health.ps1` logic into Python container
- [ ] Add Grafana annotation on heal attempts
- [ ] Add Slack webhook notification (optional)
- [ ] Add to `docker-compose.dev.yml`
- [ ] Document operator runbook
- [ ] **Deliverable**: Self-healing platform with audit trail

**Effort**: 3-5 days  
**Risk**: Low (existing logic, just containerized)

---

## 7. Implementation Strategy

### **Phase II-A: Foundation** (Milestones 1-2)
Focus on operator visibility and AI intelligence. These are **high value, low risk**.

### **Phase II-B: Security & Resilience** (Milestones 3-4)
Add RBAC and auto-heal once foundation is stable.

### **Validation Gates**
- ✅ Each milestone has Playwright test coverage
- ✅ No regression in v1.1 test suite
- ✅ Performance benchmarks for orchestrator (<200ms overhead)
- ✅ Security review for RBAC implementation

---

## 8. Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Grafana API changes** | Medium | Version-pin Grafana, abstract annotation client |
| **Orchestrator becomes bottleneck** | High | Keep logic thin, add caching, horizontal scaling |
| **RBAC breaks existing flows** | High | Feature flag: `RBAC_ENABLED=false` for rollback |
| **Auto-heal causes restart loops** | Medium | Cooldown period (5 min), max 3 restarts/hour |

---

## 9. Success Metrics

### **Operator Efficiency**
- Time to identify issue: **<30 seconds** (vs manual log diving)
- False positive heal rate: **<5%**

### **AI Performance**
- Orchestrator overhead: **<200ms**
- Failover success rate: **>95%**
- Annotation lag: **<1 second**

### **Security**
- Unauthorized access attempts: **0** (enforced by RBAC)
- Audit log completeness: **100%** (all AI calls logged)

---

## 10. Future Enhancements (Phase III+)

- **Predictive Scaling**: Use AI usage patterns to pre-scale services
- **Cost Dashboard**: Track LLM API costs per tenant
- **A/B Testing**: Route % of requests to different providers for comparison
- **Smart Routing**: ML model learns best provider per intent type
- **Federation**: Multi-region orchestrator with failover

---

## 11. Dependencies

### **External**
- Grafana 9.x or 10.x (for annotation API)
- Keycloak 20+ (for role management)
- Docker API access (for auto-heal)

### **Internal**
- v1.1.0 UI test mode (already complete)
- Kafka event infrastructure (already complete)
- Prometheus metrics (already in place)

---

## 12. Notes

### **Design Principles**
1. **Don't re-implement what Grafana already gives you** – Use their annotation API
2. **Keep orchestrator thin** – It should decide, not do everything
3. **Add feature flags** – Phase II can be turned off per tenant if needed
4. **Preserve v1.1 simplicity** – Operators shouldn't need Phase II to function

### **Testing Strategy**
- Extend `tests/aetherlink-no-auth.spec.ts` to cover Command Center
- Add `tests/orchestrator.spec.ts` for AI routing logic
- Add `tests/rbac.spec.ts` for permission enforcement
- Keep v1.1 tests passing (regression prevention)

---

## 13. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-11-03 | Start with Ops Surface (M1) | Low risk, high operator value |
| 2025-11-03 | Use FastAPI for orchestrator | Consistent with ai-summarizer |
| 2025-11-03 | Containerize auto-heal | Makes it platform-native |
| 2025-11-03 | Add RBAC in M3 (not M1) | De-risk by proving foundation first |

---

**Status**: Ready for Milestone 1 implementation  
**Next Step**: Create `services/command-center/` and `/ops/health` endpoint

---

**Approvals**:
- [ ] Product Owner
- [ ] Tech Lead
- [ ] Security Review
- [ ] DevOps Review
