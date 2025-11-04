<#
Runs pytest with coverage. Generates HTML coverage under htmlcov\ and a terminal summary.
Usage:
  .\test.ps1                 # run full test suite
  .\test.ps1 -k "customer"   # run subset (pytest -k)
#>
param(
    [string]$k
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'
$ROOT = (Get-Location).Path
$PY = Join-Path $ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $PY)) { $PY = 'python' }

# ensure deps
& $PY - <<'PY'
import sys, subprocess
def ensure(pkg):
try: __import__(pkg.split("[", 1)[0])
except Exception: subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
for p in ("pytest", "pytest-cov"):
ensure(p)
PY

$covArgs = @("--cov=.", "--cov-report=term-missing", "--cov-report=html")
$kArgs = if ($k) { @("-k", $k) } else { @() }

Write-Host "🧪 Running tests..."
& $PY -m pytest @kArgs @covArgs
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }

Write-Host "✅ Tests passed."
Write-Host "📊 Coverage report: $((Join-Path $ROOT 'htmlcov\index.html'))"
