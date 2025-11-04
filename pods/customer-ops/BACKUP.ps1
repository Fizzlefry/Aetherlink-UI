# BACKUP.ps1
# PowerShell script for backing up AetherLink data (DuckDB + Audit Log)
# Schedule with Windows Task Scheduler for nightly runs
#
# Example usage:
#   .\BACKUP.ps1
#   .\BACKUP.ps1 -DataDir "C:\path\to\data" -BackupRoot "D:\Backups"

param(
    [string]$DataDir = "C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\customer_ops\data",
    [string]$BackupRoot = "C:\Users\jonmi\OneDrive\Documents\AetherLink\backups"
)

# Create backup root if it doesn't exist
if (-not (Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot | Out-Null
    Write-Host "Created backup directory: $BackupRoot"
}

# Generate timestamp for backup folder
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFolder = Join-Path $BackupRoot "backup_$timestamp"

# Create timestamped backup folder
New-Item -ItemType Directory -Path $backupFolder | Out-Null
Write-Host "Created backup folder: $backupFolder"

# Copy DuckDB file
$duckdbPath = Join-Path $DataDir "knowledge.duckdb"
if (Test-Path $duckdbPath) {
    Copy-Item $duckdbPath -Destination $backupFolder
    Write-Host "Copied: knowledge.duckdb"
}
else {
    Write-Warning "DuckDB file not found: $duckdbPath"
}

# Copy audit log
$auditPath = Join-Path $DataDir "audit\ops.jsonl"
if (Test-Path $auditPath) {
    $auditBackupDir = Join-Path $backupFolder "audit"
    New-Item -ItemType Directory -Path $auditBackupDir | Out-Null
    Copy-Item $auditPath -Destination $auditBackupDir
    Write-Host "Copied: audit/ops.jsonl"
}
else {
    Write-Warning "Audit log not found: $auditPath"
}

# Compress to .zip
$zipPath = "$backupFolder.zip"
Compress-Archive -Path $backupFolder -DestinationPath $zipPath
Write-Host "Compressed to: $zipPath"

# Remove uncompressed folder
Remove-Item -Recurse -Force $backupFolder
Write-Host "Removed temporary folder: $backupFolder"

# Calculate zip size
$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host "Backup complete: $zipPath ($([math]::Round($zipSize, 2)) MB)"

# Optional: Clean up old backups (keep last 7 days)
$cutoffDate = (Get-Date).AddDays(-7)
Get-ChildItem -Path $BackupRoot -Filter "backup_*.zip" | 
Where-Object { $_.LastWriteTime -lt $cutoffDate } |
ForEach-Object {
    Remove-Item $_.FullName
    Write-Host "Removed old backup: $($_.Name)"
}
