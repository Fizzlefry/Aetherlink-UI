# Outcome Tracking Verification Script
# Tests the reward model foundation endpoints

Write-Host "🧠 Outcome Tracking (Reward Model Foundation) Test" -ForegroundColor Cyan
Write-Host "==================================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"

# Test 1: Create a lead
Write-Host "[1/5] Creating test lead..." -ForegroundColor Yellow
try {
    $lead = Invoke-RestMethod -Uri "$baseUrl/v1/lead" -Method Post `
        -ContentType 'application/json' `
        -Body '{"name":"RewardTest","phone":"555-1234","details":"urgent metal roof needed"}' `
        -TimeoutSec 10

    $leadId = $lead.lead_id
    Write-Host "  ✅ Lead created: $leadId" -ForegroundColor Green
    Write-Host "     Intent: $($lead.intent), Score: $($lead.score)" -ForegroundColor Cyan
} catch {
    Write-Host "  ❌ Lead creation failed: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Record outcome - booked
Write-Host "`n[2/5] Recording outcome (booked)..." -ForegroundColor Yellow
try {
    $outcome = Invoke-RestMethod -Uri "$baseUrl/v1/lead/$leadId/outcome" -Method Post `
        -ContentType 'application/json' `
        -Body '{"outcome":"booked","notes":"Customer confirmed appointment for Friday","time_to_conversion":3600}' `
        -TimeoutSec 10

    Write-Host "  ✅ Outcome recorded: $($outcome.outcome) at $($outcome.recorded_at)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Outcome recording failed: $_" -ForegroundColor Red
    exit 1
}

# Test 3: Create another lead and mark as ghosted
Write-Host "`n[3/5] Creating second lead and marking ghosted..." -ForegroundColor Yellow
try {
    $lead2 = Invoke-RestMethod -Uri "$baseUrl/v1/lead" -Method Post `
        -ContentType 'application/json' `
        -Body '{"name":"GhostTest","phone":"555-5678","details":"interested in quote"}' `
        -TimeoutSec 10

    $leadId2 = $lead2.lead_id

    $outcome2 = Invoke-RestMethod -Uri "$baseUrl/v1/lead/$leadId2/outcome" -Method Post `
        -ContentType 'application/json' `
        -Body '{"outcome":"ghosted","notes":"No response after 3 follow-ups"}' `
        -TimeoutSec 10

    Write-Host "  ✅ Second lead: $leadId2, Outcome: $($outcome2.outcome)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Second lead test failed: $_" -ForegroundColor Yellow
}

# Test 4: Get analytics
Write-Host "`n[4/5] Fetching outcome analytics..." -ForegroundColor Yellow
try {
    $analytics = Invoke-RestMethod "$baseUrl/v1/analytics/outcomes?limit=500" -TimeoutSec 10

    Write-Host "  ✅ Analytics retrieved:" -ForegroundColor Green
    Write-Host "     Total Leads: $($analytics.total_leads)" -ForegroundColor Cyan
    Write-Host "     Total Outcomes: $($analytics.total_outcomes)" -ForegroundColor Cyan
    Write-Host "     Conversion Rate: $([math]::Round($analytics.conversion_rate * 100, 2))%" -ForegroundColor Cyan

    if ($analytics.avg_time_to_conversion) {
        $avgMinutes = [math]::Round($analytics.avg_time_to_conversion / 60, 1)
        Write-Host "     Avg Time to Conversion: $avgMinutes minutes" -ForegroundColor Cyan
    }

    Write-Host "     Outcome Breakdown:" -ForegroundColor Cyan
    foreach ($key in $analytics.outcome_breakdown.PSObject.Properties.Name) {
        Write-Host "       • $key : $($analytics.outcome_breakdown.$key)" -ForegroundColor White
    }
} catch {
    Write-Host "  ❌ Analytics retrieval failed: $_" -ForegroundColor Red
}

# Test 5: Check metrics
Write-Host "`n[5/5] Verifying Prometheus metrics..." -ForegroundColor Yellow
try {
    $metricsResp = Invoke-WebRequest -Uri "$baseUrl/metrics" -UseBasicParsing -TimeoutSec 5
    $metrics = $metricsResp.Content

    # Check for outcome counter
    $outcomeLines = $metrics -split "`n" | Select-String "lead_outcome_total"
    if ($outcomeLines.Count -gt 0) {
        Write-Host "  ✅ Outcome counter found ($($outcomeLines.Count) lines)" -ForegroundColor Green
        Write-Host "     Sample: $($outcomeLines[0])" -ForegroundColor Cyan
    } else {
        Write-Host "  ⚠️  Outcome counter not found" -ForegroundColor Yellow
    }

    # Check for conversion rate gauge
    $conversionLines = $metrics -split "`n" | Select-String "lead_conversion_rate"
    if ($conversionLines.Count -gt 0) {
        Write-Host "  ✅ Conversion rate gauge found" -ForegroundColor Green
        Write-Host "     $($conversionLines[0])" -ForegroundColor Cyan
    } else {
        Write-Host "  ⚠️  Conversion rate gauge not found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Metrics check failed: $_" -ForegroundColor Red
}

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "✅ Outcome tracking verification complete!" -ForegroundColor Green
Write-Host "`nNew Endpoints:" -ForegroundColor Cyan
Write-Host "  • POST /v1/lead/{id}/outcome — Record lead outcomes" -ForegroundColor White
Write-Host "  • GET  /v1/analytics/outcomes — Conversion analytics" -ForegroundColor White
Write-Host "`nReward Model Ready:" -ForegroundColor Cyan
Write-Host "  • Track: booked, ghosted, qualified, unqualified, nurture, spam" -ForegroundColor White
Write-Host "  • Metrics: outcome counters + conversion rate gauge" -ForegroundColor White
Write-Host "  • Analytics: conversion rate, time to conversion, breakdown" -ForegroundColor White
