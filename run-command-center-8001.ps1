param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8001
)

$repo = "C:\Users\jonmi\OneDrive\Documents\AetherLink"
cd $repo
$env:PYTHONPATH = $repo

# per-instance env
$env:COMMAND_CENTER_INSTANCE_ID = "cc-02"
$env:COMMAND_CENTER_DATA_DIR = "$repo\services\command-center\data-cc02"

# make sure the per-instance data dir exists
if (-not (Test-Path $env:COMMAND_CENTER_DATA_DIR)) {
    New-Item -ItemType Directory -Path $env:COMMAND_CENTER_DATA_DIR | Out-Null
}

Write-Host "Starting AetherLink Command Center (cc-02) on $BindHost:$Port ..." -ForegroundColor Green
Write-Host "Data directory: $env:COMMAND_CENTER_DATA_DIR" -ForegroundColor Cyan

python -m uvicorn "services.command-center.main:app" --host $BindHost --port $Port --log-level info
