# Quick dependency installer for AetherLink
# Run this if you see "ModuleNotFoundError: No module named 'backoff'"

$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
Set-Location $ROOT

Write-Host "`n[Installing Dependencies]" -ForegroundColor Cyan
Write-Host "This will take 1-2 minutes..." -ForegroundColor Yellow

# Upgrade pip first
Write-Host "`nUpgrading pip..." -ForegroundColor Gray
.\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet

# Install from requirements.txt
Write-Host "Installing from requirements.txt..." -ForegroundColor Gray
.\.venv\Scripts\python.exe -m pip install -r pods\customer_ops\requirements.txt --quiet

# Ensure critical libs
Write-Host "Ensuring critical libraries (backoff, scikit-learn, scipy, numpy)..." -ForegroundColor Gray
.\.venv\Scripts\python.exe -m pip install backoff scikit-learn scipy numpy --quiet

# Verify
Write-Host "`nVerifying installation..." -ForegroundColor Cyan
$verification = .\.venv\Scripts\python.exe -c @"
try:
    import backoff, sklearn, scipy, numpy
    print('OK')
except ImportError as e:
    print(f'ERROR: {e}')
"@ 2>&1

if ($verification -eq "OK") {
    Write-Host "✅ All dependencies installed successfully!" -ForegroundColor Green
    Write-Host "`nYou can now run:" -ForegroundColor Cyan
    Write-Host "  .\LAUNCH_AB_SYSTEM.ps1" -ForegroundColor White
} else {
    Write-Host "❌ Installation failed: $verification" -ForegroundColor Red
    Write-Host "`nTry manually:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\pip.exe install backoff scikit-learn scipy numpy" -ForegroundColor White
}
