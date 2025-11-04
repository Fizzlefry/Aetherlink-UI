<#
Opens htmlcov\index.html (pytest-cov). If missing, runs tests first.
Usage:
  .\coverage.ps1
#>
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

$ROOT = (Get-Location).Path
$HTML = Join-Path $ROOT 'htmlcov\index.html'

function Run-Tests {
    if (Test-Path '.\test.ps1') {
        Write-Host "🧪 Running tests to generate coverage..."
        & powershell -NoProfile -ExecutionPolicy Bypass -File '.\test.ps1'
    }
    else {
        # Fallback if wrapper missing
        $PY = Join-Path $ROOT '.venv\Scripts\python.exe'
        if (-not (Test-Path $PY)) { $PY = 'python' }
        Write-Host "🧪 Running pytest + coverage (wrapper not found)..."
        & $PY -m pip install -q pytest pytest-cov | Out-Null
        & $PY -m pytest --cov=. --cov-report=term-missing --cov-report=html
    }
}

if (-not (Test-Path $HTML)) {
    Run-Tests
}

if (-not (Test-Path $HTML)) {
    throw "Coverage HTML not found at $HTML (did tests fail?)."
}

Write-Host "📂 Opening: $HTML"
# Use Start-Process to launch default browser
Start-Process $HTML
Write-Host "✅ Coverage opened."
