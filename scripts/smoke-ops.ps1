# scripts/smoke-ops.ps1
$ErrorActionPreference = "Stop"

Write-Host "1) Jobs..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "http://localhost:8000/ops/operator/jobs" -Method GET | Out-Null

Write-Host "2) Pause..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "http://localhost:8000/ops/operator/jobs/daily-import/pause?tenant=the-expert-co" -Method POST | Out-Null

Write-Host "3) Analytics..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "http://localhost:8000/ops/analytics?tenant=the-expert-co" -Method GET | Out-Null

Write-Host "✅ Operator deck smoke passed" -ForegroundColor Green
