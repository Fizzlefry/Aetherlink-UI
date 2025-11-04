# ════════════════════════════════════════════════════════════════
# AetherLink - Correct Setup (uses venv Python explicitly)
# ════════════════════════════════════════════════════════════════
# Run this in a fresh PowerShell window to fix Docker/Python issues

$ErrorActionPreference = "Continue"
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         AetherLink Setup - Using Correct venv Python          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ════════════════════════════════════════════════════════════════
# Step 0: Kill stray processes
# ════════════════════════════════════════════════════════════════
Write-Host "[0] Cleaning up stray processes..." -ForegroundColor Yellow
taskkill /F /IM python.exe /T 2>$null | Out-Null
taskkill /F /IM uvicorn.exe /T 2>$null | Out-Null
Write-Host "✅ Cleanup complete" -ForegroundColor Green

# ════════════════════════════════════════════════════════════════
# Step 1: Verify Docker & Start Redis
# ════════════════════════════════════════════════════════════════
Write-Host "`n[1] Checking Docker..." -ForegroundColor Yellow

$dockerRunning = $false
try {
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
        Write-Host "✅ Docker is running" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Docker is not running" -ForegroundColor Red
}

if (!$dockerRunning) {
    Write-Host "`n⚠️  Docker Desktop is NOT running!" -ForegroundColor Yellow
    Write-Host "   1. Click Start → type 'Docker Desktop' → open it" -ForegroundColor Gray
    Write-Host "   2. Wait until the whale icon shows 'Engine running'" -ForegroundColor Gray
    Write-Host "   3. Re-run this script`n" -ForegroundColor Gray
    exit 1
}

Write-Host "`nStarting Redis..." -ForegroundColor Cyan
docker rm -f aether-redis 2>$null | Out-Null
$redisId = docker run -d --name aether-redis -p 6379:6379 redis:7 2>&1

if ($LASTEXITCODE -eq 0) {
    Start-Sleep -Seconds 2
    Write-Host "✅ Redis started (container: aether-redis)" -ForegroundColor Green
    docker ps --filter "name=aether-redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
} else {
    Write-Host "❌ Redis failed to start: $redisId" -ForegroundColor Red
    exit 1
}

# ════════════════════════════════════════════════════════════════
# Step 2: Verify Correct Python (venv)
# ════════════════════════════════════════════════════════════════
Write-Host "`n[2] Verifying venv Python..." -ForegroundColor Yellow

$venvPython = Join-Path $ROOT ".venv\Scripts\python.exe"
$venvPip = Join-Path $ROOT ".venv\Scripts\pip.exe"

if (!(Test-Path $venvPython)) {
    Write-Host "❌ Virtual environment not found at: $venvPython" -ForegroundColor Red
    Write-Host "   Creating venv..." -ForegroundColor Yellow
    python -m venv .venv
    if (!(Test-Path $venvPython)) {
        Write-Host "❌ Failed to create venv. Ensure Python 3.11+ is installed." -ForegroundColor Red
        exit 1
    }
}

$pythonPath = & $venvPython -c "import sys; print(sys.executable)" 2>&1
Write-Host "✅ Using venv Python: $pythonPath" -ForegroundColor Green

# ════════════════════════════════════════════════════════════════
# Step 3: Install Dependencies in THIS venv
# ════════════════════════════════════════════════════════════════
Write-Host "`n[3] Installing dependencies in venv..." -ForegroundColor Yellow

Write-Host "   Upgrading pip..." -ForegroundColor Gray
& $venvPip install --upgrade pip --quiet 2>&1 | Out-Null

Write-Host "   Installing from requirements.txt..." -ForegroundColor Gray
& $venvPip install -r pods\customer_ops\requirements.txt --quiet 2>&1 | Out-Null

Write-Host "   Ensuring critical libs (backoff, scikit-learn, scipy, numpy)..." -ForegroundColor Gray
& $venvPip install backoff scikit-learn scipy numpy --quiet 2>&1 | Out-Null

# Verify backoff
$backoffCheck = & $venvPython -c "import backoff; print('OK:', backoff.__version__)" 2>&1
if ($backoffCheck -like "OK:*") {
    Write-Host "✅ Dependencies installed: $backoffCheck" -ForegroundColor Green
} else {
    Write-Host "❌ backoff import failed: $backoffCheck" -ForegroundColor Red
    Write-Host "`nTry manually:" -ForegroundColor Yellow
    Write-Host "   $venvPip install backoff scikit-learn scipy numpy" -ForegroundColor White
    exit 1
}

# ════════════════════════════════════════════════════════════════
# Step 4: Instructions for Manual Launch
# ════════════════════════════════════════════════════════════════
Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                   SETUP COMPLETE!                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "✅ Docker & Redis: Running" -ForegroundColor Green
Write-Host "✅ venv Python: $pythonPath" -ForegroundColor Green
Write-Host "✅ Dependencies: Installed (backoff, scikit-learn, scipy, numpy)" -ForegroundColor Green

Write-Host "`n📋 Next: Launch API and Worker in separate windows`n" -ForegroundColor Cyan

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "WINDOW 1: API Server (keep open!)" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host @"
cd "$ROOT"
`$env:PYTHONPATH = "$ROOT"
$venvPython -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload
"@ -ForegroundColor White

Write-Host "`n═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "WINDOW 2: RQ Worker (keep open!)" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host @"
cd "$ROOT"
`$env:PYTHONPATH = "$ROOT"
`$env:REDIS_URL = "redis://localhost:6379/0"
$venvPython pods\customer_ops\worker.py
"@ -ForegroundColor White

Write-Host "`n═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "WINDOW 3: Control (this window)" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host @"
# After API and Worker are running:
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select -Expand Content
.\collect_ab_artifacts.ps1
"@ -ForegroundColor White

Write-Host "`n💡 TIP: Copy each block above to a NEW PowerShell window" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════`n" -ForegroundColor DarkGray
