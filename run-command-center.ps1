param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$repo = "C:\Users\jonmi\OneDrive\Documents\AetherLink"
cd $repo
$env:PYTHONPATH = $repo

# Clear stuck python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Starting AetherLink Command Center on ${Host}:${Port}..." -ForegroundColor Green
Write-Host "Data directory: $repo\services\command-center\data" -ForegroundColor Cyan

python -m uvicorn "services.command-center.main:app" --host $Host --port $Port --log-level info
