# ========================================
# AetherLink A/B Experiment Setup & Launch
# ========================================
# Run this script to go from 0 → fully operational A/B testing in ~5 minutes
#
# Usage:
#   .\setup_and_run_ab.ps1
#
# Or with parameters:
#   .\setup_and_run_ab.ps1 -SkipDeps -SkipRedis -NumLeads 50

[CmdletBinding()]
param(
    [switch]$SkipDeps,      # Skip pip install if already done
    [switch]$SkipRedis,     # Skip Redis if already running
    [switch]$SkipModel,     # Skip model training
    [switch]$SkipWorker,    # Skip RQ worker (not recommended)
    [int]$NumLeads = 20     # Number of test leads to generate
)

$ErrorActionPreference = "Continue"
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AetherLink A/B Experimentation - Fast Path Setup            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

cd $ROOT

# ========================================
# Step 0: Environment Check
# ========================================
Write-Host "[Step 0] Environment Check" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "❌ Virtual environment not found. Creating..." -ForegroundColor Red
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create venv. Ensure Python 3.11+ is installed." -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Python venv found: .venv" -ForegroundColor Green
$pythonVersion = & ".\.venv\Scripts\python.exe" --version 2>&1
Write-Host "   Version: $pythonVersion" -ForegroundColor Gray

# ========================================
# Step 1: Install Dependencies
# ========================================
if (!$SkipDeps) {
    Write-Host "`n[Step 1] Installing Dependencies" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    Write-Host "Upgrading pip and wheel..." -ForegroundColor Cyan
    & ".\.venv\Scripts\pip.exe" install -U pip wheel --quiet

    Write-Host "Installing customer_ops requirements..." -ForegroundColor Cyan
    & ".\.venv\Scripts\pip.exe" install -r pods\customer_ops\requirements.txt --quiet

    Write-Host "Ensuring critical libs (backoff, scikit-learn, scipy, numpy)..." -ForegroundColor Cyan
    & ".\.venv\Scripts\pip.exe" install backoff scikit-learn scipy numpy --quiet

    # Verify installation
    $testImports = & ".\.venv\Scripts\python.exe" -c @"
try:
    import backoff, sklearn, scipy, numpy
    print('✅ All dependencies installed')
    print(f'   backoff: {backoff.__version__}')
    print(f'   scikit-learn: {sklearn.__version__}')
    print(f'   scipy: {scipy.__version__}')
    print(f'   numpy: {numpy.__version__}')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"@ 2>&1

    Write-Host $testImports -ForegroundColor Green
} else {
    Write-Host "`n[Step 1] Skipping dependency installation (--SkipDeps)" -ForegroundColor Gray
}

# ========================================
# Step 2: Start Redis
# ========================================
if (!$SkipRedis) {
    Write-Host "`n[Step 2] Starting Redis" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    # Check if already running
    $existing = docker ps --filter "name=aether-redis" --format "{{.Names}}" 2>$null
    if ($existing -eq "aether-redis") {
        Write-Host "✅ Redis already running (container: aether-redis)" -ForegroundColor Green
    } else {
        Write-Host "Starting Redis container..." -ForegroundColor Cyan

        # Remove old container if exists
        docker rm -f aether-redis 2>$null | Out-Null

        # Start fresh
        $redisOutput = docker run -d --name aether-redis -p 6379:6379 redis:7 2>&1
        if ($LASTEXITCODE -eq 0) {
            Start-Sleep -Seconds 2
            Write-Host "✅ Redis started (container: aether-redis)" -ForegroundColor Green
            Write-Host "   Port: 6379" -ForegroundColor Gray
        } else {
            Write-Host "❌ Failed to start Redis: $redisOutput" -ForegroundColor Red
            Write-Host "   Ensure Docker is running: docker ps" -ForegroundColor Yellow
            exit 1
        }
    }
} else {
    Write-Host "`n[Step 2] Skipping Redis (--SkipRedis)" -ForegroundColor Gray
}

# ========================================
# Step 3: Train Initial Model (Optional)
# ========================================
if (!$SkipModel) {
    Write-Host "`n[Step 3] Training Initial Model" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    if (Test-Path "pods\customer_ops\api\model.json") {
        Write-Host "✅ Model already exists (pods\customer_ops\api\model.json)" -ForegroundColor Green
    } else {
        Write-Host "No model found. Training initial model..." -ForegroundColor Cyan

        $env:PYTHONPATH = $ROOT
        $trainOutput = & ".\.venv\Scripts\python.exe" pods\customer_ops\scripts\train_model.py 2>&1

        if (Test-Path "pods\customer_ops\api\model.json") {
            Write-Host "✅ Model trained successfully" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Model training failed (API will fail-open):" -ForegroundColor Yellow
            Write-Host $trainOutput -ForegroundColor Gray
        }
    }
} else {
    Write-Host "`n[Step 3] Skipping model training (--SkipModel)" -ForegroundColor Gray
}

# ========================================
# Step 4: Enable A/B Experiment
# ========================================
Write-Host "`n[Step 4] Enabling followup_timing Experiment" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$experimentsFile = "pods\customer_ops\api\experiments.py"
$content = Get-Content $experimentsFile -Raw

if ($content -match '"followup_timing".*?enabled=False') {
    Write-Host "Setting enabled=True in experiments.py..." -ForegroundColor Cyan
    $content = $content -replace '("followup_timing".*?)(enabled=False)', '$1enabled=True'
    $content | Set-Content $experimentsFile -NoNewline
    Write-Host "✅ Experiment enabled: followup_timing" -ForegroundColor Green
} elseif ($content -match '"followup_timing".*?enabled=True') {
    Write-Host "✅ Experiment already enabled: followup_timing" -ForegroundColor Green
} else {
    Write-Host "⚠️  Could not find followup_timing experiment in experiments.py" -ForegroundColor Yellow
}

# ========================================
# Step 5: Start API (Background)
# ========================================
Write-Host "`n[Step 5] Starting API Server" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Check if already running
try {
    $healthCheck = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    Write-Host "✅ API already running on http://localhost:8000" -ForegroundColor Green
} catch {
    Write-Host "Starting uvicorn server..." -ForegroundColor Cyan
    Write-Host "   (This will open a new window - don't close it!)" -ForegroundColor Gray

    $env:PYTHONPATH = $ROOT
    $apiProcess = Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$ROOT'; `$env:PYTHONPATH='$ROOT'; .\.venv\Scripts\python.exe -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload"
    ) -PassThru

    Write-Host "   Waiting for API to start..." -ForegroundColor Gray
    Start-Sleep -Seconds 8

    # Verify
    try {
        $healthCheck = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "✅ API started successfully on http://localhost:8000" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  API may not be ready yet. Check the uvicorn window." -ForegroundColor Yellow
        Write-Host "   URL: http://localhost:8000/health" -ForegroundColor Gray
    }
}

# ========================================
# Step 6: Start RQ Worker (Background)
# ========================================
if (!$SkipWorker) {
    Write-Host "`n[Step 6] Starting RQ Worker" -ForegroundColor Yellow
    Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    Write-Host "Starting RQ worker for follow-up jobs..." -ForegroundColor Cyan
    Write-Host "   (This will open a new window - don't close it!)" -ForegroundColor Gray

    $env:PYTHONPATH = $ROOT
    $env:REDIS_URL = "redis://localhost:6379/0"

    $workerProcess = Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$ROOT'; `$env:PYTHONPATH='$ROOT'; `$env:REDIS_URL='redis://localhost:6379/0'; .\.venv\Scripts\python.exe pods\customer_ops\worker.py"
    ) -PassThru

    Start-Sleep -Seconds 3
    Write-Host "✅ RQ Worker started (PID: $($workerProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "`n[Step 6] Skipping RQ worker (--SkipWorker)" -ForegroundColor Gray
}

# ========================================
# Step 7: Reload Model & Verify
# ========================================
Write-Host "`n[Step 7] Reloading Model & Status Check" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Start-Sleep -Seconds 2

try {
    Write-Host "Reloading model..." -ForegroundColor Cyan
    $reloadResult = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/ops/reload-model" -TimeoutSec 10
    Write-Host "✅ Model reloaded: $($reloadResult | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Model reload failed (may not be critical): $($_.Exception.Message)" -ForegroundColor Yellow
}

try {
    Write-Host "Checking model status..." -ForegroundColor Cyan
    $modelStatus = Invoke-RestMethod -Uri "http://localhost:8000/ops/model-status" -TimeoutSec 10
    Write-Host "✅ Model status:" -ForegroundColor Green
    Write-Host "   Trained: $($modelStatus.trained)" -ForegroundColor Gray
    Write-Host "   Features: $($modelStatus.features -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Could not fetch model status: $($_.Exception.Message)" -ForegroundColor Yellow
}

# ========================================
# Step 8: Verify Experiment Enabled
# ========================================
Write-Host "`n[Step 8] Verifying Experiment Status" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

try {
    $experiments = Invoke-RestMethod -Uri "http://localhost:8000/ops/experiments" -TimeoutSec 10
    $followup = $experiments.experiments.followup_timing

    if ($followup.enabled) {
        Write-Host "✅ Experiment 'followup_timing' is ENABLED" -ForegroundColor Green
        Write-Host "   Variants:" -ForegroundColor Gray
        foreach ($variant in $followup.variants) {
            Write-Host "     - $($variant.name): $($variant.traffic_weight * 100)% traffic" -ForegroundColor Gray
        }
    } else {
        Write-Host "❌ Experiment 'followup_timing' is DISABLED" -ForegroundColor Red
        Write-Host "   Check pods\customer_ops\api\experiments.py line 104" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Could not fetch experiment status: $($_.Exception.Message)" -ForegroundColor Red
}

# ========================================
# Step 9: Run A/B Smoke Test
# ========================================
Write-Host "`n[Step 9] Running A/B Smoke Test ($NumLeads leads)" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (Test-Path ".\test_ab_experiment.ps1") {
    Write-Host "Executing test_ab_experiment.ps1..." -ForegroundColor Cyan
    Write-Host ""

    & ".\test_ab_experiment.ps1" -NumLeads $NumLeads -ApiBase "http://localhost:8000"

    Write-Host ""
} else {
    Write-Host "⚠️  Smoke test script not found: test_ab_experiment.ps1" -ForegroundColor Yellow
    Write-Host "   Run manually: .\test_ab_experiment.ps1 -NumLeads $NumLeads" -ForegroundColor Gray
}

# ========================================
# Final Summary
# ========================================
Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Setup Complete! A/B Experimentation is LIVE                 ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

Write-Host "🎯 What's Running:" -ForegroundColor Green
Write-Host "   • API:        http://localhost:8000" -ForegroundColor White
Write-Host "   • Redis:      localhost:6379 (container: aether-redis)" -ForegroundColor White
Write-Host "   • RQ Worker:  Watching follow-up queue" -ForegroundColor White
Write-Host "   • Experiment: followup_timing (control vs aggressive)" -ForegroundColor White

Write-Host "`n📊 Quick Commands:" -ForegroundColor Green
Write-Host "   # View experiment dashboard" -ForegroundColor Gray
Write-Host "   Invoke-RestMethod -Uri 'http://localhost:8000/ops/experiments' | ConvertTo-Json -Depth 10" -ForegroundColor Cyan

Write-Host "`n   # Check Prometheus metrics" -ForegroundColor Gray
Write-Host "   Invoke-WebRequest -Uri 'http://localhost:8000/metrics' | Select-Object -ExpandProperty Content | Select-String 'experiment_'" -ForegroundColor Cyan

Write-Host "`n   # Promote winner (when p<0.05)" -ForegroundColor Gray
Write-Host "   Invoke-RestMethod -Method POST -Uri 'http://localhost:8000/ops/experiments/followup_timing/promote' | ConvertTo-Json" -ForegroundColor Cyan

Write-Host "`n   # Re-run smoke test" -ForegroundColor Gray
Write-Host "   .\test_ab_experiment.ps1 -NumLeads 50" -ForegroundColor Cyan

Write-Host "`n📚 Documentation:" -ForegroundColor Green
Write-Host "   • Quick Start:  QUICKSTART_AB.md" -ForegroundColor White
Write-Host "   • Full Guide:   AB_EXPERIMENTS_GUIDE.md" -ForegroundColor White
Write-Host "   • Executive:    SHIPPED_AB_EXPERIMENTS.md" -ForegroundColor White

Write-Host "`n🚀 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Monitor /ops/experiments daily" -ForegroundColor White
Write-Host "   2. Wait for 100+ samples per variant (1-2 weeks)" -ForegroundColor White
Write-Host "   3. Promote winner when p < 0.05" -ForegroundColor White
Write-Host "   4. Configure next experiment (prediction_threshold, enrichment_model)" -ForegroundColor White

Write-Host "`n✨ Happy experimenting! Let the data guide you to 30% conversion lift! ✨`n" -ForegroundColor Cyan
