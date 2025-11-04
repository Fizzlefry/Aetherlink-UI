<#
AetherLink PowerShell Makefile
Usage examples:
  ./makefile.ps1 up
  ./makefile.ps1 watch
  ./makefile.ps1 stop
  ./makefile.ps1 reset-db
  ./makefile.ps1 migrate
  ./makefile.ps1 seed
  ./makefile.ps1 revision -Msg "add users table"
  ./makefile.ps1 logs
  ./makefile.ps1 check-schema
  ./makefile.ps1 lint
  ./makefile.ps1 typecheck
  ./makefile.ps1 fmt
  ./makefile.ps1 pre-commit
  ./makefile.ps1 pre-commit-all
  ./makefile.ps1 test
  ./makefile.ps1 backup
  ./makefile.ps1 restore -Msg "path_to_backup_file"
  ./makefile.ps1 coverage
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "up", "watch", "stop", "down", "down-prune", "restart", "reset-db",
        "migrate", "seed", "revision",
        "logs", "check-schema", "health",
        "lint", "typecheck", "fmt",
        "pre-commit", "pre-commit-all",
        "test", "backup", "restore", "coverage",
        "schedule-backup", "unschedule-backup",
        "restore-latest", "sync-backup",
        "schedule-sync", "unschedule-sync",
        "verify", "verify-seed",
        "reload-auth",
        "help"
    )]
    [string]$Task = "help",

    # Message for "revision" and "restore"
    [string]$Msg
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

# --- Paths ---
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
$PY = Join-Path $ROOT ".venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { $PY = "python" }  # fallback to system python

function Invoke-PS {
    param([string]$File, [string[]]$ArgList)
    $argsLine = ($ArgList -join ' ')
    Write-Host "▶ $File $argsLine"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $File @ArgList
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $File $argsLine" }
}

function Invoke-Cmd {
    param([string]$Cmd)
    Write-Host "▶ $Cmd"
    powershell -NoProfile -ExecutionPolicy Bypass -Command $Cmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Cmd" }
}

switch ($Task) {

    "up" { Invoke-PS ".\dev_setup.ps1" @(); break }
    "watch" { Invoke-PS ".\dev_setup.ps1" @("-Watch"); break }
    "stop" { Invoke-PS ".\dev_stop.ps1" @(); break }
    "down" { Invoke-PS ".\dev_stop.ps1" @(); break }
    "down-prune" { Invoke-PS ".\dev_stop.ps1" @("-Prune"); break }
    "restart" { Invoke-PS ".\dev_restart.ps1" @(); break }
    "reset-db" { Invoke-PS ".\dev_reset_db.ps1" @(); break }

    "migrate" { Invoke-PS ".\dev_migrate.ps1" @(); break }
    "seed" { Invoke-PS ".\dev_migrate.ps1" @("-Seed"); break }
    "revision" {
        if (-not $Msg) { throw "Provide -Msg for revision, e.g. ./makefile.ps1 revision -Msg 'add users table'" }
        Invoke-PS ".\dev_migrate.ps1" @("-RevMsg", $Msg); break
    }

    "logs" { Invoke-PS ".\dev_logs.ps1" @(); break }
    "check-schema" { Invoke-PS ".\dev_check_schema.ps1" @(); break }

    "health" {
        $headers = @{}
        if ($env:API_KEY_EXPERTCO) { $headers["x-api-key"] = $env:API_KEY_EXPERTCO }
        try {
            Write-Host "GET /health"; Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json -Depth 5
            Write-Host "GET /ops/model-status"; Invoke-RestMethod http://localhost:8000/ops/model-status -Headers $headers | ConvertTo-Json -Depth 5
        }
        catch { Write-Host "Health check failed:"; Write-Host $_ }
        break
    }

    "lint" { Invoke-Cmd "pre-commit run --all-files"; break }
    "typecheck" { Invoke-Cmd "mypy ."; break }
    "fmt" { Invoke-Cmd "ruff format ."; break }

    "pre-commit" { Invoke-Cmd "python -m pip install -r requirements-dev.txt; pre-commit install"; break }
    "pre-commit-all" { Invoke-Cmd "pre-commit run --all-files"; break }

    "test" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\test.ps1"; break }
    "backup" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\pg_backup.ps1"; break }
    "restore" {
        if (-not $Msg) { throw "Use -Msg to pass path: ./makefile.ps1 restore -Msg .\backups\aetherlink_xxx.dump" }
        & powershell -NoProfile -ExecutionPolicy Bypass -File ".\pg_restore.ps1" -File $Msg; break
    }

    "coverage" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\coverage.ps1"; break }

    "schedule-backup" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\schedule_nightly_backup.ps1"; break }
    "unschedule-backup" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\unschedule_nightly_backup.ps1"; break }

    "restore-latest" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\pg_restore_latest.ps1"; break }
    "sync-backup" {
        if (-not $Msg) { throw "Pass destination via -Msg, e.g. .\\makefile.ps1 sync-backup -Msg 'C:\\Users\\You\\OneDrive\\AetherLink\\backups'" }
        & powershell -NoProfile -ExecutionPolicy Bypass -File ".\post_backup_sync.ps1" -Dest $Msg; break
    }

    "schedule-sync" {
        if (-not $Msg) { throw "Pass destination via -Msg, e.g. .\\makefile.ps1 schedule-sync -Msg 'C:\\Users\\You\\OneDrive\\AetherLink\\backups'" }
        & powershell -NoProfile -ExecutionPolicy Bypass -File ".\schedule_post_backup_sync.ps1" -Dest $Msg; break
    }
    "unschedule-sync" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\unschedule_post_backup_sync.ps1"; break }

    "verify" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\verify_e2e.ps1"; break }
    "verify-seed" { & powershell -NoProfile -ExecutionPolicy Bypass -File ".\verify_e2e.ps1" -Seed; break }

    "reload-auth" {
      $headers = @{}
      if ($env:API_ADMIN_KEY)     { $headers["x-admin-key"] = $env:API_ADMIN_KEY }
      if ($env:API_KEY_EXPERTCO)  { $headers["x-api-key"]   = $env:API_KEY_EXPERTCO }
      try {
        Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $headers | ConvertTo-Json -Depth 5
      } catch { Write-Host "Reload failed:"; Write-Host $_ }
      break
    }

    default {
        Write-Host @"
AetherLink Makefile (PowerShell)

STACK
  up                 Start dev stack
  watch              Start dev stack with self-heal watch
  stop               Stop API/Worker & containers
  reset-db           Drop/clean Postgres dev volume & recreate

DB / MIGRATIONS
  migrate            Alembic upgrade head
  seed               Alembic upgrade + run seeds
  revision -Msg "..." Create new Alembic revision with message
  check-schema       Fail if models != DB (schema drift guard)

DEV UTIL
  logs               Tail Redis/Postgres logs + ping health
  health             Quick API health + model-status check

QUALITY
  fmt                Ruff format
  lint               Run all pre-commit hooks on repo
  typecheck          mypy .

META
  pre-commit         Install hooks (one-time + ensure deps)
  pre-commit-all     Run all hooks against repo

Examples:
  ./makefile.ps1 up
  ./makefile.ps1 revision -Msg "add customer table"
  ./makefile.ps1 verify-seed
"@
    }
}
