<#
PowerShell helper for common dev tasks
Usage: .\dev.ps1 <command>
Commands:
  start   - start docker-compose dev stack (build)
  stop    - stop docker-compose dev stack
  logs    - tail logs for running compose services
  test    - run pytest
  lint    - run pre-commit hooks and python -m pyright
  rebuild - stop, rebuild, and restart the compose stack
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Command
)

function Ensure-Env {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed or not in PATH. Please install Docker Desktop and try again."
        exit 1
    }
}

switch ($Command.ToLower()) {
    'start' {
        Ensure-Env
        Write-Host "Starting dev stack..." -ForegroundColor Cyan
        docker compose -f deploy/docker-compose.dev.yml up -d --build
        Write-Host "Dev stack started." -ForegroundColor Green
    }
    'stop' {
        Ensure-Env
        Write-Host "Stopping dev stack..." -ForegroundColor Cyan
        docker compose -f deploy/docker-compose.dev.yml down
        Write-Host "Dev stack stopped." -ForegroundColor Green
    }
    'logs' {
        Ensure-Env
        Write-Host "Tailing logs (Ctrl+C to stop)..." -ForegroundColor Cyan
        docker compose -f deploy/docker-compose.dev.yml logs -f
    }
    'test' {
        Write-Host "Running pytest..." -ForegroundColor Cyan
        python -m pytest -q
    }
    'lint' {
        Write-Host "Running pre-commit hooks..." -ForegroundColor Cyan
        python -m pip install --upgrade pip
        python -m pip install pre-commit pyright
        pre-commit run --all-files
        Write-Host "Running pyright..." -ForegroundColor Cyan
        python -m pyright
    }
    'rebuild' {
        Ensure-Env
        Write-Host "Rebuilding dev stack..." -ForegroundColor Cyan
        docker compose -f deploy/docker-compose.dev.yml down
        docker compose -f deploy/docker-compose.dev.yml up -d --build
        Write-Host "Rebuild complete." -ForegroundColor Green
    }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Yellow
        Write-Host "Usage: .\dev.ps1 <start|stop|logs|test|lint|rebuild>"
    }
}
