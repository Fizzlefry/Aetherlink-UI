# Open Autoheal – Aetherlink Platform Ops Helper
# Opens all autoheal monitoring interfaces

Write-Host "Opening Autoheal monitoring interfaces..." -ForegroundColor Cyan

# SSE Console (live events)
Start-Process "http://localhost:9009/console"
Start-Sleep -Milliseconds 500

# Audit Trail API (last 200 events)
Start-Process "http://localhost:9009/audit?n=200"
Start-Sleep -Milliseconds 500

# Health Check
Start-Process "http://localhost:9009/"
Start-Sleep -Milliseconds 500

# Grafana Dashboard (if available)
Start-Process "http://localhost:3000/d/autoheal"

Write-Host "`n✅ Autoheal interfaces opened!" -ForegroundColor Green
Write-Host "  - Console: http://localhost:9009/console" -ForegroundColor Gray
Write-Host "  - Audit: http://localhost:9009/audit" -ForegroundColor Gray
Write-Host "  - Health: http://localhost:9009/" -ForegroundColor Gray
Write-Host "  - Dashboard: http://localhost:3000/d/autoheal" -ForegroundColor Gray
