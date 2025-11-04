<#
Restores the most recent .dump file from .\backups into 'aetherlink' DB
in the 'aether-postgres' container.

Usage:
  .\pg_restore_latest.ps1
#>

param(
    [switch]$Force
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

$ROOT = (Get-Location).Path
$BACKUPS = Join-Path $ROOT 'backups'
if (-not (Test-Path $BACKUPS)) { throw "Backups folder not found: $BACKUPS" }

# Find latest *.dump
$latest = Get-ChildItem $BACKUPS -Filter '*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw "No .dump files found in $BACKUPS" }

Write-Host "🧭 Latest backup: $($latest.FullName)"
$container = "aether-postgres"

# Sanity checks
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

# Copy and restore
$base = Split-Path -Leaf $latest.FullName
Write-Host "⬆️  Copying backup into container..."
docker cp "$($latest.FullName)" "${container}:/tmp/$base"

Write-Host "♻️  Restoring into database 'aetherlink'..."
$env:PGPASSWORD = "aetherpass"
docker exec -e PGPASSWORD=$env:PGPASSWORD $container pg_restore -U aether -d aetherlink --clean --if-exists "/tmp/$base"
docker exec $container bash -lc "rm -f '/tmp/$base'" | Out-Null
Remove-Item Env:\PGPASSWORD

Write-Host "✅ Restore from latest complete."
