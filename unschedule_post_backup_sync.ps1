param([string]$TaskName = "AetherLink Nightly DB Sync")
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "🗑 Removed scheduled task: $TaskName"
}
else {
    Write-Host "ℹ️ Task not found: $TaskName"
}
