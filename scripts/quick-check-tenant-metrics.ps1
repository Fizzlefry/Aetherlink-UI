param(
  [string]$BaseUrl,
  [string]$ApiKey,
  [string]$TenantLabelFilter
)

if (-not $BaseUrl) { $BaseUrl = "http://localhost:8000" }
if (-not $ApiKey) { $ApiKey = $env:API_KEY_EXPERTCO }
if (-not $ApiKey) { $ApiKey = $env:API_ADMIN_KEY }
if (-not $ApiKey) { 
  Write-Host "ERROR: No API key found in API_KEY_EXPERTCO or API_ADMIN_KEY" -ForegroundColor Red
  exit 1 
}

Write-Host "Nudging API to generate metrics..." -ForegroundColor Cyan
$null = curl.exe -s -H "X-API-Key: $ApiKey" "$BaseUrl/search?q=test&mode=hybrid"

Start-Sleep -Seconds 1

Write-Host "Fetching metrics..." -ForegroundColor Cyan
$metrics = curl.exe -s "$BaseUrl/metrics"

$pattern = if ($TenantLabelFilter) { "tenant=|$TenantLabelFilter" } else { "tenant=" }
$lines = $metrics | Select-String $pattern

Write-Host "`n========== TENANT METRICS ==========" -ForegroundColor Green
if ($lines) {
  $lines | Select-Object -First 10 | ForEach-Object { Write-Host $_.Line -ForegroundColor Yellow }
} else {
  Write-Host "No tenant-labeled metrics found." -ForegroundColor Red
  Write-Host "Check that requests include an API key that resolves to a tenant_id." -ForegroundColor Gray
}
Write-Host "====================================`n" -ForegroundColor Green
