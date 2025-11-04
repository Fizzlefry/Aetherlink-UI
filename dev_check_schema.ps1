Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

$PY = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
if (-not (Test-Path $PY)) { $PY = 'python' }

Write-Host "🔎 Checking Alembic schema drift..."
& $PY scripts\check_alembic_clean.py
