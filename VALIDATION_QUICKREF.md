# Quick Wins Validation - Quick Reference Card

## 🚀 Run Validation

### First Time / Fresh Deploy
```powershell
# VS Code: Ctrl+Shift+P → Tasks: Run Task → "Aether: Setup Sample Data + Validate"
# Or terminal:
.\scripts\setup-and-validate.ps1
```
✓ Ingests sample docs + runs all tests (~30 seconds)

### Quick Check (Existing Data)
```powershell
# VS Code: Ctrl+Shift+P → Tasks: Run Task → "Aether: Validate Quick Wins"
# Or terminal:
.\scripts\validate-quick-wins.ps1
```
⚡ Fast validation (~10 seconds)

---

## 📋 Pre-flight Checklist

```powershell
# 1. Set API key
$env:API_KEY_EXPERTCO = "your-editor-key"

# 2. Check API is up
docker compose -f pods\customer_ops\docker-compose.yml ps

# 3. Verify health
curl.exe http://localhost:8000/health
```

---

## 🎯 What Gets Tested

| # | Feature | What It Checks |
|---|---------|----------------|
| 1.x | **Health + Metrics** | API up, metrics endpoint, cache counters |
| 2.x | **Cache Performance** | Hot 2-4× faster than cold, counters increment |
| 3.x | **Hybrid Weighting** | Score fields present, α blending works |
| 4.x | **Neighbor Chunks** | Citations show `count > 1` for same URL |
| 5.x | **Highlights** | Character offsets `{start, end}` present |
| 6.x | **Rerank + Guards** | Rerank works, confidence thresholds, PII blocks |

---

## ✅ Expected Results

```
✓ ALL TESTS PASSED (11/11)
🎉 Quick wins are live and working!
```

**Pass criteria:**
- Health: API responds, DB OK
- Cache: Hot request faster than cold
- Metrics: aether_rag_cache_* counters exist
- Citations: Have `count` and `highlights` fields
- Confidence: High signal answers, low signal abstains

---

## 🐛 Troubleshooting

### Cache Metrics Not Found
```powershell
# Make a few requests first
curl.exe "http://localhost:8000/answer?q=test" -H "x-api-key: $env:API_KEY_EXPERTCO"
```

### Connection Refused
```powershell
# Check containers
docker compose -f pods\customer_ops\docker-compose.yml ps

# Check logs
docker compose -f pods\customer_ops\docker-compose.yml logs --tail=50 api
```

### No Highlights
```powershell
# Ingest sample data first
.\scripts\setup-and-validate.ps1
```

### Wrong API Key
```powershell
# Check current key
echo $env:API_KEY_EXPERTCO

# Set it
$env:API_KEY_EXPERTCO = "your-key-here"
```

---

## 📊 Manual Testing

### Cache Hit Rate
```powershell
# Same query twice
curl.exe "http://localhost:8000/answer?q=storm%20collar&mode=hybrid" -H "x-api-key: $env:API_KEY_EXPERTCO"
curl.exe "http://localhost:8000/answer?q=storm%20collar&mode=hybrid" -H "x-api-key: $env:API_KEY_EXPERTCO"

# Check metrics
curl.exe http://localhost:8000/metrics | Select-String "aether_rag_cache_hits_total"
```

### Citation Features
```powershell
$r = curl.exe "http://localhost:8000/answer?q=storm%20collar%20installation&mode=hybrid&rerank=true" `
  -H "x-api-key: $env:API_KEY_EXPERTCO" | ConvertFrom-Json

# Inspect
$r.citations | Format-List url, count, highlights
```

### Neighbor Enrichment
```powershell
# Multi-sentence citations (count > 1)
$r.citations | Where-Object { $_.count -gt 1 }
```

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_EXPERTCO` | - | Primary API key |
| `API_ADMIN_KEY` | - | Fallback admin key |
| `ANSWER_CACHE_TTL` | 60 | Cache TTL (seconds) |
| `HYBRID_ALPHA` | 0.6 | Semantic weight (0.0-1.0) |

Change and restart:
```powershell
$env:ANSWER_CACHE_TTL = "120"
docker compose restart api
```

---

## 📁 Sample Documents

Ingested by `setup-and-validate.ps1`:

1. **Storm Collar Guide** (~1500 words)
   - Test: Neighbor chunks, highlights, grouping
   - Query: "how to install storm collar"

2. **PII Test Document** (~200 words)
   - Test: PII guard (should block)
   - Query: "customer support case"

3. **Audit Log** (~500 words)
   - Test: Confidence scoring, lexical search
   - Query: "system performance metrics"

---

## ⌨️ Keyboard Shortcut (Optional)

**Setup:**
1. VS Code → Keyboard Shortcuts
2. Search "Run Task"
3. Bind to `Ctrl+Shift+T` (or your preference)

**Use:**
- `Ctrl+Shift+T` → Select task → Instant validation!

---

## 🎓 Output Legend

| Symbol | Meaning |
|--------|---------|
| ✓ | Test passed |
| ✗ | Test failed |
| ℹ | Information |
| ⚠ | Warning (non-critical) |

**Colors:**
- Green = Success
- Red = Failure
- Cyan = Info
- Yellow = Warning
- Magenta = Step header

---

## 📞 Quick Help

**Tasks in VS Code:**
- `Ctrl+Shift+P` → "Tasks: Run Task"
- Select: `Aether: Setup Sample Data + Validate`
- Or: `Aether: Validate Quick Wins`

**From Terminal:**
```powershell
# Full setup
.\scripts\setup-and-validate.ps1

# Quick validate
.\scripts\validate-quick-wins.ps1
```

**Check logs:**
```powershell
docker compose -f pods\customer_ops\docker-compose.yml logs --tail=100 api
```

**Restart API:**
```powershell
docker compose restart api
```

---

**Last Updated:** November 2025  
**Version:** 1.0 (Initial quick wins deployment)
