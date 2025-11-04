# CustomerOps AI Agent — Feature Overview

## 🚀 Core Capabilities

### 1. **Conversation Memory** ✅
- Redis-backed conversation history per lead
- Automatic message storage with timestamps and roles
- Semantic recall of past conversations
- **Endpoint**: `GET /v1/lead/{lead_id}/history?limit=20`
- **Feature flag**: `ENABLE_MEMORY=true` (default)

**Example**:
```powershell
# Create a lead
$lead = Invoke-RestMethod -Uri http://localhost:8000/v1/lead -Method Post `
  -ContentType 'application/json' `
  -Body '{"name":"John","phone":"555-1234","details":"need metal roof estimate"}'

# Get conversation history
Invoke-RestMethod "http://localhost:8000/v1/lead/$($lead.lead_id)/history?limit=10"
```

**Response**:
```json
{
  "lead_id": "abc123",
  "items": [
    {
      "ts": 1730350000.123,
      "role": "user",
      "text": "need metal roof estimate"
    }
  ]
}
```

---

### 2. **Lead Enrichment & Scoring** ✅
- AI-powered intent detection (quote, booking, support, etc.)
- Urgency classification (low, medium, high)
- Sentiment analysis (positive, neutral, negative)
- Conversion probability score (0.0-1.0)
- **Feature flag**: `ENABLE_ENRICHMENT=true` (default)

**Automatic on lead creation**:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/v1/lead -Method Post `
  -ContentType 'application/json' `
  -Body '{"name":"Alice","phone":"555-5678","details":"urgent metal roof repair needed today"}'
```

**Enriched Response**:
```json
{
  "lead_id": "xyz789",
  "intent": "quote_request",
  "urgency": "high",
  "sentiment": "neutral",
  "score": 0.92
}
```

---

### 3. **Semantic Lead Search** ✅
- Search across all leads by keyword
- Scores results by keyword frequency
- Preview of conversation context
- **Endpoint**: `GET /v1/search?q=metal%20roof&limit=20`

**Example**:
```powershell
Invoke-RestMethod "http://localhost:8000/v1/search?q=metal%20roof&limit=10" | ConvertTo-Json -Depth 5
```

**Response**:
```json
{
  "query": "metal roof",
  "count": 3,
  "results": [
    {
      "lead_id": "abc123",
      "name": "John",
      "phone": "555-1234",
      "score": 5,
      "preview": "need metal roof estimate for my house..."
    }
  ]
}
```

---

### 4. **Prometheus Metrics & Observability** ✅
- Intent counter: `agent_intent_total{intent, endpoint}`
- Lead enrichment counter: `lead_enrich_total{intent, urgency, sentiment}`
- **Score distribution histogram**: `lead_enrich_score` (buckets: 0.0-1.0)
- **Endpoint**: `GET /metrics`

**Example**:
```powershell
(Invoke-WebRequest -Uri http://localhost:8000/metrics -UseBasicParsing).Content -split "`n" | Select-String "lead_enrich"
```

**Sample metrics**:
```
# HELP lead_enrich_score Distribution of lead enrichment scores
# TYPE lead_enrich_score histogram
lead_enrich_score_bucket{le="0.25"} 2
lead_enrich_score_bucket{le="0.5"} 8
lead_enrich_score_bucket{le="0.75"} 15
lead_enrich_score_bucket{le="0.9"} 42
lead_enrich_score_bucket{le="1.0"} 67
lead_enrich_score_sum 58.32
lead_enrich_score_count 67

# HELP lead_enrich_total Count of lead enrich operations
# TYPE lead_enrich_total counter
lead_enrich_total{intent="quote_request",sentiment="neutral",urgency="high"} 12
lead_enrich_total{intent="booking",sentiment="positive",urgency="medium"} 8
```

---

### 5. **Feature Flags (A/B Testing & Hot-Disable)** ✅
- Runtime toggle for memory and enrichment
- Zero code changes required
- Visible in `/ops/config`

**Configuration**:
```bash
# .env or environment variables
ENABLE_MEMORY=true          # Conversation history storage
ENABLE_ENRICHMENT=true      # AI-powered lead scoring
```

**Check current flags**:
```powershell
Invoke-RestMethod http://localhost:8000/ops/config | Select-Object enable_memory, enable_enrichment
```

**Use cases**:
- **A/B testing**: Run 50% of traffic with enrichment disabled to measure impact
- **Cost control**: Disable enrichment during high-traffic periods
- **Shadow mode**: Collect data without using enrichment in decision logic
- **Incident response**: Hot-disable features if Redis or enrichment service fails

---

### 6. **API Key Auth & Multi-Tenant** ✅
- Per-tenant rate limiting
- Tenant-aware conversation memory
- API key → tenant mapping
- **Config**: `REQUIRE_API_KEY=true`

**Example**:
```bash
API_KEYS=ACME_KEY:acme,BETA_KEY:beta_corp
```

**Usage**:
```powershell
$headers = @{ "x-api-key" = "ACME_KEY" }
Invoke-RestMethod -Uri http://localhost:8000/v1/lead -Headers $headers -Method Post `
  -Body '{"name":"Test","phone":"555-0000"}' -ContentType 'application/json'
```

---

### 7. **Structured Logging & Sentry** ✅
- JSON-structured logs with request IDs
- Sentry error tracking (optional)
- Log level: `LOG_LEVEL=INFO` (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Sample log**:
```json
{
  "event": "lead_created",
  "timestamp": "2025-10-31T12:34:56Z",
  "request_id": "req_abc123",
  "tenant": "acme",
  "lead_id": "xyz789",
  "intent": "quote_request",
  "urgency": "high",
  "level": "info"
}
```

---

## 🎯 Quick Test Script

```powershell
# 1. Health check
Invoke-RestMethod http://localhost:8000/healthz

# 2. Create lead
$lead = Invoke-RestMethod -Uri http://localhost:8000/v1/lead -Method Post `
  -ContentType 'application/json' `
  -Body '{"name":"TestUser","phone":"555-1234","details":"urgent metal roof repair needed"}'

Write-Host "Lead created: $($lead.lead_id) | Score: $($lead.score) | Intent: $($lead.intent)"

# 3. Get conversation history
$history = Invoke-RestMethod "http://localhost:8000/v1/lead/$($lead.lead_id)/history?limit=5"
Write-Host "History items: $($history.items.Count)"

# 4. Search leads
$results = Invoke-RestMethod "http://localhost:8000/v1/search?q=metal%20roof&limit=10"
Write-Host "Search results: $($results.count)"

# 5. Check metrics
$metrics = (Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content
$metrics -split "`n" | Select-String "lead_enrich_total|lead_enrich_score_count"
```

---

## 🔧 Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `dev` | Environment: dev, staging, prod |
| `APP_NAME` | `CustomerOps` | Application name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENABLE_MEMORY` | `true` | Conversation history storage |
| `ENABLE_ENRICHMENT` | `true` | AI-powered lead scoring |
| `REQUIRE_API_KEY` | `false` | Enforce API key auth (auto-true in prod) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `DATABASE_URL` | `sqlite:///./local.db` | Database connection |
| `SENTRY_DSN` | _(optional)_ | Sentry error tracking |
| `API_KEYS` | `""` | Comma-separated keys or tenant:key pairs |

### Rate Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_FALLBACK` | `60/minute` | Default rate limit |
| `RATE_LIMIT_FAQ` | `10/minute` | FAQ endpoint limit |
| `RATE_LIMIT_CHAT` | `30/minute` | Chat endpoint limit |

---

## 📊 Observability Dashboard (Grafana)

**Recommended panels**:
1. **Lead Intent Distribution** — `rate(lead_enrich_total[5m]) by (intent)`
2. **Conversion Score Heatmap** — `lead_enrich_score` histogram
3. **Memory Usage** — Redis memory and key count
4. **Request Rate** — `rate(http_requests_total[1m])`
5. **Error Rate** — `rate(http_requests_total{status=~"5.."}[1m])`

---

## 🧪 Testing

```powershell
# Run all tests
cd pods/customer_ops
$env:PYTHONPATH="c:\Users\jonmi\OneDrive\Documents\AetherLink"
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=api --cov-report=html

# Run specific test suite
python -m pytest tests/test_search_and_history.py -v
python -m pytest tests/test_feature_flags.py -v
```

---

## 🚀 Next Steps

### Immediate Enhancements
- [ ] **PII Redaction** — Redact phone/email in conversation memory (prod safety)
- [ ] **Outcome Tracking** — Add `/v1/lead/{id}/outcome` endpoint (booked, ghosted, etc.)
- [ ] **Batch Enrichment** — Re-enrich old leads to warm histogram
- [ ] **Readiness Check** — Hard-fail `/readyz` if prod env without Postgres

### Advanced Intelligence
- [ ] **Predictive Conversion Model** — Fine-tune scoring with outcome feedback
- [ ] **Multi-Agent Task Queue** — Celery + RQ for follow-ups, CRM sync
- [ ] **Voice Integration** — Whisper + OpenAI Realtime API
- [ ] **Image Analysis** — Roof photo classification (CLIP + OpenCV)

---

## 📚 Resources

- **API Docs**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics
- **Health**: http://localhost:8000/healthz
- **Config**: http://localhost:8000/ops/config

---

**Built with**: FastAPI • Redis • PostgreSQL • Prometheus • Sentry • Docker
