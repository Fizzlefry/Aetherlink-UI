# SCHEDULE_BACKUP.ps1
# Creates a Windows scheduled task for nightly AetherLink backups
# Run this script in an elevated PowerShell window (Run as Administrator)

$taskName = "AetherLink Nightly Backup"
$psPath = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$script = "C:\Users\jonmi\OneDrive\Documents\AetherLink\pods\customer-ops\BACKUP.ps1"

Write-Host "Creating scheduled task: $taskName" -ForegroundColor Cyan
Write-Host "Script: $script" -ForegroundColor Gray
Write-Host "Schedule: Daily at 2:30 AM" -ForegroundColor Gray
Write-Host ""

# Create the scheduled task
schtasks /Create /TN "$taskName" /TR "`"$psPath`" -ExecutionPolicy Bypass -File `"$script`"" /SC DAILY /ST 02:30 /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Scheduled task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To verify:" -ForegroundColor Yellow
    Write-Host "  schtasks /Query /TN `"$taskName`" /V /FO LIST" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To run manually:" -ForegroundColor Yellow
    Write-Host "  schtasks /Run /TN `"$taskName`"" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To delete:" -ForegroundColor Yellow
    Write-Host "  schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor Gray
}
else {
    Write-Host "❌ Failed to create scheduled task. Make sure you're running as Administrator." -ForegroundColor Red
}
