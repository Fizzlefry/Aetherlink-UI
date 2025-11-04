# Quick Wins Validation Scripts

## Overview
Two powerful scripts for validating RAG performance enhancements:

1. **`validate-quick-wins.ps1`** - Fast validation of existing data
2. **`setup-and-validate.ps1`** - Full end-to-end test with sample data ingestion

## Usage

### 🎯 Option 1: Full Setup + Validation (Recommended for First Run)

**Via VS Code Task:**
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type `Tasks: Run Task`
3. Select `Aether: Setup Sample Data + Validate`

**Via Command Line:**
```powershell
.\scripts\setup-and-validate.ps1
```

**What it does:**
1. ✓ Checks API health
2. ✓ Ingests 3 sample documents (storm collar, PII test, audit log)
3. ✓ Waits for embeddings to process
4. ✓ Primes the cache with test queries
5. ✓ Runs full validation suite (11 tests)

Perfect for: Fresh deployments, testing after code changes, demos

---

### ⚡ Option 2: Quick Validation (Existing Data)

**Via VS Code Task:**
1. Press `Ctrl+Shift+P`
2. Type `Tasks: Run Task`
3. Select `Aether: Validate Quick Wins`

**Via Command Line:**
```powershell
# With default settings (uses $env:API_KEY_EXPERTCO)
.\scripts\validate-quick-wins.ps1

# With custom API key
.\scripts\validate-quick-wins.ps1 -ApiKey "your-key-here"

# With custom base URL and timeout
.\scripts\validate-quick-wins.ps1 -BaseUrl "http://localhost:8001" -Timeout 10
```

Perfect for: Quick health checks, regression testing, CI/CD pipelines

## What It Tests

### 1. Health + Basic Metrics
- ✓ API health endpoint responds
- ✓ Metrics endpoint accessible
- ✓ Cache metrics present (aether_rag_cache_*)

### 2. Cache Performance
- ✓ Cold vs hot request speedup (2-4× faster)
- ✓ Cache hit/miss counters increment correctly

### 3. Hybrid Alpha Weighting
- ✓ Search returns score fields
- ✓ Hybrid mode combines semantic + lexical

### 4. Neighbor Chunk Enrichment
- ✓ Citations include multiple sentences from same URL
- ✓ `count` field present in citations (URL grouping)

### 5. Highlights (Character Offsets)
- ✓ Citations include `highlights` array
- ✓ Highlights have valid `{start, end}` offsets

### 6. Rerank + Confidence + PII
- ✓ Reranking works (rerank_used != "none")
- ✓ High-confidence queries return valid answers
- ✓ Low-signal queries abstain (confidence < 0.25)

## Output Format

```
╔══════════════════════════════════════════════════════╗
║  AetherLink RAG Performance Quick Wins Validation   ║
╚══════════════════════════════════════════════════════╝
ℹ Base URL: http://localhost:8000
ℹ API Key: test-key...
ℹ Timeout: 5s

━━━ 1.1 Health Check ━━━
ℹ   Uptime: 7m 35s
ℹ   DB: ok
✓ 1.1 Health Check passed

━━━ 2.1 Cache Speedup (Cold vs Hot) ━━━
ℹ   Cold: 234ms | Hot: 87ms | Speedup: 2.69×
✓   Cache is working (hot < cold)
✓ 2.1 Cache Speedup (Cold vs Hot) passed

...

╔══════════════════════════════════════════════════════╗
║                  VALIDATION SUMMARY                  ║
╚══════════════════════════════════════════════════════╝

  ✓ ALL TESTS PASSED (11/11)

  🎉 Quick wins are live and working!
```

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Troubleshooting

### No API Key
```
✗ No valid API key found. Cannot proceed.
```
**Fix**: Set `$env:API_KEY_EXPERTCO` or pass `-ApiKey` parameter

### Connection Refused
```
✗ 1.1 Health Check failed: Unable to connect to the remote server
```
**Fix**: Check if API is running:
```powershell
docker compose ps
docker logs aether-customer-ops --tail 100
```

### Cache Metrics Not Found
```
⚠ Cache metrics not found (might be zero if no requests yet)
```
**Fix**: This is normal on fresh restart. Make a few requests first:
```powershell
curl.exe "http://localhost:8000/answer?q=test" -H "x-api-key: your-key"
```

### No Highlights Found
```
⚠ No highlights found (might be no matching sentences)
```
**Fix**: This happens when the knowledge base is empty or query doesn't match any content. Ingest some sample documents first.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_EXPERTCO` | - | Primary API key for requests |
| `API_ADMIN_KEY` | - | Fallback admin key |
| `ANSWER_CACHE_TTL` | 60 | Cache TTL in seconds |
| `HYBRID_ALPHA` | 0.6 | Semantic weight (0.0-1.0) |

## Related Files

- Task definition: `.vscode/tasks.json`
- Performance docs: `PERFORMANCE_QUICK_WINS.md`
- Main API: `pods/customer_ops/api/main.py`

## Advanced Usage

### Run Only Specific Sections
Edit the script and comment out test blocks you don't need:

```powershell
# Comment out a test block
# Test-Endpoint "5.1 Citations Include Highlights" {
#     ...
# }
```

### Increase Timeout for Slow Connections
```powershell
.\scripts\validate-quick-wins.ps1 -Timeout 30
```

### Test Against Remote Server
```powershell
.\scripts\validate-quick-wins.ps1 -BaseUrl "https://api.example.com" -ApiKey "prod-key"
```

## Sample Documents

The `setup-and-validate.ps1` script ingests 3 carefully crafted test documents:

### 1. Storm Collar Installation Guide (~1500 words)
- **Purpose**: Multi-chunk document for testing neighbor windowing
- **Features**: Step-by-step instructions, materials list, troubleshooting
- **Tests**: Neighbor chunk enrichment, citation grouping, highlights
- **Example Query**: "how to install storm collar"

### 2. PII Test Document (~200 words)
- **Purpose**: Contains PII placeholders ([EMAIL], [PHONE], [CARD])
- **Features**: Support case with redacted sensitive data
- **Tests**: PII guard (should block or refuse answers containing PII)
- **Example Query**: "customer support case 45231"

### 3. System Audit Log (~500 words)
- **Purpose**: Structured log data for confidence testing
- **Features**: Timestamps, metrics, performance notes
- **Tests**: Low-confidence queries, lexical search, date-based queries
- **Example Query**: "system performance metrics october"

All documents are automatically ingested with proper metadata and tags for optimal retrieval testing.

## Pro Tips

### Pre-flight Checklist
Before running validation:

```powershell
# 1. Set API key
$env:API_KEY_EXPERTCO = "your-editor-key"

# 2. Check API is up
docker compose -f pods\customer_ops\docker-compose.yml ps

# 3. Confirm metrics endpoint
curl.exe -sS --max-time 3 http://localhost:8000/metrics | Select-String aether_rag_cache
```

### Re-prime Cache
If cache metrics show zero hits:

```powershell
# Run same query twice
curl.exe "http://localhost:8000/answer?q=storm%20collar&mode=hybrid" -H "x-api-key: $env:API_KEY_EXPERTCO"
curl.exe "http://localhost:8000/answer?q=storm%20collar&mode=hybrid" -H "x-api-key: $env:API_KEY_EXPERTCO"
```

### Quick Triage
If tests fail:

```powershell
# Check logs
docker compose -f pods\customer_ops\docker-compose.yml logs --tail=100 api

# Verify health
curl.exe http://localhost:8000/health

# Check API key
echo $env:API_KEY_EXPERTCO
```

### Keyboard Shortcut (Optional)
Add a keybinding for instant validation:

1. VS Code → Keyboard Shortcuts
2. Search "Run Task"
3. Set your preferred key combo (e.g., `Ctrl+Shift+T`)
4. Now you can validate with one keystroke!

## CI/CD Integration

### GitHub Actions
```yaml
- name: Setup Sample Data and Validate
  run: |
    $env:API_KEY_EXPERTCO = "${{ secrets.API_KEY }}"
    .\scripts\setup-and-validate.ps1
  shell: pwsh
```

### Quick Validation Only
```yaml
- name: Validate RAG Quick Wins
  run: |
    $env:API_KEY_EXPERTCO = "${{ secrets.API_KEY }}"
    .\scripts\validate-quick-wins.ps1
  shell: pwsh
```

Exit code 0 = success, 1 = failure (workflow will fail on test failures).

## Testing Specific Features

### Cache Metrics
```powershell
# After making queries, check counters
curl.exe http://localhost:8000/metrics | Select-String "aether_rag_cache_(hits|misses)_total"
```

### Citation Highlights
```powershell
$r = curl.exe "http://localhost:8000/answer?q=storm%20collar&mode=hybrid&rerank=true" `
  -H "x-api-key: $env:API_KEY_EXPERTCO" | ConvertFrom-Json

# Inspect first citation
$r.citations[0] | Format-List url, count, highlights
```

### Neighbor Enrichment
```powershell
# Look for citations with count > 1 (multiple sentences from same URL)
$r.citations | Where-Object { $_.count -gt 1 } | Format-List url, count
```

### PII Guard
```powershell
# Query the PII document (should abstain or redact)
curl.exe "http://localhost:8000/answer?q=customer%20support%20case" `
  -H "x-api-key: $env:API_KEY_EXPERTCO"
```
