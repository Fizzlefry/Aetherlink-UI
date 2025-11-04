<#
Creates or updates a Scheduled Task that runs post_backup_sync.ps1 nightly.
Defaults: 02:45 AM local (15 min after backup), Keep=20.
Usage:
  .\schedule_post_backup_sync.ps1 -Dest "C:\Users\You\OneDrive\AetherLink\backups"
  .\schedule_post_backup_sync.ps1 -Dest "D:\Backups\AetherLink" -Time "03:00" -Keep 30 -TaskName "AetherLink Nightly DB Sync"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Dest,
    [string]$Time = "02:45",                       # HH:mm
    [int]$Keep = 20,
    [string]$TaskName = "AetherLink Nightly DB Sync"
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$SyncScript = Join-Path $Repo "post_backup_sync.ps1"
if (-not (Test-Path $SyncScript)) { throw "Missing: $SyncScript" }

# Validate time
try { $t = [DateTime]::ParseExact($Time, 'HH:mm', $null) } catch { throw "Invalid -Time (use HH:mm)" }

# Command block (cd into repo, run sync, log to backups/)
$psCmd = @"
`$d = Get-Date -Format yyyyMMdd_HHmmss;
Set-Location '$Repo';
.\post_backup_sync.ps1 -Dest '$Dest' -Keep $Keep *>&1 | Out-File -FilePath (Join-Path 'backups' "sync_`$d.log") -Encoding utf8
"@

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $psCmd
)
$trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours($t.Hour).AddMinutes($t.Minute))
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -LogonType InteractiveToken
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "✅ Updated task: $TaskName ($Time daily → $Dest, Keep=$Keep)"
}
else {
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "✅ Created task: $TaskName ($Time daily → $Dest, Keep=$Keep)"
}

Write-Host "🗓 Next run:"; (Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo).NextRunTime
