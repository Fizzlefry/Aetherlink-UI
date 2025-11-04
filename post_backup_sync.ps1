<#
Copies the most recent backup from .\backups to a destination folder.
Optionally keeps only N most recent in destination.

Usage:
  .\post_backup_sync.ps1 -Dest "C:\Users\You\OneDrive\AetherLink\backups" -Keep 10
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Dest,
    [int]$Keep = 10
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

$ROOT = (Get-Location).Path
$SRC = Join-Path $ROOT 'backups'
if (-not (Test-Path $SRC)) { throw "Source backups folder not found: $SRC" }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Find latest dump
$latest = Get-ChildItem $SRC -Filter '*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw "No .dump files found in $SRC" }

$target = Join-Path $Dest $latest.Name
Write-Host "⬆️  Syncing latest backup to: $target"
Copy-Item -Force $latest.FullName $target

# Retention at destination
$destFiles = Get-ChildItem $Dest -Filter '*.dump' | Sort-Object LastWriteTime -Descending
if ($destFiles.Count -gt $Keep) {
    $toDelete = $destFiles[$Keep..($destFiles.Count - 1)]
    foreach ($f in $toDelete) {
        Write-Host "🧹 Pruning old synced backup: $($f.Name)"
        Remove-Item -Force $f.FullName
    }
}

Write-Host "✅ Sync complete."
