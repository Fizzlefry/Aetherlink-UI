# Backup & Disaster Recovery - PowerShell Version
# Windows-compatible backup script for autoheal audit trail

param(
    [string]$BackupDir = "C:\backups\aetherlink\autoheal",
    [string]$AuditDataDir = "C:\Users\jonmi\OneDrive\Documents\AetherLink\monitoring\data\autoheal",
    [int]$RetentionDays = 30,
    [switch]$CloudBackup
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

function Write-Log {
    param([string]$Message)
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$time] $Message" -ForegroundColor Cyan
}

# Create backup directory
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
    Write-Log "Created backup directory: $BackupDir"
}

Write-Log "Starting autoheal backup..."

# 1. Backup audit trail
$auditFile = Join-Path $AuditDataDir "audit.jsonl"
if (Test-Path $auditFile) {
    Write-Log "Backing up audit trail..."
    $backupFile = Join-Path $BackupDir "audit_${timestamp}.jsonl"
    Copy-Item $auditFile $backupFile

    # Compress with 7-Zip if available, otherwise use .NET compression
    if (Get-Command 7z -ErrorAction SilentlyContinue) {
        & 7z a "$backupFile.gz" $backupFile
        Remove-Item $backupFile
        Write-Log "Audit trail backed up (compressed): audit_${timestamp}.jsonl.gz"
    }
    else {
        Compress-Archive -Path $backupFile -DestinationPath "$backupFile.zip"
        Remove-Item $backupFile
        Write-Log "Audit trail backed up (ZIP): audit_${timestamp}.jsonl.zip"
    }
}
else {
    Write-Log "WARNING: Audit trail not found at $auditFile" -ForegroundColor Yellow
}

# 2. Backup rotated archives
$archives = Get-ChildItem -Path $AuditDataDir -Filter "audit.jsonl-*" -ErrorAction SilentlyContinue
if ($archives) {
    Write-Log "Backing up $($archives.Count) rotated archives..."
    foreach ($archive in $archives) {
        $destFile = Join-Path $BackupDir "$($archive.Name)_${timestamp}"
        Copy-Item $archive.FullName $destFile
        Write-Log "Archived: $($archive.Name)"
    }
}

# 3. Clean up old backups
Write-Log "Cleaning up backups older than $RetentionDays days..."
$cutoffDate = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -Filter "audit_*.jsonl.*" | Where-Object { $_.LastWriteTime -lt $cutoffDate } | Remove-Item -Force
Get-ChildItem $BackupDir -Filter "audit.jsonl-*" | Where-Object { $_.LastWriteTime -lt $cutoffDate } | Remove-Item -Force

# 4. Cloud sync (if enabled and rclone is available)
if ($CloudBackup) {
    if (Get-Command rclone -ErrorAction SilentlyContinue) {
        Write-Log "Syncing to cloud storage..."
        $rcloneRemote = "s3:aetherlink-backups/autoheal"
        rclone sync $BackupDir $rcloneRemote --log-level INFO
        Write-Log "Cloud sync complete"
    }
    else {
        Write-Log "WARNING: rclone not installed, skipping cloud sync" -ForegroundColor Yellow
    }
}

# 5. Generate manifest
$manifestFile = Join-Path $BackupDir "manifest_${timestamp}.txt"
@"
Autoheal Backup Manifest
Generated: $(Get-Date)
Backup Directory: $BackupDir
Retention Days: $RetentionDays

Files Backed Up:
$(Get-ChildItem $BackupDir | Where-Object { $_.Name -like "audit_*" -or $_.Name -like "audit.jsonl-*" } | Format-Table -AutoSize | Out-String)

Disk Usage:
$((Get-ChildItem $BackupDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB) MB
"@ | Out-File $manifestFile

Write-Log "Backup complete!"
Write-Log "Manifest: $manifestFile"
Write-Log "Total backups: $($(Get-ChildItem $BackupDir -Filter "audit_*").Count)"
