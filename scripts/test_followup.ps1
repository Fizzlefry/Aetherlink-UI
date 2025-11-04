# Test Follow-Up Engine - Verification Script
# Tests: schedule parsing, high-prob lead enqueue, queue status endpoint

$ErrorActionPreference = "Stop"

Write-Host "=== Follow-Up Engine Verification ===" -ForegroundColor Cyan
Write-Host ""

# Configuration
$BASE_URL = "http://localhost:8000"
$API_KEY = "dev-key-123"

Write-Host "[1/4] Testing Queue Status Endpoint..." -ForegroundColor Yellow
try {
    $queueStatus = Invoke-RestMethod `
        -Uri "$BASE_URL/ops/followup/queue" `
        -Method GET `
        -Headers @{ "x-api-key" = $API_KEY }

    Write-Host "  ✓ Queue Status: enabled=$($queueStatus.enabled), queue=$($queueStatus.queue)" -ForegroundColor Green
    if ($queueStatus.jobs) {
        Write-Host "    - Queued: $($queueStatus.jobs.queued)" -ForegroundColor Gray
        Write-Host "    - Scheduled: $($queueStatus.jobs.scheduled)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ✗ Queue status check failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Creating High-Probability Lead (should trigger follow-ups)..." -ForegroundColor Yellow

$highProbLead = @{
    name = "Alex Rivera"
    phone = "+1-555-0199"
    details = "Urgent: Need to book immediately for tomorrow morning. Budget $5000, credit card ready."
} | ConvertTo-Json

try {
    $leadResponse = Invoke-RestMethod `
        -Uri "$BASE_URL/v1/lead" `
        -Method POST `
        -Headers @{
            "x-api-key" = $API_KEY
            "Content-Type" = "application/json"
        } `
        -Body $highProbLead

    $leadId = $leadResponse.data.lead_id
    $predProb = $leadResponse.data.pred_prob
    $intent = $leadResponse.data.intent
    $urgency = $leadResponse.data.urgency

    Write-Host "  ✓ Lead Created: $leadId" -ForegroundColor Green
    Write-Host "    - Intent: $intent" -ForegroundColor Gray
    Write-Host "    - Urgency: $urgency" -ForegroundColor Gray
    Write-Host "    - Pred Prob: $predProb" -ForegroundColor Gray

    if ($predProb -ge 0.70) {
        Write-Host "    ✓ Pred prob >= 0.70 - follow-ups should be enqueued!" -ForegroundColor Green
    } else {
        Write-Host "    ⚠ Pred prob < 0.70 - follow-ups will NOT be enqueued" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ✗ Lead creation failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[3/4] Checking Queue Status After Lead Creation..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

try {
    $queueStatusAfter = Invoke-RestMethod `
        -Uri "$BASE_URL/ops/followup/queue" `
        -Method GET `
        -Headers @{ "x-api-key" = $API_KEY }

    Write-Host "  ✓ Queue Status After Lead Creation:" -ForegroundColor Green
    if ($queueStatusAfter.jobs) {
        Write-Host "    - Queued: $($queueStatusAfter.jobs.queued)" -ForegroundColor Gray
        Write-Host "    - Scheduled: $($queueStatusAfter.jobs.scheduled)" -ForegroundColor Gray

        if ($queueStatusAfter.jobs.scheduled -gt 0) {
            Write-Host "    ✓ Follow-up tasks scheduled!" -ForegroundColor Green
        } else {
            Write-Host "    ⚠ No scheduled tasks found (check FOLLOWUP_ENABLED, pred_prob threshold)" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  ✗ Queue status check failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] Creating Low-Probability Lead (should NOT trigger follow-ups)..." -ForegroundColor Yellow

$lowProbLead = @{
    name = "Bob Smith"
    phone = "+1-555-0100"
    details = "Just browsing, not sure what I want."
} | ConvertTo-Json

try {
    $lowLeadResponse = Invoke-RestMethod `
        -Uri "$BASE_URL/v1/lead" `
        -Method POST `
        -Headers @{
            "x-api-key" = $API_KEY
            "Content-Type" = "application/json"
        } `
        -Body $lowProbLead

    $lowLeadId = $lowLeadResponse.data.lead_id
    $lowPredProb = $lowLeadResponse.data.pred_prob

    Write-Host "  ✓ Low-Prob Lead Created: $lowLeadId" -ForegroundColor Green
    Write-Host "    - Pred Prob: $lowPredProb" -ForegroundColor Gray

    if ($lowPredProb -lt 0.70) {
        Write-Host "    ✓ Pred prob < 0.70 - correctly skipped follow-ups" -ForegroundColor Green
    } else {
        Write-Host "    ⚠ Pred prob >= 0.70 - follow-ups will be enqueued" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ✗ Low-prob lead creation failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Verification Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor White
Write-Host "  • Queue enabled: $($queueStatus.enabled)" -ForegroundColor Gray
Write-Host "  • High-prob lead: $leadId (pred_prob=$predProb)" -ForegroundColor Gray
Write-Host "  • Low-prob lead: $lowLeadId (pred_prob=$lowPredProb)" -ForegroundColor Gray
Write-Host "  • Scheduled tasks: $($queueStatusAfter.jobs.scheduled)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Check worker logs: docker-compose logs -f worker" -ForegroundColor Gray
Write-Host "  2. Monitor metrics: http://localhost:8000/metrics (search FOLLOWUP_JOBS_TOTAL)" -ForegroundColor Gray
Write-Host "  3. Watch follow-up hook calls in API logs when tasks execute" -ForegroundColor Gray
Write-Host ""
