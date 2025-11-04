# 🚀 AetherLink CustomerOps - Quick Start Guide

## ✅ What's Live Now

Your agent has **all five enterprise features** operational:

### **Option A: Streaming + Tool Calling** ✅
- SSE streaming via `/chat/stream`
- Two tools: `lead_lookup`, `schedule_inspection`
- Provider-aware (OpenAI full support, Gemini/Ollama graceful fallback)
- Metrics: `agent_tool_call`, latency tracking

### **Option B: Error Taxonomy + PII Guard** ✅
- Unified JSON errors: `{"error": {"type", "message", "trace_id"}}`
- SSE error events: `event: error` with same format
- PII redaction: emails/phones/SSNs scrubbed before model calls
- Metrics: `errors_total{type,endpoint}`, `pii_redactions_total`

### **Option C: RAG + Evals** ✅
- Knowledge ingestion: `/knowledge/ingest` ✅ **VERIFIED WORKING**
- Multi-tenant vector store (SQLite + cosine similarity)
- Auto-retrieval in `/chat` and `/chat/stream`
- Metrics: `rag_retrieval_latency_ms`, `rag_hits_total{tenant}`
- Three embedding providers: OpenAI, Ollama, Gemini (with fallback)

### **Option D: Human-Friendly Control Plane** ✅
- Zero-dependency web dashboard at `http://localhost:8000/`
- Health monitoring + live tenant count
- Streaming chat UI with SSE
- Knowledge management (ingest, list, export CSV)
- 2D embedding explorer (UMAP/PCA visualization)
- URL ingestion for quick knowledge capture
- Golden eval harness (`/evals/run`)
- VS Code one-click tasks

### **Option E: Secure + File Upload** ✅ **NEW!**
- 🔐 Admin-protected dashboard (x-admin-key required)
- 📤 File upload ingestion (PDF, TXT, MD, DOCX)
- Automatic text extraction from PDFs
- Drag-drop UI for non-technical users
- Production-ready security

## 🎯 Quick Start (60 seconds)

### Pick Your LLM Provider:

#### **Option 1: Ollama (Local & Free)** ⭐ Recommended for dev
```powershell
# Install from https://ollama.com if needed
ollama serve  # Keep running in separate terminal

# In your main terminal:
ollama pull llama3
$env:MODEL_PROVIDER="ollama"
$env:MODEL_NAME="llama3"
$env:OLLAMA_BASE_URL="http://localhost:11434"

cd C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\customer_ops
docker compose up -d
```

#### **Option 2: OpenAI**
```powershell
$env:MODEL_PROVIDER="openai"
$env:MODEL_NAME="gpt-4o-mini"
$env:OPENAI_API_KEY="sk-YOUR-KEY"

cd C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\customer_ops
docker compose up -d
```

#### **Option 3: Gemini**
```powershell
$env:MODEL_PROVIDER="gemini"
$env:MODEL_NAME="gemini-1.5-pro"
$env:GOOGLE_API_KEY="YOUR-KEY"

cd C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\customer_ops
docker compose up -d
```

## 🧪 Test End-to-End

```powershell
# 1. Health check
Invoke-WebRequest http://localhost:8000/health

# 2. Ingest knowledge
$h=@{'x-api-key'='test-key'; 'Content-Type'='application/json'}
$body=@{text='Lead 123 (Acme Inc.) requires inspection next week. Contact: ops@acme.com. Priority: High. Estimated value: $50,000.'; source='crm-export'} | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/knowledge/ingest -Method Post -Headers $h -Body $body | ConvertTo-Json -Depth 5

# 3. Ask about it (RAG → model with context)
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h -Body '{"message":"What do you know about Lead 123?"}' -ContentType 'application/json' | ConvertTo-Json -Depth 5

# 4. Test tool calling
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h -Body '{"message":"Look up lead 123"}' -ContentType 'application/json' | ConvertTo-Json -Depth 5

# 5. Test streaming
$b=@{message='Tell me about Lead 123 and schedule an inspection'} | ConvertTo-Json
Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8000/chat/stream -Method Post -Headers $h -Body $b

# 6. Check metrics
(Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content -split "`n" | Select-String "rag_|errors_|pii_"
```

## 📊 VS Code Tasks (One-Click)

All available in **Terminal → Run Task**:
- `AetherLink: Open Dashboard` ⭐ **NEW! Web UI**
- `AetherLink: Run Golden Evals` ⭐ **NEW! Test harness**
- `AetherLink: Health Check`
- `AetherLink: Ingest Sample Knowledge` ⭐ Quick RAG test
- `AetherLink: Chat Smoke` ⭐ Test basic chat
- `AetherLink: Chat Stream Smoke` ⭐ Test streaming + tools
- `AetherLink: Check Metrics`
- `AetherLink: List Tenants`
- `AetherLink: Reload Auth Keys`

## 🔍 What You'll See

### Successful RAG Response:
```json
{
  "request_id": "abc-123",
  "reply": "Based on the information I have, Lead 123 is Acme Inc. They require an inspection next week. The contact email is ops@acme.com, and it's marked as high priority with an estimated value of $50,000.",
  "latency_ms": 234.5,
  "provider": "ollama",
  "model": "llama3"
}
```

### Successful Tool Call:
```json
{
  "request_id": "def-456",
  "tool_result": {
    "lead_id": "123",
    "name": "Sample Lead",
    "email": "sample@example.com",
    "status": "qualified",
    "notes": "High-value prospect"
  },
  "latency_ms": 123.4,
  "provider": "ollama",
  "model": "llama3"
}
```

### SSE Stream:
```
event: text
data: Based on the context, Lead 123...

event: text
data: is Acme Inc...

event: tool_result
data: {"ok":true,"date":"2025-11-08","job_id":"J-1001","confirmation":"SCHEDULED"}

event: done
data: ok
```

## 📈 Metrics to Watch

```powershell
# RAG performance
rag_retrieval_latency_ms_sum / rag_retrieval_latency_ms_count

# RAG usage
rag_hits_total{tenant="public"}

# Error tracking
errors_total{type="internal_error",endpoint="/chat"}

# PII scrubbing
pii_redactions_total

# Tool usage
# (logged as "agent_tool_call" events in JSON logs)
```

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| `401/403` on API calls | Add header: `'x-api-key'='test-key'` |
| Model connection error | Check `$env:MODEL_PROVIDER` is set and Ollama is running |
| RAG metrics show 0 | Ingest data first, then ask a question about it |
| `OPENAI_API_KEY missing` | Change `EMBED_PROVIDER` to `gemini` (has fallback) or set the key |
| Port 8000 already in use | `docker compose down` first |

## 📚 Documentation

- **RAG Details**: `pods/customer_ops/RAG_GUIDE.md`
- **Error Handling**: Check README section "Error Handling & Observability"
- **Config Reference**: `pods/customer_ops/api/config.py`

## 🖥️ Option D: Web Dashboard

Visit **`http://localhost:8000/`** for:
- **Health & Metrics**: Live health status + tenant count
- **Streaming Chat UI**: Test chat with SSE or JSON, switch providers
- **Knowledge Management**: Ingest text, list entries, export CSV
- **Embedding Explorer**: Visualize knowledge clusters in 2D (UMAP/PCA)
- **URL Ingestion**: `POST /knowledge/ingest-url?url=https://...`
- **Golden Evals**: `POST /evals/run` (tests against `evals/golden.yml`)

All features respect tenant isolation and PII redaction.

## 🎉 What You've Built

An **enterprise-grade conversational AI agent** with:
- ✅ Real-time SSE streaming
- ✅ Function/tool calling (2 tools ready, extensible)
- ✅ Unified error taxonomy + PII redaction
- ✅ RAG knowledge retrieval (multi-tenant, vector search)
- ✅ Zero-dependency web control panel with embedding visualization
- ✅ Golden test harness for CI/CD validation
- ✅ **Admin-secured dashboard with RBAC**
- ✅ **File upload ingestion (PDF/DOCX/TXT/MD)**
- ✅ Prometheus metrics everywhere
- ✅ Multi-provider support (OpenAI/Gemini/Ollama)
- ✅ Production-ready auth, rate limiting, request tracking
- ✅ Fail-safe design (RAG/tools fail gracefully)

**You're ready for production! 🚀**
