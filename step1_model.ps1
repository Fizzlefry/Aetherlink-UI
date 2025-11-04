# ════════════════════════════════════════════════════════════════
# 1) OPTIONAL: Seed Initial Model (Control window)
# ════════════════════════════════════════════════════════════════
$ROOT = "$env:USERPROFILE\OneDrive\Documents\AetherLink"
cd $ROOT
$env:PYTHONPATH = $ROOT

Write-Host "`n[1] Training Initial Model" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (Test-Path "pods\customer_ops\api\model.json") {
    Write-Host "✅ Model already exists (pods\customer_ops\api\model.json)" -ForegroundColor Green
    Write-Host "   Skipping training. Delete the file to retrain." -ForegroundColor Gray
} else {
    Write-Host "Training model with synthetic data..." -ForegroundColor Yellow
    .\.venv\Scripts\python.exe pods\customer_ops\scripts\train_model.py

    if (Test-Path "pods\customer_ops\api\model.json") {
        Write-Host "✅ Model trained successfully!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Model training failed (API will fail-open)" -ForegroundColor Yellow
    }
}
