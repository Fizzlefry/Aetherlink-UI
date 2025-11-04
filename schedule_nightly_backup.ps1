<#
Creates or updates a Windows Scheduled Task that runs pg_backup.ps1 nightly.
Defaults: 2:30 AM local, keep last 10 snapshots.
Usage examples:
  .\schedule_nightly_backup.ps1
  .\schedule_nightly_backup.ps1 -Time "01:15" -Keep 20 -TaskName "AetherLink Nightly DB Backup"
#>

param(
    [string]$Time = "02:30",                    # HH:mm (24h)
    [int]$Keep = 10,                            # retention used by pg_backup.ps1
    [string]$TaskName = "AetherLink Nightly DB Backup"
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

# Resolve absolute repo path (where this script is)
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupScript = Join-Path $Repo "pg_backup.ps1"
if (-not (Test-Path $BackupScript)) {
    throw "pg_backup.ps1 not found at $BackupScript. Run from the repo where it's installed."
}

# Build a PowerShell command that sets the working directory, runs the backup, and writes a log
# We generate a timestamped log under ./backups
$psCmd = @"
`$d = Get-Date -Format yyyyMMdd_HHmmss;
Set-Location '$Repo';
.\pg_backup.ps1 -Keep $Keep *>&1 | Out-File -FilePath (Join-Path 'backups' "scheduled_`$d.log") -Encoding utf8
"@

# Use powershell.exe with -Command to execute the above block
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $psCmd
)

# Daily trigger at the specified time
try {
    $parsed = [DateTime]::ParseExact($Time, 'HH:mm', $null)
}
catch {
    throw "Invalid -Time format. Use HH:mm (e.g., 02:30)."
}
$trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours($parsed.Hour).AddMinutes($parsed.Minute))

# Run as current user with highest privileges
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -LogonType InteractiveToken

# Ensure the task definition
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings

# Register or update
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "✅ Updated scheduled task: $TaskName ($Time daily, Keep=$Keep)"
}
else {
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "✅ Created scheduled task: $TaskName ($Time daily, Keep=$Keep)"
}

Write-Host "🗓  Next run:"; (Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo).NextRunTime
Write-Host "ℹ️  Logs will be written to: $Repo\backups\scheduled_YYYYmmdd_HHMMSS.log"