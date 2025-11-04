# ════════════════════════════════════════════════════════════════
# MASTER LAUNCHER - Opens all 3 windows automatically
# ════════════════════════════════════════════════════════════════
# Run this ONE script to launch everything!
# Usage: .\LAUNCH_AB_SYSTEM.ps1
# ════════════════════════════════════════════════════════════════

$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT
Set-ExecutionPolicy Bypass -Scope Process -Force

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          AetherLink A/B System - Master Launcher              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ════════════════════════════════════════════════════════════════
# STEP 0: Preflight
# ════════════════════════════════════════════════════════════════
Write-Host "[0] Running Preflight Checks..." -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Redis
Write-Host "`nStarting Redis..." -ForegroundColor Cyan
docker rm -f aether-redis 2>$null | Out-Null
$redisOutput = docker run -d --name aether-redis -p 6379:6379 redis:7 2>&1
if ($LASTEXITCODE -eq 0) {
    Start-Sleep -Seconds 2
    Write-Host "✅ Redis started (container: aether-redis)" -ForegroundColor Green
} else {
    Write-Host "❌ Redis failed to start. Ensure Docker is running." -ForegroundColor Red
    exit 1
}

# Dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
.\.venv\Scripts\pip.exe install -U pip wheel --quiet 2>$null
.\.venv\Scripts\pip.exe install -r pods\customer_ops\requirements.txt --quiet 2>$null
.\.venv\Scripts\pip.exe install backoff scikit-learn scipy numpy --quiet 2>$null

# Verify
$libCheck = .\.venv\Scripts\python.exe -c @"
try:
    import backoff, sklearn, scipy, numpy
    print('OK')
except ImportError as e:
    print(f'ERROR: {e}')
"@ 2>&1

if ($libCheck -eq "OK") {
    Write-Host "✅ All dependencies installed" -ForegroundColor Green
} else {
    Write-Host "❌ Dependency error: $libCheck" -ForegroundColor Red
    exit 1
}

# ════════════════════════════════════════════════════════════════
# STEP 1: Optional Model Training
# ════════════════════════════════════════════════════════════════
if (!(Test-Path "pods\customer_ops\api\model.json")) {
    Write-Host "`n[1] Training initial model..." -ForegroundColor Yellow
    $env:PYTHONPATH = $ROOT
    .\.venv\Scripts\python.exe pods\customer_ops\scripts\train_model.py 2>&1 | Out-Null
    
    if (Test-Path "pods\customer_ops\api\model.json") {
        Write-Host "✅ Model trained" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Model training skipped (API will fail-open)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[1] Model already exists, skipping training" -ForegroundColor Gray
}

# ════════════════════════════════════════════════════════════════
# STEP 2: Launch API Window
# ════════════════════════════════════════════════════════════════
Write-Host "`n[2] Launching API Server..." -ForegroundColor Yellow

$apiTitle = "AetherLink API Server"
$apiScript = @"
`$ROOT = '$ROOT'
Set-Location `$ROOT
`$env:PYTHONPATH = `$ROOT
`$host.UI.RawUI.WindowTitle = '$apiTitle'
Write-Host '╔════════════════════════════════════════════════════════════════╗' -ForegroundColor Green
Write-Host '║              API SERVER - Keep this window open!              ║' -ForegroundColor Green
Write-Host '╚════════════════════════════════════════════════════════════════╝' -ForegroundColor Green
Write-Host ''
Write-Host 'Starting uvicorn on http://0.0.0.0:8000...' -ForegroundColor Cyan
Write-Host 'Press CTRL+C to stop' -ForegroundColor Yellow
Write-Host ''
.\.venv\Scripts\python.exe -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload
"@

$apiProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiScript -PassThru
Write-Host "✅ API window opened (PID: $($apiProcess.Id))" -ForegroundColor Green

# ════════════════════════════════════════════════════════════════
# STEP 3: Launch Worker Window
# ════════════════════════════════════════════════════════════════
Write-Host "`n[3] Launching RQ Worker..." -ForegroundColor Yellow

$workerTitle = "AetherLink RQ Worker"
$workerScript = @"
`$ROOT = '$ROOT'
Set-Location `$ROOT
`$env:PYTHONPATH = `$ROOT
`$env:REDIS_URL = 'redis://localhost:6379/0'
`$host.UI.RawUI.WindowTitle = '$workerTitle'
Write-Host '╔════════════════════════════════════════════════════════════════╗' -ForegroundColor Magenta
Write-Host '║            RQ WORKER - Keep this window open!                 ║' -ForegroundColor Magenta
Write-Host '╚════════════════════════════════════════════════════════════════╝' -ForegroundColor Magenta
Write-Host ''
Write-Host 'Starting RQ worker for follow-up queue...' -ForegroundColor Cyan
Write-Host 'Press CTRL+C to stop' -ForegroundColor Yellow
Write-Host ''
.\.venv\Scripts\python.exe pods\customer_ops\worker.py
"@

$workerProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $workerScript -PassThru
Write-Host "✅ Worker window opened (PID: $($workerProcess.Id))" -ForegroundColor Green

# ════════════════════════════════════════════════════════════════
# Wait for services to start
# ════════════════════════════════════════════════════════════════
Write-Host "`n⏳ Waiting for services to start (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# ════════════════════════════════════════════════════════════════
# Verify API is responding
# ════════════════════════════════════════════════════════════════
Write-Host "`nVerifying API..." -ForegroundColor Cyan
$apiReady = $false
try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ API is responding: $($health.Content)" -ForegroundColor Green
    $apiReady = $true
} catch {
    try {
        $health = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✅ API is responding: $($health.Content)" -ForegroundColor Green
        $apiReady = $true
    } catch {
        Write-Host "⚠️  API not responding yet. Check API window for errors." -ForegroundColor Yellow
        Write-Host "   It may need more time to start." -ForegroundColor Gray
    }
}

# ════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════
Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  LAUNCH COMPLETE!                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "✅ Three windows opened:" -ForegroundColor Cyan
Write-Host "   1. API Server (green title) - Port 8000" -ForegroundColor White
Write-Host "   2. RQ Worker (magenta title) - Watching queue" -ForegroundColor White
Write-Host "   3. Control (this window) - For running tests" -ForegroundColor White

Write-Host "`n📋 Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Wait for API to finish starting (check green window)" -ForegroundColor Gray
Write-Host "   2. Run validation: .\step4_7_validation.ps1" -ForegroundColor Gray
Write-Host "   3. Or run smoke test directly: .\test_ab_experiment.ps1 -NumLeads 20" -ForegroundColor Gray

Write-Host "`n🔧 Quick Commands:" -ForegroundColor Yellow
Write-Host "   # Check experiment status" -ForegroundColor Gray
Write-Host "   Invoke-RestMethod -Uri 'http://localhost:8000/ops/experiments' | ConvertTo-Json -Depth 10" -ForegroundColor Cyan

Write-Host "`n   # View metrics" -ForegroundColor Gray
Write-Host "   Invoke-WebRequest -Uri 'http://localhost:8000/metrics' | Select-Object -ExpandProperty Content | Select-String 'experiment_'" -ForegroundColor Cyan

Write-Host "`n   # Run full validation" -ForegroundColor Gray
Write-Host "   .\step4_7_validation.ps1" -ForegroundColor Cyan

if ($apiReady) {
    Write-Host "`n🎯 Ready to run validation!" -ForegroundColor Green
    Write-Host "`nPress ENTER to run validation now, or CTRL+C to run commands manually..." -ForegroundColor Yellow
    Read-Host
    
    Write-Host "`nLaunching validation..." -ForegroundColor Cyan
    .\step4_7_validation.ps1
} else {
    Write-Host "`n⚠️  API may need more time. Wait 30 seconds and run:" -ForegroundColor Yellow
    Write-Host "   .\step4_7_validation.ps1" -ForegroundColor Cyan
}
