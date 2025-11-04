# SLO Backfill Simulator
# Placeholder for historical SLO data ingestion
# Wire to your push endpoint when available for realistic runway calculations

param(
    [int]$Days = 30,
    [int]$InvoicesPerDay = 200,
    [int]$PaidPerDay = 180
)

Write-Host "`n=== SLO Backfill Simulator ===" -ForegroundColor Cyan
Write-Host "Target: $Days days of historical data" -ForegroundColor Yellow
Write-Host "Invoices/day: $InvoicesPerDay, Paid/day: $PaidPerDay" -ForegroundColor Yellow

# Calculate payment rate
$paymentRate = ($PaidPerDay / $InvoicesPerDay) * 100
Write-Host "`nSimulated Payment Rate: $($paymentRate)%" -ForegroundColor Cyan

# Placeholder for push endpoint
Write-Host "`n[INFO] Backfill requires push endpoint configuration" -ForegroundColor Yellow
Write-Host "Options:" -ForegroundColor White
Write-Host "  1. Prometheus remote_write endpoint" -ForegroundColor White
Write-Host "  2. Push Gateway (pushgateway:9091)" -ForegroundColor White
Write-Host "  3. Direct TSDB insertion" -ForegroundColor White

Write-Host "`n[TODO] Wire this to your ingestion endpoint:" -ForegroundColor Yellow
Write-Host "  # Pseudocode loop:" -ForegroundColor DarkGray
Write-Host "  for (`$day = `$Days; `$day -ge 0; `$day--) {" -ForegroundColor DarkGray
Write-Host "    `$timestamp = (Get-Date).AddDays(-`$day).ToUniversalTime()" -ForegroundColor DarkGray
Write-Host "    # POST to push endpoint with timestamp" -ForegroundColor DarkGray
Write-Host "    # invoices_generated_total{org_id=`"1`"} $InvoicesPerDay @`$timestamp" -ForegroundColor DarkGray
Write-Host "    # invoices_paid_total{org_id=`"1`"} $PaidPerDay @`$timestamp" -ForegroundColor DarkGray
Write-Host "  }" -ForegroundColor DarkGray

Write-Host "`n[ALTERNATIVE] Use existing simulators for live behavior:" -ForegroundColor Yellow
Write-Host "  .\scripts\simulate_payment_rate_dip.ps1" -ForegroundColor White
Write-Host "  .\scripts\simulate_payment_rate_recovery.ps1" -ForegroundColor White

Write-Host ""
