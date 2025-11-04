# AetherLink - One-shot collector for A/B validation artifacts
# Usage: In the Control window, run:
#   cd "$env:USERPROFILE\OneDrive\Documents\AetherLink"
#   .\collect_ab_artifacts.ps1

$ErrorActionPreference = "Continue"
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT

# 1) Tail of validation/smoke (re-run smoke if needed)
Write-Host "[1/3] Collecting validation tail..." -ForegroundColor Cyan
try {
    if (Test-Path .\ab_smoke_output.txt) {
        $tail = Get-Content .\ab_smoke_output.txt | Select-Object -Last 12
    } elseif (Test-Path .\test_ab_experiment.ps1) {
        Write-Host "   Smoke output not found; running test_ab_experiment.ps1 -NumLeads 20" -ForegroundColor Yellow
        .\test_ab_experiment.ps1 -NumLeads 20 2>&1 | Tee-Object -FilePath ab_smoke_output.txt | Out-Null
        $tail = Get-Content .\ab_smoke_output.txt | Select-Object -Last 12
    } else {
        Write-Host "   ⚠️  test_ab_experiment.ps1 not found; skipping smoke re-run" -ForegroundColor Yellow
        $tail = @("(no smoke output available)")
    }
} catch {
    $tail = @("(error collecting smoke output: $($_.Exception.Message))")
}

# 2) Experiments JSON
Write-Host "[2/3] Fetching /ops/experiments JSON..." -ForegroundColor Cyan
$expJsonFile = Join-Path $ROOT "ab_experiments.json"
try {
    $exp = Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" -TimeoutSec 10
    $null = ($exp | ConvertTo-Json -Depth 10 | Tee-Object -FilePath $expJsonFile)
} catch {
    $exp = $null
    "{ \"error\": \"$($_.Exception.Message)\" }" | Set-Content $expJsonFile
}

# 3) experiment_* metrics
Write-Host "[3/3] Extracting experiment_* metrics..." -ForegroundColor Cyan
$metricsFile = Join-Path $ROOT "ab_metrics.txt"
try {
    $metricsRaw = (Invoke-WebRequest -Uri "http://localhost:8000/metrics" -UseBasicParsing -TimeoutSec 10).Content
    $metrics = $metricsRaw | Select-String "experiment_variant_assigned_total|experiment_outcome_total|experiment_conversion_rate|experiment_sample_size"
    if (-not $metrics) { $metrics = @("(no experiment_* metrics matched)") }
    $null = ($metrics | Tee-Object -FilePath $metricsFile)
} catch {
    "(error fetching metrics: $($_.Exception.Message))" | Set-Content $metricsFile
}

# Final printout
Write-Host "`n===== COPY BELOW THIS LINE =====" -ForegroundColor Green
Write-Host "--- Validation tail ---" -ForegroundColor White
$tail | ForEach-Object { $_ }

Write-Host "`n--- /ops/experiments JSON ---" -ForegroundColor White
Get-Content $expJsonFile

Write-Host "`n--- experiment_* metrics ---" -ForegroundColor White
Get-Content $metricsFile
Write-Host "===== COPY ABOVE THIS LINE =====" -ForegroundColor Green
