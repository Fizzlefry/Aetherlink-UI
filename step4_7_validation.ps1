# ════════════════════════════════════════════════════════════════
# 4-7) VALIDATION & SMOKE TEST (Control window)
# ════════════════════════════════════════════════════════════════
# Run these commands in your CONTROL window after API and Worker are running
# ════════════════════════════════════════════════════════════════

$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    VALIDATION & SMOKE TEST                     ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ════════════════════════════════════════════════════════════════
# 4) Quick Health & Model Checks
# ════════════════════════════════════════════════════════════════
Write-Host "[4] Health & Model Checks" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Write-Host "`nChecking API health..." -ForegroundColor Cyan
Start-Sleep -Seconds 3  # Give API time to fully start

try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ API Health: $($health.Content)" -ForegroundColor Green
} catch {
    Write-Host "⚠️  /health endpoint not found, trying /healthz..." -ForegroundColor Yellow
    try {
        $health = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 5
        Write-Host "✅ API Health: $($health.Content)" -ForegroundColor Green
    } catch {
        Write-Host "❌ API not responding! Check API window for errors." -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
        exit 1
    }
}

Write-Host "`nReloading model..." -ForegroundColor Cyan
try {
    $reloadResult = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/ops/reload-model" -TimeoutSec 10
    Write-Host "✅ Model reloaded: $($reloadResult | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Model reload endpoint not available (may be okay)" -ForegroundColor Yellow
}

Write-Host "`nChecking model status..." -ForegroundColor Cyan
try {
    $modelStatus = Invoke-RestMethod -Uri "http://localhost:8000/ops/model-status" -TimeoutSec 10
    Write-Host "✅ Model Status:" -ForegroundColor Green
    Write-Host ($modelStatus | ConvertTo-Json -Depth 5) -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Model status endpoint not available" -ForegroundColor Yellow
}

# ════════════════════════════════════════════════════════════════
# 5) Ensure A/B is Enabled
# ════════════════════════════════════════════════════════════════
Write-Host "`n[5] A/B Experiment Status" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

try {
    $experiments = Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" -TimeoutSec 10
    $followup = $experiments.experiments.followup_timing

    Write-Host "`nExperiment: followup_timing" -ForegroundColor Cyan
    Write-Host "  Enabled: $($followup.enabled)" -ForegroundColor $(if ($followup.enabled) { "Green" } else { "Red" })
    Write-Host "  Description: $($followup.description)" -ForegroundColor Gray

    if ($followup.variants) {
        Write-Host "  Variants:" -ForegroundColor Gray
        foreach ($variant in $followup.variants) {
            $weight = $variant.traffic_weight * 100
            Write-Host "    - $($variant.name): $weight% traffic, delay=$($variant.config.delay_seconds)s" -ForegroundColor Gray
        }
    }

    if (!$followup.enabled) {
        Write-Host "`n❌ Experiment NOT enabled!" -ForegroundColor Red
        Write-Host "   Edit: pods\customer_ops\api\experiments.py line 104" -ForegroundColor Yellow
        Write-Host "   Change: enabled=False → enabled=True" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "`n✅ Experiment is ready!" -ForegroundColor Green

} catch {
    Write-Host "❌ Could not fetch experiments: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ════════════════════════════════════════════════════════════════
# 6) Run the Smoke Test
# ════════════════════════════════════════════════════════════════
Write-Host "`n[6] Running A/B Smoke Test (20 leads)" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (!(Test-Path ".\test_ab_experiment.ps1")) {
    Write-Host "❌ Smoke test script not found: test_ab_experiment.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "`nExecuting smoke test..." -ForegroundColor Cyan
Write-Host ""

.\test_ab_experiment.ps1 -NumLeads 20 -ApiBase "http://localhost:8000"

# ════════════════════════════════════════════════════════════════
# 7) Metrics Spot-Check
# ════════════════════════════════════════════════════════════════
Write-Host "`n[7] Metrics Spot-Check" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Write-Host "`nPrometheus experiment metrics:" -ForegroundColor Cyan
try {
    $metrics = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -UseBasicParsing -TimeoutSec 10
    $experimentMetrics = $metrics.Content | Select-String "experiment_variant_assigned_total|experiment_outcome_total|experiment_conversion_rate|experiment_sample_size"

    if ($experimentMetrics) {
        Write-Host $experimentMetrics -ForegroundColor Green
    } else {
        Write-Host "⚠️  No experiment metrics found yet (create some leads first)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Could not fetch metrics: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nLead prediction metrics:" -ForegroundColor Cyan
try {
    $predMetrics = $metrics.Content | Select-String "lead_pred_"
    if ($predMetrics) {
        Write-Host $predMetrics -ForegroundColor Gray
    }
} catch {
    # Already have error above
}

# ════════════════════════════════════════════════════════════════
# FINAL OUTPUT FOR VERIFICATION
# ════════════════════════════════════════════════════════════════
Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                   VALIDATION COMPLETE!                         ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "📋 COPY THIS OUTPUT TO SHARE:" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Write-Host "`n1) Full Experiment Status (JSON):" -ForegroundColor Yellow
$fullExperiments = Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" -TimeoutSec 10
Write-Host ($fullExperiments | ConvertTo-Json -Depth 10) -ForegroundColor White

Write-Host "`n2) Key Experiment Metrics:" -ForegroundColor Yellow
$allMetrics = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -UseBasicParsing -TimeoutSec 10
$keyMetrics = $allMetrics.Content | Select-String "experiment_variant_assigned_total|experiment_outcome_total|experiment_conversion_rate"
Write-Host $keyMetrics -ForegroundColor White

Write-Host "`n─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "✅ System is LIVE and collecting A/B data!" -ForegroundColor Green
Write-Host "`n📊 Monitor daily at: http://localhost:8000/ops/experiments" -ForegroundColor Cyan
Write-Host "🎯 Target: 100+ samples per variant for significance" -ForegroundColor Cyan
Write-Host "🚀 Promote winner when p < 0.05" -ForegroundColor Cyan
Write-Host ""
