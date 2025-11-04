# ════════════════════════════════════════════════════════════════
# 3) START RQ WORKER (New window - keep open!)
# ════════════════════════════════════════════════════════════════
# Copy this entire block to a NEW PowerShell window
# DO NOT CLOSE THIS WINDOW - Worker will run here
# ════════════════════════════════════════════════════════════════

$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT
$env:PYTHONPATH = $ROOT
$env:REDIS_URL = "redis://localhost:6379/0"

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║            RQ WORKER - Keep this window open!                 ║" -ForegroundColor Magenta
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Magenta

Write-Host "Starting RQ worker for follow-up queue..." -ForegroundColor Cyan
Write-Host "Press CTRL+C to stop the worker`n" -ForegroundColor Yellow

.\.venv\Scripts\python.exe pods\customer_ops\worker.py

# ════════════════════════════════════════════════════════════════
# You should see:
# INFO: Starting RQ worker...
# INFO: Worker started, watching queue: followup_queue
# INFO: Connected to Redis at redis://localhost:6379/0
# ════════════════════════════════════════════════════════════════
