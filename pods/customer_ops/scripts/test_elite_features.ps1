# Elite Features Verification Script
# Tests: memory, enrichment, search, histogram, feature flags

Write-Host "🚀 CustomerOps AI Agent — Elite Features Test" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"

# Test 1: Health Check
Write-Host "[1/7] Health check..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod "$baseUrl/healthz" -TimeoutSec 5
    if ($health.ok) {
        Write-Host "  ✅ API is healthy (DB: $($health.db), Redis: $($health.redis))" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  API responded but not fully healthy" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Health check failed: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Feature flags visible in config
Write-Host "`n[2/7] Feature flags configuration..." -ForegroundColor Yellow
try {
    $config = Invoke-RestMethod "$baseUrl/ops/config"
    Write-Host "  ✅ ENABLE_MEMORY: $($config.enable_memory)" -ForegroundColor Green
    Write-Host "  ✅ ENABLE_ENRICHMENT: $($config.enable_enrichment)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Config check failed: $_" -ForegroundColor Red
}

# Test 3: Create lead with enrichment
Write-Host "`n[3/7] Create lead (with enrichment)..." -ForegroundColor Yellow
try {
    $leadBody = @{
        name = "TestUser"
        phone = "555-1234"
        details = "urgent metal roof repair needed today"
    } | ConvertTo-Json

    $lead = Invoke-RestMethod -Uri "$baseUrl/v1/lead" -Method Post `
        -ContentType 'application/json' -Body $leadBody -TimeoutSec 10

    $leadId = $lead.lead_id
    Write-Host "  ✅ Lead created: $leadId" -ForegroundColor Green
    Write-Host "     Intent: $($lead.intent), Urgency: $($lead.urgency), Score: $($lead.score)" -ForegroundColor Cyan
} catch {
    Write-Host "  ❌ Lead creation failed: $_" -ForegroundColor Red
    exit 1
}

# Test 4: Get conversation history
Write-Host "`n[4/7] Retrieve conversation history..." -ForegroundColor Yellow
try {
    $history = Invoke-RestMethod "$baseUrl/v1/lead/$leadId/history?limit=10" -TimeoutSec 5
    $itemCount = $history.items.Count
    Write-Host "  ✅ History retrieved: $itemCount messages" -ForegroundColor Green
    if ($itemCount -gt 0) {
        $firstMsg = $history.items[0]
        Write-Host "     First message: role=$($firstMsg.role), text=$($firstMsg.text.Substring(0, [Math]::Min(40, $firstMsg.text.Length)))..." -ForegroundColor Cyan
    }
} catch {
    Write-Host "  ⚠️  History retrieval failed (memory might be disabled): $_" -ForegroundColor Yellow
}

# Test 5: Create another lead for search
Write-Host "`n[5/7] Create second lead..." -ForegroundColor Yellow
try {
    $lead2Body = @{
        name = "SecondUser"
        phone = "555-5678"
        details = "metal siding installation quote"
    } | ConvertTo-Json

    $lead2 = Invoke-RestMethod -Uri "$baseUrl/v1/lead" -Method Post `
        -ContentType 'application/json' -Body $lead2Body -TimeoutSec 10

    Write-Host "  ✅ Second lead created: $($lead2.lead_id)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Second lead creation failed: $_" -ForegroundColor Yellow
}

# Test 6: Search leads
Write-Host "`n[6/7] Search leads by keyword..." -ForegroundColor Yellow
try {
    $search = Invoke-RestMethod "$baseUrl/v1/search?q=metal&limit=10" -TimeoutSec 5
    Write-Host "  ✅ Search returned $($search.count) results for 'metal'" -ForegroundColor Green
    if ($search.results.Count -gt 0) {
        $topResult = $search.results[0]
        Write-Host "     Top result: lead=$($topResult.lead_id), score=$($topResult.score)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "  ❌ Search failed: $_" -ForegroundColor Red
}

# Test 7: Check metrics
Write-Host "`n[7/7] Verify Prometheus metrics..." -ForegroundColor Yellow
try {
    $metricsResp = Invoke-WebRequest -Uri "$baseUrl/metrics" -UseBasicParsing -TimeoutSec 5
    $metrics = $metricsResp.Content

    # Check for histogram
    $histogramLines = $metrics -split "`n" | Select-String "lead_enrich_score"
    if ($histogramLines.Count -gt 0) {
        Write-Host "  ✅ Score histogram metric found ($($histogramLines.Count) lines)" -ForegroundColor Green
        # Show count
        $countLine = $metrics -split "`n" | Select-String "lead_enrich_score_count" | Select-Object -First 1
        if ($countLine) {
            Write-Host "     $countLine" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  ⚠️  Score histogram not found in metrics" -ForegroundColor Yellow
    }

    # Check for enrichment counter
    $enrichLines = $metrics -split "`n" | Select-String "lead_enrich_total"
    if ($enrichLines.Count -gt 0) {
        Write-Host "  ✅ Enrichment counter found ($($enrichLines.Count) lines)" -ForegroundColor Green
        Write-Host "     Sample: $($enrichLines[0])" -ForegroundColor Cyan
    } else {
        Write-Host "  ⚠️  Enrichment counter not found in metrics" -ForegroundColor Yellow
    }

    # Check for intent counter
    $intentLines = $metrics -split "`n" | Select-String "agent_intent_total"
    if ($intentLines.Count -gt 0) {
        Write-Host "  ✅ Intent counter found ($($intentLines.Count) lines)" -ForegroundColor Green
    }
} catch {
    Write-Host "  ❌ Metrics check failed: $_" -ForegroundColor Red
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "✅ Elite features verification complete!" -ForegroundColor Green
Write-Host "`nAvailable endpoints:" -ForegroundColor Cyan
Write-Host "  • POST /v1/lead              — Create lead (with enrichment)" -ForegroundColor White
Write-Host "  • GET  /v1/lead              — List leads (with history)" -ForegroundColor White
Write-Host "  • GET  /v1/lead/{id}/history — Conversation memory" -ForegroundColor White
Write-Host "  • GET  /v1/search            — Semantic search" -ForegroundColor White
Write-Host "  • GET  /metrics              — Prometheus metrics" -ForegroundColor White
Write-Host "  • GET  /ops/config           — Feature flags & config" -ForegroundColor White
Write-Host "`nFeature flags:" -ForegroundColor Cyan
Write-Host "  • ENABLE_MEMORY=true         — Conversation history storage" -ForegroundColor White
Write-Host "  • ENABLE_ENRICHMENT=true     — AI-powered lead scoring" -ForegroundColor White
