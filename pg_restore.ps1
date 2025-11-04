<#
Restores a .dump created by pg_backup.ps1 into the 'aetherlink' DB in the aether-postgres container.
Includes --clean --if-exists to drop/replace objects as needed.
Usage:
  .\pg_restore.ps1 -File .\backups\aetherlink_20251101_130500.dump
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$File,
    [switch]$Force
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $File)) { throw "Backup file not found: $File" }

function Test-Docker() { try { docker version *>$null } catch { throw "Docker Desktop isn't running." } }
Test-Docker

$container = "aether-postgres"
$exists = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
if (-not $exists) { throw "Container '$container' not found. Start with .\dev_setup.ps1" }

$running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $container }
if (-not $running) { docker start $container | Out-Null }

# Confirm unless -Force supplied
if (-not $Force) {
    Write-Host "⚠️  This will DROP and replace objects in database 'aetherlink' inside container '$container'." -ForegroundColor Yellow
    $confirm = Read-Host "Continue? (y/N)"
    $ans = ($confirm | ForEach-Object { $_.ToString().ToLowerInvariant() })
    if ($ans -ne 'y' -and $ans -ne 'yes') { Write-Host "Restore aborted."; exit 1 }
}

# Copy file into container and restore
$base = Split-Path -Leaf $File
Write-Host "⬆️  Copying backup into container..."
docker cp "$File" "${container}:/tmp/$base"

Write-Host "♻️  Restoring into database 'aetherlink'..."
$env:PGPASSWORD = "aetherpass"
docker exec -e PGPASSWORD=$env:PGPASSWORD $container pg_restore -U aether -d aetherlink --clean --if-exists "/tmp/$base"
docker exec $container bash -lc "rm -f '/tmp/$base'" | Out-Null
Remove-Item Env:\PGPASSWORD

Write-Host "✅ Restore complete."
