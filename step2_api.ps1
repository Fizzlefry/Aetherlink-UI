# ════════════════════════════════════════════════════════════════
# 2) START API SERVER (New window - keep open!)
# ════════════════════════════════════════════════════════════════
# Copy this entire block to a NEW PowerShell window
# DO NOT CLOSE THIS WINDOW - API will run here
# ════════════════════════════════════════════════════════════════

$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT
$env:PYTHONPATH = $ROOT

# Optional: Set environment flags if needed
# $env:ENABLE_PII_REDACTION = "true"
# $env:FOLLOWUP_ENABLED = "true"

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              API SERVER - Keep this window open!              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "Starting uvicorn on http://0.0.0.0:8000..." -ForegroundColor Cyan
Write-Host "Press CTRL+C to stop the server`n" -ForegroundColor Yellow

.\.venv\Scripts\python.exe -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload

# ════════════════════════════════════════════════════════════════
# You should see:
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
# INFO:     Started reloader process [12345] using WatchFiles
# INFO:     Started server process [12346]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# ════════════════════════════════════════════════════════════════
