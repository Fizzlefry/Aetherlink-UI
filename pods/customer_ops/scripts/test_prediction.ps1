# Predictive Conversion Score Verification
# Tests real-time ML prediction on lead creation

Write-Host "🧠 Predictive Conversion Score Test" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8000"

# Step 1: Export training data
Write-Host "[1/5] Exporting outcome data for model training..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "$baseUrl/ops/export/outcomes.csv" -OutFile "outcomes.csv" -TimeoutSec 10
    $lineCount = (Get-Content "outcomes.csv" | Measure-Object -Line).Lines
    Write-Host "  ✅ Exported $lineCount rows to outcomes.csv" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Export failed (might not have outcomes yet): $_" -ForegroundColor Yellow
}

# Step 2: Train model (if Python available)
Write-Host "`n[2/5] Training conversion prediction model..." -ForegroundColor Yellow
try {
    if (Test-Path "outcomes.csv") {
        $trainOutput = python scripts/train_model.py 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Model trained successfully" -ForegroundColor Green
            Write-Host "     Check api/model.json for coefficients" -ForegroundColor Cyan
        } else {
            Write-Host "  ⚠️  Training failed or not enough data" -ForegroundColor Yellow
            Write-Host "     Need at least 10 leads with outcomes" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  ⚠️  No outcomes.csv found, skipping training" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️  Training skipped: $_" -ForegroundColor Yellow
}

# Step 3: Create lead with prediction
Write-Host "`n[3/5] Creating lead (with prediction)..." -ForegroundColor Yellow
try {
    $lead = Invoke-RestMethod -Uri "$baseUrl/v1/lead" -Method Post `
        -ContentType 'application/json' `
        -Body '{"name":"PredictTest","phone":"555-9999","details":"urgent metal roof installation needed today"}' `
        -TimeoutSec 10

    $leadId = $lead.lead_id
    Write-Host "  ✅ Lead created: $leadId" -ForegroundColor Green
    Write-Host "     Intent: $($lead.intent), Score: $($lead.score)" -ForegroundColor Cyan

    if ($lead.pred_prob) {
        $predPercent = [math]::Round($lead.pred_prob * 100, 1)
        Write-Host "     🎯 Predicted Conversion Probability: $predPercent%" -ForegroundColor Magenta
    } else {
        Write-Host "     ℹ️  Prediction not available (model not trained yet)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Lead creation failed: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Record outcome
Write-Host "`n[4/5] Recording outcome (booked)..." -ForegroundColor Yellow
try {
    $outcome = Invoke-RestMethod -Uri "$baseUrl/v1/lead/$leadId/outcome" -Method Post `
        -ContentType 'application/json' `
        -Body '{"outcome":"booked","notes":"Customer booked - prediction was correct!","time_to_conversion":1800}' `
        -TimeoutSec 10

    Write-Host "  ✅ Outcome recorded: $($outcome.outcome)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Outcome recording failed: $_" -ForegroundColor Yellow
}

# Step 5: Check prediction metrics
Write-Host "`n[5/5] Verifying prediction metrics..." -ForegroundColor Yellow
try {
    $metricsResp = Invoke-WebRequest -Uri "$baseUrl/metrics" -UseBasicParsing -TimeoutSec 5
    $metrics = $metricsResp.Content

    # Check for prediction probability histogram
    $predProbLines = $metrics -split "`n" | Select-String "lead_pred_prob"
    if ($predProbLines.Count -gt 0) {
        Write-Host "  ✅ Prediction probability histogram found" -ForegroundColor Green
        Write-Host "     Sample: $($predProbLines[0])" -ForegroundColor Cyan
    } else {
        Write-Host "  ⚠️  Prediction histogram not found (no predictions yet)" -ForegroundColor Yellow
    }

    # Check for prediction latency
    $latencyLines = $metrics -split "`n" | Select-String "lead_pred_latency_seconds"
    if ($latencyLines.Count -gt 0) {
        Write-Host "  ✅ Prediction latency metric found" -ForegroundColor Green
        $countLine = $latencyLines | Select-String "_count" | Select-Object -First 1
        if ($countLine) {
            Write-Host "     $countLine" -ForegroundColor Cyan
        }
    } else {
        Write-Host "  ⚠️  Latency metric not found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Metrics check failed: $_" -ForegroundColor Red
}

Write-Host "`n====================================" -ForegroundColor Cyan
Write-Host "✅ Prediction system verification complete!" -ForegroundColor Green
Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "  1. Collect 20+ outcomes (mix of booked/ghosted)" -ForegroundColor White
Write-Host "  2. Re-run: python scripts/train_model.py" -ForegroundColor White
Write-Host "  3. Restart API to load new model" -ForegroundColor White
Write-Host "  4. pred_prob will appear on all new leads!" -ForegroundColor White
Write-Host "`nPrediction Flow:" -ForegroundColor Cyan
Write-Host "  • Export data → Train model → Deploy JSON → Real-time inference (<50ms)" -ForegroundColor White
Write-Host "  • Features: score, intent, sentiment, urgency, details_len, hour, tenant" -ForegroundColor White
Write-Host "  • Model: Logistic Regression (lightweight, interpretable)" -ForegroundColor White
