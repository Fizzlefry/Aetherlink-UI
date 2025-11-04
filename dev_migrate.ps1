<#
Runs DB migrations (alembic upgrade head) and optional seed.
Usage:
  .\dev_migrate.ps1                 # migrate only
  .\dev_migrate.ps1 -Seed           # migrate + seed
  .\dev_migrate.ps1 -RevMsg "init"  # create revision with message (no migrate)
#>

param(
  [switch]$Seed,
  [string]$RevMsg
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

# --- Paths & Python ---
$ROOT = (Get-Location).Path
$PY = Join-Path $ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $PY)) { throw "Could not find venv python at $PY (create venv first)" }

# --- Env vars required by your app/Alembic env.py ---
$env:PYTHONPATH = $ROOT
if (-not $env:DATABASE_URL) {
  $env:DATABASE_URL = 'postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink'
}

# --- Ensure docker postgres is up (fast check) ---
function Test-TcpPort($Host, $Port, $TimeoutSec = 2) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect($Host, $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds($TimeoutSec))
    if ($ok) { $c.EndConnect($iar); $c.Close(); return $true } else { $c.Close(); return $false }
  } catch { return $false }
}
if (-not (Test-TcpPort 'localhost' 5432 2)) {
  Write-Host "⚠️  Postgres isn't listening on 5432. Start with .\dev_setup.ps1 first." -ForegroundColor Yellow
}

# --- Ensure alembic is installed ---
& $PY - <<'PY'
import sys, subprocess
def ensure(pkg):
    try:
        __import__(pkg)
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
for p in ("alembic", "psycopg2-binary"):
    ensure(p)
PY

# --- Verify alembic.ini exists ---
$alembicIni = Join-Path $ROOT 'alembic.ini'
if (-not (Test-Path $alembicIni)) {
  throw "alembic.ini not found. Create Alembic config (e.g. `alembic init -t async alembic`) and ensure env.py reads DATABASE_URL."
}

# --- Optional: create a revision only ---
if ($RevMsg) {
  Write-Host "📝 Creating alembic revision: $RevMsg"
  & $PY -m alembic revision -m $RevMsg
  exit $LASTEXITCODE
}

# --- Upgrade head ---
Write-Host "⏫ Running alembic upgrade head..."
& $PY -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Alembic failed" }
Write-Host "✅ Migration complete."

# --- Seed (optional) ---
if ($Seed) {
  $seedMod = 'scripts.seed'
  Write-Host "🌱 Running seed module ($seedMod)..."
  & $PY - <<'PY'
import importlib, os, sys
mod = importlib.import_module("scripts.seed")
if hasattr(mod, "main"):
    mod.main()
else:
    print("Seed module found but no main() defined", file=sys.stderr)
PY
  if ($LASTEXITCODE -ne 0) { throw "Seed failed" }
  Write-Host "✅ Seed complete."
}
