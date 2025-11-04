# Increase "paid" without increasing "generated" to push burn rate DOWN
# This simulates payment recovery to test SLO burn-down scenarios

$ErrorActionPreference = "Stop"

Write-Host "[recovery] Starting payment recovery simulation..." -ForegroundColor Green
Write-Host "[recovery] This will increase paid invoices without new generations" -ForegroundColor Green
Write-Host "[recovery] Watch the burn-rate panels & EBR gauge recover." -ForegroundColor Green
Write-Host ""

$org = "1"
$incrementCount = 15

# Create a Python script to increment only paid invoices
$pythonScript = @"
import time, os
try:
    from crm.metrics import CRM_INVOICES_PAID
    org = os.environ.get("ORG", "1")

    print(f"[recovery] Incrementing paid invoices for org_id={org}")
    for i in range($incrementCount):
        CRM_INVOICES_PAID.labels(org_id=org).inc(1)
        print(f"  Payment {i+1}/$incrementCount processed")
        time.sleep(0.3)

    print("[recovery] Payment recovery complete!")
except ImportError as e:
    print(f"[recovery] Error: Could not import CRM metrics. Is crm-api running? {e}")
except Exception as e:
    print(f"[recovery] Error during simulation: {e}")
"@

# Execute the Python script inside the crm-api container
try {
    Write-Host "[recovery] Executing in crm-api container..." -ForegroundColor Cyan
    $pythonScript | docker exec -i crm-api python -

    Write-Host ""
    Write-Host "[recovery] ✅ Simulation complete!" -ForegroundColor Green
    Write-Host "[recovery] Payment rate should improve. Check these panels:" -ForegroundColor Green
    Write-Host "  - Payment Rate (30d) - should increase" -ForegroundColor White
    Write-Host "  - Burn Rate (1h/6h) - should decrease" -ForegroundColor White
    Write-Host "  - Error Budget Remaining - should recover" -ForegroundColor White
    Write-Host ""
    Write-Host "[recovery] Opening SLO dashboard..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:3000/d/peakpro_crm_slo"
}
catch {
    Write-Host "[recovery] ❌ Error: $_" -ForegroundColor Red
    Write-Host "[recovery] Make sure crm-api container is running: docker ps | grep crm-api" -ForegroundColor Yellow
}
