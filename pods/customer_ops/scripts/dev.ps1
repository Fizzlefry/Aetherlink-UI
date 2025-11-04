[CmdletBinding()]
param(
    [switch]$Up,
    [switch]$Down,
    [switch]$Verify
)

$ErrorActionPreference = "Stop"

# Helper functions
function Test-Docker {
    if (!(Get-Command "docker" -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed or not in PATH"
        exit 1
    }
}

function Start-Stack {
    Write-Host "Starting customer-ops stack..." -ForegroundColor Green
    docker-compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start stack"
        exit 1
    }
    Write-Host "Stack started successfully" -ForegroundColor Green
}

function Stop-Stack {
    Write-Host "Stopping customer-ops stack..." -ForegroundColor Yellow
    docker-compose down
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to stop stack"
        exit 1
    }
    Write-Host "Stack stopped successfully" -ForegroundColor Green
}

function Test-Stack {
    Write-Host "Verifying stack health..." -ForegroundColor Blue
    
    # Wait for services to be ready
    Start-Sleep -Seconds 5

    # Run smoke tests
    Write-Host "Running smoke tests..."
    $env:PYTHONPATH = "."
    pytest tests/test_smoke.py -v
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Smoke tests failed"
        exit 1
    }
    Write-Host "Stack verified successfully" -ForegroundColor Green
}

# Main script
Test-Docker

if ($Up) {
    Start-Stack
    if ($Verify) {
        Test-Stack
    }
}
elseif ($Down) {
    Stop-Stack
}
elseif ($Verify) {
    Test-Stack
}
else {
    Write-Host "Usage: dev.ps1 [-Up] [-Down] [-Verify]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Up      Start the customer-ops stack"
    Write-Host "  -Down    Stop the customer-ops stack"
    Write-Host "  -Verify  Run smoke tests to verify stack health"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\dev.ps1 -Up -Verify    # Start stack and verify"
    Write-Host "  .\dev.ps1 -Down          # Stop stack"
    Write-Host "  .\dev.ps1 -Verify        # Run verification only"
}