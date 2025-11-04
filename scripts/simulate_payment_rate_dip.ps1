# Simulate a short payment-rate dip by bumping generated without paid
# This helps visualize the Error Budget Remaining gauge drop in dev

$env:ORG = "1"

Write-Host "[sim] Starting payment rate dip simulation..." -ForegroundColor Yellow
Write-Host "[sim] This will increase invoices_generated without corresponding paid invoices" -ForegroundColor Yellow
Write-Host "[sim] Watch the payment rate panels & Error Budget Remaining gauge." -ForegroundColor Yellow
Write-Host ""

# Create a Python script to increment metrics
$pythonScript = @'
import time, os
try:
    from crm.metrics import CRM_INVOICES_PAID, CRM_INVOICES_GENERATED
    org = os.environ.get("ORG", "1")
    
    print(f"[sim] Incrementing invoices_generated for org_id={org}")
    for i in range(10):
        CRM_INVOICES_GENERATED.labels(org_id=org).inc(1)
        print(f"  Step {i+1}/10: Generated +1 invoice (no payment)")
        time.sleep(0.5)
    
    print("[sim] Simulation complete. Check Grafana SLO dashboard.")
except ImportError as e:
    print(f"[sim] Error: Could not import CRM metrics. Is crm-api running? {e}")
except Exception as e:
    print(f"[sim] Error during simulation: {e}")
'@

# Execute the Python script inside the crm-api container
try {
    Write-Host "[sim] Executing in crm-api container..." -ForegroundColor Cyan
    $pythonScript | docker exec -i crm-api python -
    
    Write-Host ""
    Write-Host "[sim] ✅ Simulation complete!" -ForegroundColor Green
    Write-Host "[sim] Check these panels in Grafana:" -ForegroundColor Green
    Write-Host "  - Payment Rate (30d)" -ForegroundColor White
    Write-Host "  - Error Budget Remaining gauge" -ForegroundColor White
    Write-Host ""
    Write-Host "[sim] Opening SLO dashboard..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:3000/d/peakpro_crm_slo"
}
catch {
    Write-Host "[sim] ❌ Error: $_" -ForegroundColor Red
    Write-Host "[sim] Make sure crm-api container is running: docker ps | grep crm-api" -ForegroundColor Yellow
}
