<#
Removes the scheduled task created by schedule_nightly_backup.ps1.
Usage:
  .\unschedule_nightly_backup.ps1
  .\unschedule_nightly_backup.ps1 -TaskName "AetherLink Nightly DB Backup"
#>
param(
    [string]$TaskName = "AetherLink Nightly DB Backup"
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "🗑  Removed scheduled task: $TaskName"
}
else {
    Write-Host "ℹ️  Task not found: $TaskName"
}
