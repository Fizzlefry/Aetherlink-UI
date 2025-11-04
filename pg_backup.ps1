<#
Creates a compressed pg_dump (.dump) from the 'aether-postgres' container into ./backups/.
Keeps the N most recent backups (default 10).
Usage:
  .\pg_backup.ps1
  .\pg_backup.ps1 -Keep 20
#>
param([int]$Keep = 10)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

function Test-Docker() { try { docker version *>$null } catch { throw "Docker Desktop isn't running." } }
Test-Docker

$container = "aether-postgres"
# quick existence check
$exists = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
if (-not $exists) { throw "Container '$container' not found. Start with .\dev_setup.ps1" }

# ensure running
$running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $container }
if (-not $running) { docker start $container | Out-Null }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$localDir = Join-Path (Get-Location) "backups"
$newFile = Join-Path $localDir "aetherlink_$stamp.dump"

New-Item -ItemType Directory -Force -Path $localDir | Out-Null

Write-Host "🗄️  Creating backup inside container..."
$env:PGPASSWORD = "aetherpass"
docker exec -e PGPASSWORD=$env:PGPASSWORD $container pg_dump -U aether -d aetherlink -F c -f /tmp/aetherlink.dump

Write-Host "⬇️  Copying to host: $newFile"
docker cp "${container}:/tmp/aetherlink.dump" "$newFile"
docker exec $container bash -lc "rm -f /tmp/aetherlink.dump" | Out-Null
Remove-Item Env:\PGPASSWORD

# Retention
$files = Get-ChildItem $localDir -Filter "aetherlink_*.dump" | Sort-Object LastWriteTime -Descending
if ($files.Count -gt $Keep) {
    $toDelete = $files[$Keep..($files.Count - 1)]
    foreach ($f in $toDelete) { Write-Host "🧹 Deleting old backup: $($f.Name)"; Remove-Item $f.FullName -Force }
}

Write-Host "✅ Backup complete: $newFile"
