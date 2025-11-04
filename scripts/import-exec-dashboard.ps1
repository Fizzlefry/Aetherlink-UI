# ============================================================================
# IMPORT EXECUTIVE DASHBOARD VIA GRAFANA API
# ============================================================================
# Automatically imports the Business KPIs executive dashboard into Grafana
# No manual UI interaction required
# ============================================================================

param(
    [string]$GrafanaUrl = "http://localhost:3000",
    [string]$Username = "admin",
    [string]$Password = "admin"
)

Write-Host "`n╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         IMPORT EXECUTIVE DASHBOARD (API)              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$dashboardPath = "$PSScriptRoot\..\monitoring\grafana-dashboard-business-kpis.json"

# Verify dashboard file exists
if (-not (Test-Path $dashboardPath)) {
    Write-Host "❌ Dashboard file not found: $dashboardPath" -ForegroundColor Red
    exit 1
}

Write-Host "📁 Dashboard: $dashboardPath" -ForegroundColor Gray
Write-Host "🌐 Grafana: $GrafanaUrl" -ForegroundColor Gray
Write-Host ""

# Load dashboard JSON
try {
    $dashboardJson = Get-Content $dashboardPath -Raw | ConvertFrom-Json
    Write-Host "✅ Dashboard JSON loaded" -ForegroundColor Green
}
catch {
    Write-Host "❌ Failed to load dashboard JSON: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Prepare import payload
$importPayload = @{
    dashboard = $dashboardJson
    overwrite = $true
    message   = "Imported via API - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
} | ConvertTo-Json -Depth 100

# Create auth header
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${Username}:${Password}"))
$headers = @{
    Authorization  = "Basic $auth"
    'Content-Type' = 'application/json'
}

# Import dashboard
Write-Host "📤 Importing dashboard..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod `
        -Uri "$GrafanaUrl/api/dashboards/db" `
        -Method POST `
        -Headers $headers `
        -Body $importPayload `
        -ErrorAction Stop
    
    Write-Host "✅ Dashboard imported successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Title: $($response.title)" -ForegroundColor Gray
    Write-Host "   UID: $($response.uid)" -ForegroundColor Gray
    Write-Host "   URL: $GrafanaUrl/d/$($response.uid)" -ForegroundColor Cyan
    Write-Host ""
    
    # Open in browser
    Write-Host "🌐 Opening dashboard in browser..." -ForegroundColor Cyan
    Start-Process "$GrafanaUrl/d/$($response.uid)"
    
    Write-Host ""
    Write-Host "🎉 Executive dashboard is now live!" -ForegroundColor Green
    Write-Host ""
    
}
catch {
    $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
    
    if ($errorDetails) {
        Write-Host "❌ Import failed: $($errorDetails.message)" -ForegroundColor Red
    }
    else {
        Write-Host "❌ Import failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "💡 Troubleshooting:" -ForegroundColor Yellow
    Write-Host "   1. Check Grafana is running: $GrafanaUrl" -ForegroundColor Gray
    Write-Host "   2. Verify credentials (default: admin/admin)" -ForegroundColor Gray
    Write-Host "   3. Try manual import: Grafana → Dashboards → Import → Upload JSON" -ForegroundColor Gray
    Write-Host ""
    
    exit 1
}

Write-Host "📊 Available Dashboards:" -ForegroundColor Cyan
Write-Host "   Main (5 panels):      $GrafanaUrl/d/aetherlink_rag_tenant_metrics_enhanced" -ForegroundColor Gray
Write-Host "   Executive (4 panels): $GrafanaUrl/d/$($response.uid)" -ForegroundColor Gray
Write-Host ""
