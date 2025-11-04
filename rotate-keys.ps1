[CmdletBinding()]
param(
  [string[]] $AddTenants,               # e.g. "EXPERTCO:ABC123","ARGUS:XYZ789"
  [string[]] $RemoveKeys,               # e.g. "OLDKEY1","OLDKEY2"
  [string]   $BaseUrl = "http://localhost:8000",
  [string]   $TenantApiKey = $env:API_KEY_EXPERTCO,  # used to auth reload endpoint
  [string]   $AdminKey     = $env:API_ADMIN_KEY,     # admin guard
  [switch]   $NoReload                                      # skip calling /ops/reload-auth
)

function Get-Tenants {
  param($Headers)
  try {
    $r = Invoke-RestMethod -Uri "$BaseUrl/ops/tenants" -Headers $Headers -TimeoutSec 8 -ErrorAction Stop
    return $r
  } catch {
    return $null
  }
}

function Get-TenantCountFromMetrics {
  try {
    $content = (Invoke-WebRequest -Uri "$BaseUrl/metrics" -UseBasicParsing -TimeoutSec 8).Content
    $line = $content -split "`n" | Where-Object { $_ -match '^\s*api_tenants_count' } | Select-Object -First 1
    if ($line -match 'api_tenants_count\s+([0-9]+)') { return [int]$Matches[1] }
  } catch {}
  return $null
}

Write-Host "Rotate Keys :: $BaseUrl" -ForegroundColor Cyan

$headers = @{
  "x-api-key"  = $TenantApiKey
  "x-admin-key"= $AdminKey
}

# Snapshot BEFORE
$beforeTenants = Get-Tenants -Headers $headers
$beforeCount   = Get-TenantCountFromMetrics

# Apply additions
if ($AddTenants) {
  foreach ($pair in $AddTenants) {
    if ($pair -notmatch ":") {
      Write-Warning "Invalid AddTenants entry '$pair' (expected TENANT:KEY)"
      continue
    }
    $tenant, $key = $pair.Split(":", 2)
    $tenantVar = "API_KEY_{0}" -f ($tenant.ToUpper())
    # Process-level env var for current shell
    $env:$tenantVar = $key
    # Optionally persist to user env (uncomment if desired):
    # [Environment]::SetEnvironmentVariable($tenantVar, $key, "User")
    Write-Host "Added: $tenantVar" -ForegroundColor Green
  }
}

# Apply removals
if ($RemoveKeys) {
  foreach ($key in $RemoveKeys) {
    # We can't know the tenant var name from the key alone, so just clear any matching process envs.
    # (If you want tenant-level removal, pass TENANT:KEY via -AddTenants with an empty KEY and treat as removal.)
    # Below is a no-op placeholder; real removal requires knowing the env var name.
    Write-Host "Requested remove of key '$key' — note: remove action requires clearing the specific API_KEY_* env var." -ForegroundColor Yellow
  }
}

# Reload (unless skipped)
if (-not $NoReload.IsPresent) {
  try {
    $resp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/ops/reload-auth" -Headers $headers -TimeoutSec 8 -ErrorAction Stop
    Write-Host ("Reloaded auth: " + ($resp | ConvertTo-Json -Depth 5)) -ForegroundColor Cyan
  } catch {
    Write-Warning ("Reload failed: " + $_.Exception.Message)
  }
} else {
  Write-Host "Skipped /ops/reload-auth (NoReload)" -ForegroundColor Yellow
}

# Snapshot AFTER
$afterTenants = Get-Tenants -Headers $headers
$afterCount   = Get-TenantCountFromMetrics

# Print diff
Write-Host "`n=== BEFORE ===" -ForegroundColor DarkGray
if ($beforeTenants) { $beforeTenants | ConvertTo-Json -Depth 5 | Write-Output } else { "n/a" | Write-Output }
Write-Host "api_tenants_count: $beforeCount`n" -ForegroundColor DarkGray

Write-Host "=== AFTER ===" -ForegroundColor DarkGray
if ($afterTenants) { $afterTenants | ConvertTo-Json -Depth 5 | Write-Output } else { "n/a" | Write-Output }
Write-Host "api_tenants_count: $afterCount`n" -ForegroundColor DarkGray

Write-Host "Done." -ForegroundColor Green
