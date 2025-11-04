# AetherLink v1.0 Architecture Overview

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER LAYER (Browser)                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  React UI (port 5173)                                             │  │
│  │  • Lead table with filters                                        │  │
│  │  • AI Extract panel (✨ Create New Lead)                         │  │
│  │  • Lead drawer with AI Summary button                            │  │
│  │  • Activity timeline with "📥 Add to timeline"                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP + JWT (Keycloak)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                                │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────┐    │
│  │   Traefik    │────▶│  Keycloak    │────▶│   ApexFlow CRM      │    │
│  │  (port 80)   │     │  (port 8180) │     │    (port 8080)      │    │
│  │              │     │              │     │                     │    │
│  │  Routing +   │     │  Auth +      │     │  • Leads API        │    │
│  │  TLS Term    │     │  Multi-tenant│     │  • Notes API        │    │
│  └──────────────┘     └──────────────┘     │  • Activity API     │    │
│                                             │  • Status Updates   │    │
│                                             └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Emits Events
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EVENT BACKBONE (Kafka)                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Topics:                                                          │  │
│  │  • apexflow.leads.created        (new leads)                     │  │
│  │  • apexflow.leads.status_changed (qualified, won, lost, etc.)    │  │
│  │  • apexflow.leads.note_added     (AI notes, manual notes)        │  │
│  │  • apexflow.leads.assigned       (assignment changes)            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │                           │                           │
          │ consume                   │ consume                   │ consume
          ▼                           ▼                           ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────────┐
│  Events Sink     │      │  Notifications   │      │  (Future Consumers)  │
│  (port 9105-6)   │      │  Consumer        │      │  • Analytics         │
│                  │      │  (port 9107)     │      │  • Webhooks          │
│  • Persists all  │      │                  │      │  • Email/Slack       │
│    events to     │      │  • Rules Engine  │      └──────────────────────┘
│    PostgreSQL    │      │  • Hot Reload    │
│  • Queryable     │      │  • Log Enrich    │
│    history       │      │  • Webhooks      │
└──────────────────┘      └──────────────────┘
                                    │
                                    │ reads rules.yaml
                                    ▼
                          ┌──────────────────┐
                          │   rules.yaml     │
                          │  (volume mount)  │
                          │                  │
                          │  • Live editable │
                          │  • POST /reload  │
                          └──────────────────┘
```

---

## 🤖 AI Intelligence Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI SUMMARIZER SERVICE                               │
│                         (port 9108)                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Endpoints:                                               │  │
│  │                                                                    │  │
│  │  GET  /health                                                     │  │
│  │  GET  /summaries/lead/{id}       ← Summarize lead activity       │  │
│  │  POST /summaries/extract-lead    ← Extract fields from text      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Integration:                                                     │  │
│  │                                                                    │  │
│  │  • Fetches activity from ApexFlow                                │  │
│  │  • Builds structured prompts                                     │  │
│  │  • Calls Claude Sonnet (or stub mode)                            │  │
│  │  • Returns normalized JSON                                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Stub Mode (no API key):                                         │  │
│  │  • Email extraction via regex                                    │  │
│  │  • Sensible defaults (status: "new", tags: ["ai-extracted"])    │  │
│  │  • Always returns valid JSON                                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Claude API
                                    ▼
                          ┌──────────────────┐
                          │  Claude Sonnet   │
                          │  (External API)  │
                          │                  │
                          │  • Summarization │
                          │  • Extraction    │
                          │  • Inference     │
                          └──────────────────┘
```

---

## 🔄 AI Capability Flows

### Flow 1: AI Explains (Summarize Lead)
```
User clicks "✨ AI Summary" in lead drawer
    ↓
UI → GET /summaries/lead/{id}?tenant_id={tenant}
    ↓
AI Summarizer → GET /leads/{id}/activity (from ApexFlow)
    ↓
AI Summarizer → build_prompt(activity)
    ↓
AI Summarizer → Claude API (or stub)
    ↓
AI Summarizer → return summary text
    ↓
UI → displays in purple box
```

### Flow 2: AI Writes Back (Save as Note)
```
User clicks "📥 Add to timeline"
    ↓
UI → POST /leads/{id}/notes { body: aiSummary }
    ↓
ApexFlow → saves note to database
    ↓
ApexFlow → emits apexflow.leads.note_added to Kafka
    ↓
Events Sink → persists to event_journal
    ↓
Notifications Consumer → applies rules (can trigger webhooks)
    ↓
UI → refreshes activity timeline → note appears
```

### Flow 3: AI Extracts & Creates Lead
```
User pastes text in "Create New Lead" panel
    ↓
User clicks "Run AI Extract"
    ↓
UI → POST /summaries/extract-lead { tenant_id, raw_text }
    ↓
AI Summarizer → parse text (stub or Claude)
    ↓
AI Summarizer → return { name, email, company, phone, status, tags }
    ↓
UI → autofills form fields
    ↓
User clicks "✅ Create Lead"
    ↓
UI → POST /leads { name, email, company, phone, status, tags }
    ↓
ApexFlow → saves lead to database
    ↓
ApexFlow → emits apexflow.leads.created to Kafka
    ↓
Events Sink → persists event
    ↓
Notifications Consumer → applies rules (e.g., "notify-on-new-lead")
    ↓
UI → refreshes leads table → new lead appears
    ↓
Panel closes → ready for next lead
```

---

## 📊 Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY LAYER                                 │
│                                                                          │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────────┐ │
│  │  Prometheus  │─────▶│   Grafana    │◀─────│  Loki (planned)      │ │
│  │  (port 9090) │      │  (port 3000) │      │                      │ │
│  │              │      │              │      │  • Structured logs   │ │
│  │  • Metrics   │      │  • Dashboards│      │  • LogQL queries     │ │
│  │  • Alerts    │      │  • Alerts    │      │  • rule= enrichment  │ │
│  └──────────────┘      │  • Queries   │      └──────────────────────┘ │
│                        └──────────────┘                                 │
│                                                                          │
│  Key Queries:                                                           │
│  • {service="ai-summarizer"} |= "POST /summaries"                      │
│  • {service="notifications-consumer"} |= "matched rule="               │
│  • {service="apexflow"} |= "lead.created"                              │
│  • count_over_time({service="notifications"} |= "suppressed" [5m])     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security & Multi-Tenancy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                               │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  JWT Flow:                                                        │  │
│  │                                                                    │  │
│  │  1. User authenticates → Keycloak                                │  │
│  │  2. Keycloak issues JWT with tenant_id claim                     │  │
│  │  3. UI extracts tenant from token: getTenantFromToken()          │  │
│  │  4. All API calls include:                                       │  │
│  │     • Authorization: Bearer {token}                              │  │
│  │     • x-tenant-id: {tenant}                                      │  │
│  │  5. ApexFlow validates token + enforces tenant isolation         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Tenant Isolation:                                                │  │
│  │                                                                    │  │
│  │  • Database: row-level security (RLS) on tenant_id               │  │
│  │  • Events: tenant_id in every Kafka message                      │  │
│  │  • AI calls: tenant_id parameter required                        │  │
│  │  • Rules: can match on tenant_id for per-tenant notifications    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Data Flow Summary

**Write Path** (User creates lead via AI):
```
Browser → ApexFlow → Kafka → [Sink, Notifications] → Grafana
```

**Read Path** (User views lead summary):
```
Browser → AI Summarizer → ApexFlow → Claude → Browser
```

**Feedback Loop** (AI note becomes data):
```
AI Summary → Save as Note → Kafka → Sink → Activity Timeline → Future AI Context
```

---

## 📦 Deployment Map

| Component | Container | Port(s) | Dependencies |
|-----------|-----------|---------|--------------|
| UI | `aether-crm-ui` | 5173 | Keycloak, ApexFlow, AI Summarizer |
| AI Summarizer | `aether-ai-summarizer` | 9108 | ApexFlow, Claude API (optional) |
| ApexFlow CRM | `aether-apexflow` | 8080 | PostgreSQL, Kafka, Keycloak |
| Notifications | `aether-notifications-consumer` | 9107 | Kafka, rules.yaml (volume) |
| Events Sink | `aether-crm-events-sink` | 9105-6 | Kafka, PostgreSQL |
| Keycloak | `aether-keycloak` | 8180 | PostgreSQL |
| Traefik | `aether-traefik` | 80, 8090 | All backend services |
| Kafka | `aether-crm-events` | 9010 | — |
| Grafana | `aether-grafana` | 3000 | Prometheus, Loki |
| Prometheus | `aether-prom` | 9090 | Service exporters |

---

## 🚦 Service Dependencies Graph

```
aether-crm-ui
    ├── aether-keycloak (auth)
    ├── aether-apexflow (CRM data)
    └── aether-ai-summarizer (AI features)

aether-ai-summarizer
    ├── aether-apexflow (activity data)
    └── Claude API (external, optional)

aether-apexflow
    ├── aether-apexflow-db (PostgreSQL)
    ├── aether-kafka (events)
    └── aether-keycloak (auth validation)

aether-notifications-consumer
    ├── aether-kafka (event source)
    └── rules.yaml (volume mount)

aether-crm-events-sink
    ├── aether-kafka (event source)
    └── aether-crm-events-db (PostgreSQL)

aether-grafana
    ├── aether-prom (metrics)
    └── loki (logs, planned)
```

---

## 🔄 Event Types & Schemas

### apexflow.leads.created
```json
{
  "event_type": "lead.created",
  "tenant_id": "acme",
  "lead_id": 42,
  "actor": "jane@acme.com",
  "timestamp": "2025-11-03T10:30:00Z",
  "data": {
    "name": "John Smith",
    "email": "john@novatek.io",
    "company": "NovaTek",
    "status": "new",
    "tags": ["ai-extracted", "inbound"]
  }
}
```

### apexflow.leads.status_changed
```json
{
  "event_type": "lead.status_changed",
  "tenant_id": "acme",
  "lead_id": 42,
  "actor": "jane@acme.com",
  "timestamp": "2025-11-03T11:00:00Z",
  "old_status": "contacted",
  "new_status": "qualified"
}
```

### apexflow.leads.note_added
```json
{
  "event_type": "lead.note_added",
  "tenant_id": "acme",
  "lead_id": 42,
  "actor": "ai-summarizer",
  "timestamp": "2025-11-03T11:15:00Z",
  "note_id": 128,
  "body": "Lead shows strong buying intent. Last interaction was positive. Recommend sending pricing proposal before Friday."
}
```

---

## 📈 Performance Characteristics

| Metric | Target | Current |
|--------|--------|---------|
| UI Load Time | < 2s | ✅ ~1.2s |
| AI Summary Response | < 5s | ✅ ~2.5s (stub) / ~4s (Claude) |
| AI Extract Response | < 3s | ✅ ~1.5s (stub) / ~2.8s (Claude) |
| Lead Creation | < 1s | ✅ ~400ms |
| Event Propagation | < 2s | ✅ ~800ms (ApexFlow → Kafka → Sink) |
| Rule Reload | < 1s | ✅ ~200ms |

---

## 🛡️ Resilience Features

- **Stub Mode**: AI services work without external API keys
- **Hot Reload**: Rules update without restart
- **Event Persistence**: All events stored for replay
- **Health Checks**: Docker healthchecks on all critical services
- **Graceful Degradation**: UI continues to work if AI service is down
- **Tenant Isolation**: Row-level security prevents data leakage
- **Autoheal**: Failed containers restart automatically

---

## 📚 Documentation Index

- **Release Notes**: `/docs/RELEASE_NOTES_v1.0_AetherLink.md`
- **Architecture**: `/docs/ARCHITECTURE.md` (this file)
- **Ops Guide**: `/services/notifications-consumer/OPS-QUICK-CARD.md`
- **Grafana Queries**: `/services/notifications-consumer/GRAFANA-QUERIES.md`
- **AI Summarizer**: `/services/ai-summarizer/README.md`
- **Prompt Engineering**: `/services/ai-summarizer/PROMPT-GUIDE.md`
- **Health Check Script**: `/scripts/verify-health.ps1`

---

**AetherLink v1.0** - Where Intelligence Meets Infrastructure 🚀
