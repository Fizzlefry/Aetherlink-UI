<#
One-shot verification: health -> migrate[+seed] -> backup -> restore-latest -> health
Usage:
    .\verify_e2e.ps1
    .\verify_e2e.ps1 -Seed   # run seeds before backup
#>

param(
    [switch]$Seed
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

function Test-Url {
    param([string]$Url, [int]$TimeoutSec = 3)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 300
    }
    catch { return $false }
}

Write-Host "🚀 Verifying AetherLink end-to-end..."

# Ensure API is reachable (give it up to 60s)
$healthUrl = 'http://localhost:8000/health'
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    if (Test-Url $healthUrl 3) { $ok = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ok) {
    Write-Host "ℹ️  API health not ready yet, attempting to start stack (\"up\")..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\dev_setup.ps1'
    # Probe again up to 60s
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Url $healthUrl 3) { $ok = $true; break }
        Start-Sleep -Seconds 1
    }
}
if (-not $ok) { throw "API did not become healthy at $healthUrl" }
Write-Host "✅ API healthy before DB ops."

if ($Seed) {
    Write-Host "⏫ Running migrations + seed..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\dev_migrate.ps1' -Seed
    if ($LASTEXITCODE -ne 0) { throw "Migration+Seed failed" }
}
else {
    Write-Host "⏫ Running migrations..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\dev_migrate.ps1'
    if ($LASTEXITCODE -ne 0) { throw "Migration failed" }
}

# Backup now
Write-Host "💾 Creating backup..."
& powershell -NoProfile -ExecutionPolicy Bypass -File '.\pg_backup.ps1'
if ($LASTEXITCODE -ne 0) { throw "Backup failed" }

# Restore latest
Write-Host "♻️  Restoring latest backup..."
& powershell -NoProfile -ExecutionPolicy Bypass -File '.\pg_restore_latest.ps1' -Force
if ($LASTEXITCODE -ne 0) { throw "Restore-latest failed" }

# Final health check
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    if (Test-Url $healthUrl 3) { $ok = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ok) { throw "API not healthy after restore at $healthUrl" }
Write-Host "✅ API healthy after restore."

Write-Host "🎉 Verify complete: migrate → backup → restore-latest → health check all passed."
