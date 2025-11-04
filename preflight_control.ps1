# ════════════════════════════════════════════════════════════════
# AetherLink A/B Experiments - Preflight & Launch Checklist
# ════════════════════════════════════════════════════════════════
# Usage: Run these commands in THREE PowerShell windows
# Window 1: CONTROL (this window)
# Window 2: API (keep open)
# Window 3: WORKER (keep open)
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 0) PREFLIGHT (Control window)
# ════════════════════════════════════════════════════════════════
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT
Set-ExecutionPolicy Bypass -Scope Process -Force

Write-Host "`n[0] Preflight Checks" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

# Make sure Redis is fresh and up
Write-Host "Starting Redis..." -ForegroundColor Yellow
docker rm -f aether-redis 2>$null
docker run -d --name aether-redis -p 6379:6379 redis:7
Start-Sleep -Seconds 2
docker ps --filter "name=aether-redis" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Sanity: key libs present
Write-Host "`nInstalling/verifying dependencies..." -ForegroundColor Yellow
.\.venv\Scripts\pip.exe install -U pip wheel --quiet
.\.venv\Scripts\pip.exe install -r pods\customer_ops\requirements.txt --quiet
.\.venv\Scripts\pip.exe install backoff scikit-learn scipy numpy --quiet

Write-Host "`nVerifying critical libraries..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -c @"
import backoff, sklearn, scipy, numpy
print('✅ backoff', backoff.__version__)
print('✅ scikit-learn', sklearn.__version__)
print('✅ scipy', scipy.__version__)
print('✅ numpy', numpy.__version__)
"@

Write-Host "`n✅ Preflight complete!" -ForegroundColor Green
Write-Host "`n════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Next: Run commands in sections 1-3 below" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════`n" -ForegroundColor Cyan
