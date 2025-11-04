# 🖥️ AetherLink Control Plane - Option D

## Overview

Option D provides a **zero-dependency web dashboard** and **human-friendly APIs** for managing your AetherLink agent. No React, no build system—just a single HTML file served by FastAPI.

## Features

### 1. Web Dashboard (`http://localhost:8000/`)

A single-page control panel with:

- **🔍 Health & Metrics**
  - Live health status indicator
  - Active tenant count
  - One-click metrics viewer

- **🧪 Streaming Chat UI**
  - Test chat with JSON or SSE streaming
  - Switch providers (Ollama/OpenAI/Gemini)
  - Live tool execution display
  - Error event visualization

- **📚 Knowledge Management**
  - Ingest text directly from UI
  - List knowledge entries
  - Search within knowledge
  - Export to CSV

- **🧠 Embedding Explorer**
  - 2D projection of knowledge clusters
  - UMAP or PCA fallback
  - Download visualization data as CSV
  - Interactive preview

### 2. Knowledge Admin Endpoints

#### `GET /knowledge/list`
List knowledge entries for your tenant with optional text search.

**Query Parameters:**
- `limit` (int, default: 50) - Max entries to return
- `q` (str, optional) - Text search query

**Response:**
```json
{
  "ok": true,
  "count": 2,
  "items": [
    {
      "id": 123,
      "source": "crm-export",
      "text": "Lead 123 (Acme Inc.) requires...",
      "created_at": 1699123456.789
    }
  ]
}
```

#### `DELETE /knowledge/delete`
Delete specific knowledge entries by ID.

**Query Parameters:**
- `ids` (List[str]) - Comma-separated IDs to delete

**Response:**
```json
{
  "ok": true,
  "deleted": 2
}
```

#### `GET /knowledge/export`
Export all knowledge entries as CSV.

**Response:** `text/csv` with columns: id, source, text, created_at

### 3. Embedding Explorer Endpoints

#### `GET /embed/project`
Project embeddings to 2D using UMAP (if available) or PCA fallback.

**Query Parameters:**
- `k` (int, default: 200) - Max points to project

**Response:**
```json
{
  "ok": true,
  "n": 150,
  "points": [
    {
      "id": 123,
      "source": "crm-export",
      "text": "Lead 123 (Acme Inc.)...",
      "x": -2.34,
      "y": 1.56
    }
  ]
}
```

**Notes:**
- Requires numpy installed
- Uses UMAP if `umap-learn` is installed, otherwise falls back to PCA
- Coordinates are normalized

#### `GET /embed/project.csv`
Export 2D projection as CSV for external visualization tools.

**Response:** `text/csv` with columns: id, source, x, y, text

### 4. URL Ingestion

#### `POST /knowledge/ingest-url`
Ingest knowledge from a URL with automatic HTML text extraction.

**Query Parameters:**
- `url` (str, required) - URL to fetch
- `source` (str, default: "url") - Source tag

**Response:**
```json
{
  "ok": true,
  "ingested_chunks": 12,
  "source": "url",
  "tenant": "public"
}
```

**Notes:**
- Strips HTML tags, scripts, styles
- Unescapes HTML entities
- Timeout: 10 seconds
- Chunks text using `_simple_chunk()` (800 char max)

### 5. Golden Eval Harness

#### `POST /evals/run`
Run golden test evaluations against the chat endpoint.

**Response:**
```json
{
  "ok": true,
  "n": 2,
  "passed": 2,
  "latency_ms": 1234.5,
  "results": [
    {
      "id": "lead-123",
      "ok": true,
      "reason": null
    },
    {
      "id": "schedule",
      "ok": false,
      "reason": "expected tool: schedule_inspection"
    }
  ]
}
```

**Configuration:**
Tests are defined in `pods/customer_ops/evals/golden.yml`:

```yaml
version: 1
dataset:
  - id: lead-123
    question: "What do we know about Lead 123?"
    must_contain: ["Lead 123", "Acme", "priority"]
  
  - id: schedule
    question: "Please schedule an inspection for job J-1001 next week."
    expect_tool: "schedule_inspection"
```

**Validation Rules:**
- `must_contain`: All strings must appear in response (case-insensitive)
- `expect_tool`: Tool name must appear in response

## VS Code Tasks

Run via **Terminal → Run Task**:

### `AetherLink: Open Dashboard`
Opens `http://localhost:8000/` in your default browser.

### `AetherLink: Run Golden Evals`
Executes `/evals/run` and displays results in JSON format.

```powershell
# Example output:
{
  "ok": true,
  "n": 2,
  "passed": 2,
  "latency_ms": 1234.5,
  "results": [...]
}
```

## Dependencies

Added to `requirements.txt`:

```text
PyYAML>=6.0.1                 # for evals/golden.yml parsing
numpy>=1.24.0                 # for vector operations
umap-learn>=0.5.5             # optional: better 2D projections
```

**Install:**
```powershell
cd pods/customer_ops
pip install -r requirements.txt
```

Or rebuild Docker:
```powershell
docker compose down
docker compose up --build -d
```

## Architecture

### UI Component (`api/ui.py`)
- Single FastAPI router with one endpoint: `GET /`
- Returns self-contained HTML with embedded CSS and JavaScript
- Uses native `fetch()` API for all requests
- Custom EventSource polyfill for SSE with POST support
- No external dependencies (no CDN, no npm)

### Eval Harness (`api/evals.py`)
- FastAPI router with `POST /evals/run`
- Uses `fastapi.testclient.TestClient` for local loopback (no network overhead)
- Loads tests from `evals/golden.yml`
- Validates responses against constraints
- Returns pass/fail with detailed reasons

### Vector Store Extensions (`api/vector_store.py`)
New methods added to `SQLiteVectorStore`:
- `list(tenant, limit, q)` - Query entries with text search
- `delete(tenant, ids)` - Bulk delete by IDs
- `export_csv(tenant)` - CSV export
- `project_umap(tenant, k)` - 2D projection with UMAP/PCA
- `project_umap_csv(tenant, k)` - CSV export of projection

## Security

All endpoints respect:
- **Tenant isolation**: Knowledge is scoped by API key
- **PII redaction**: Applied before model calls
- **Rate limiting**: Same limits as other endpoints
- **Auth required**: Must provide `x-api-key` header

## Example Workflows

### 1. Ingest from URL and visualize
```powershell
# Ingest
$h=@{'x-api-key'='test-key'}
Invoke-RestMethod "http://localhost:8000/knowledge/ingest-url?url=https://example.com" -Headers $h -Method Post

# Visualize
Invoke-RestMethod "http://localhost:8000/embed/project?k=100" -Headers $h | ConvertTo-Json -Depth 5

# Export for external tools
Invoke-WebRequest "http://localhost:8000/embed/project.csv" -Headers $h -OutFile knowledge_map.csv
```

### 2. Run golden evals in CI/CD
```yaml
# .github/workflows/test.yml
- name: Run Golden Evals
  run: |
    curl -X POST http://localhost:8000/evals/run \
      -H "x-api-key: ${{ secrets.API_KEY }}" \
      -o results.json
    
    # Fail if not all tests passed
    PASSED=$(jq -r '.passed' results.json)
    TOTAL=$(jq -r '.n' results.json)
    if [ "$PASSED" != "$TOTAL" ]; then
      echo "Only $PASSED/$TOTAL tests passed"
      exit 1
    fi
```

### 3. Knowledge lifecycle management
```powershell
# List all knowledge
$h=@{'x-api-key'='test-key'}
$items = (Invoke-RestMethod "http://localhost:8000/knowledge/list?limit=100" -Headers $h).items

# Delete old entries
$old_ids = $items | Where-Object { $_.created_at -lt (Get-Date).AddDays(-30).ToUnixTimeSeconds() } | Select-Object -ExpandProperty id
Invoke-RestMethod "http://localhost:8000/knowledge/delete?ids=$($old_ids -join ',')" -Headers $h -Method Delete

# Export for backup
Invoke-WebRequest "http://localhost:8000/knowledge/export" -Headers $h -OutFile "knowledge_backup_$(Get-Date -Format 'yyyy-MM-dd').csv"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Dashboard shows 404 | Ensure routers are mounted: `app.include_router(ui_router)` |
| Embedding explorer fails | Install numpy: `pip install numpy` |
| UMAP import error | Optional dependency. Uses PCA fallback automatically |
| Evals fail to load | Check `evals/golden.yml` exists and is valid YAML |
| Tenant count shows "?" | Add `x-api-key` header in dashboard input field |
| SSE stream hangs | Check model provider is running and configured |

## Future Enhancements (Optional)

These can be added later without breaking changes:

1. **Grafana JSON Dashboard**
   - Pre-wired to Prometheus metrics
   - Beautiful time-series charts

2. **Auth'd Dashboard**
   - Tenant-scoped view vs admin view
   - Role-based access control

3. **File Upload**
   - PDFs → text extraction + chunking
   - Drag-and-drop ingestion

4. **Readability Extractor**
   - Better article extraction from URLs
   - Remove boilerplate/ads/navigation

5. **DuckDB Backend**
   - Replace SQLite for large knowledge bases
   - Faster vector operations

6. **Real-time UMAP**
   - Live updates as knowledge grows
   - Interactive scatter plot with zoom/pan

## API Reference Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Web dashboard UI |
| `/knowledge/list` | GET | List entries with search |
| `/knowledge/delete` | DELETE | Bulk delete by IDs |
| `/knowledge/export` | GET | CSV export |
| `/knowledge/ingest-url` | POST | Fetch and ingest URL |
| `/embed/project` | GET | 2D embedding projection |
| `/embed/project.csv` | GET | CSV export of projection |
| `/evals/run` | POST | Run golden test suite |

All endpoints require `x-api-key` header for tenant authentication.

---

**You now have a complete control plane for your AI agent! 🎉**
