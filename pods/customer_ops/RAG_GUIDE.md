# RAG Guide

## What this adds
- `/knowledge/ingest` (tenant-protected): store chunks + embeddings in SQLite
- Retrieval in `/chat` and `/chat/stream`: top-k cosine search adds context
- Metrics: `rag_retrieval_latency_ms`, `rag_hits_total{tenant}`

## Config
- `RAG_ENABLED` (default `true`)
- `RAG_TOP_K` (default `4`)
- `RAG_MIN_SCORE` (default `0.15`)
- `EMBED_PROVIDER` (`openai` | `gemini` | `ollama`)
- `EMBED_MODEL` (default `text-embedding-3-small` for OpenAI)

## Quick Start
```powershell
$env:API_KEY_EXPERTCO="ABC123"
$env:RAG_ENABLED="true"
$env:EMBED_PROVIDER="openai"
$env:EMBED_MODEL="text-embedding-3-small"
.\makefile.ps1 up

# Ingest:
# VS Code → Tasks: Run Task → "AetherLink: Ingest Sample Knowledge"

# Ask:
$h=@{'x-api-key'=$env:API_KEY_EXPERTCO}
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h -Body '{"message":"What about Lead 123?"}' -ContentType 'application/json'
```

## Provider Configuration

### OpenAI (Recommended)
Best embedding quality. Requires API key:
```powershell
$env:EMBED_PROVIDER="openai"
$env:EMBED_MODEL="text-embedding-3-small"
$env:OPENAI_API_KEY="sk-..."
```

### Ollama (Local)
Free, runs locally. Install Ollama and pull the model:
```powershell
ollama pull nomic-embed-text
$env:EMBED_PROVIDER="ollama"
$env:EMBED_MODEL="nomic-embed-text"
$env:OLLAMA_BASE_URL="http://localhost:11434"
```

### Gemini
Placeholder implementation (uses hash-based pseudo-embeddings). To enable real Gemini embeddings, wire the Embeddings API and set:
```powershell
$env:EMBED_PROVIDER="gemini"
$env:GOOGLE_API_KEY="..."
```

## Ingestion

Send text to `/knowledge/ingest`:
```powershell
$h=@{'x-api-key'='YOUR_KEY'}
$body=@{
    text='Lead 123 (Acme Inc.) requires inspection next week. Contact: ops@acme.com'
    source='crm-export-2024'
} | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/knowledge/ingest -Method Post -Headers $h -Body $body -ContentType 'application/json'
```

Response:
```json
{
  "ok": true,
  "ingested_chunks": 1,
  "source": "crm-export-2024"
}
```

## Retrieval

Retrieval happens automatically when you chat. Context is prepended to the prompt if relevant chunks are found (score >= `RAG_MIN_SCORE`).

Example:
```powershell
$h=@{'x-api-key'='YOUR_KEY'}
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h -Body '{"message":"Tell me about Lead 123"}' -ContentType 'application/json'
```

The agent will receive:
```
Use the following context if relevant:

[score=0.856 source=crm-export-2024]
Lead 123 (Acme Inc.) requires inspection next week. Contact: ops@acme.com

---

User: Tell me about Lead 123
```

## Metrics

After making requests, check Prometheus metrics:
```powershell
(Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content -split "`n" | Select-String "rag_"
```

- `rag_retrieval_latency_ms` - Summary histogram of retrieval latency
- `rag_hits_total{tenant}` - Counter of retrieved chunks per tenant

## Design Notes

- **Fail-open**: If RAG retrieval fails, chat still succeeds (no coupling to outages)
- **Multi-tenant**: Each tenant's knowledge is isolated by tenant key
- **Chunking**: Simple line/paragraph chunker (max 800 chars per chunk)
- **Storage**: SQLite vector store (cosine similarity search)
- **Context injection**: Top-K chunks prepended to prompt with scores and sources

## Future Enhancements

1. **File Ingestion**: PDF/Docx → text extraction
2. **Advanced Chunking**: Semantic chunking, overlapping windows
3. **Hybrid Search**: Combine vector + keyword search
4. **Relevance Evals**: CI tests for retrieval accuracy
5. **Real Gemini Embeddings**: Replace pseudo-embeddings with Gemini API
