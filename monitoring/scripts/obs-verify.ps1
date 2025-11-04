# AetherLink Observability Verification
# Runs all pre-deployment checks: promtool rules check, tests, and vision status

Write-Host "`n=== Observability Verification ===" -ForegroundColor Cyan

# 1. Prometheus rules syntax check
Write-Host "`n[Prometheus Rules Check]" -ForegroundColor Yellow
docker run --rm --entrypoint promtool -v ${PWD}:/w -w /w prom/prometheus:v2.54.1 `
    check rules monitoring/prometheus-recording-rules.yml monitoring/prometheus-alerts.yml

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Prometheus rules check" -ForegroundColor Red
    exit 1
}

# 2. Prometheus rule tests
Write-Host "`n[Rule Tests]" -ForegroundColor Yellow
docker run --rm --entrypoint promtool -v ${PWD}:/w -w /w prom/prometheus:v2.54.1 `
    test rules monitoring/tests/rules.test.yml

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Promtool tests" -ForegroundColor Red
    exit 1
}

# 3. Alertmanager config check
Write-Host "`n[Alertmanager Config Check]" -ForegroundColor Yellow
docker run --rm --entrypoint amtool -v ${PWD}/monitoring:/conf quay.io/prometheus/alertmanager:latest `
    check-config /conf/alertmanager.yml

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Alertmanager config check" -ForegroundColor Red
    exit 1
}# 4. AetherVision snapshot
Write-Host "`n[AetherVision Snapshot]" -ForegroundColor Yellow
Push-Location monitoring
.\scripts\vision-verify.ps1
Pop-Location

Write-Host "`n=== All Checks Passed ===" -ForegroundColor Green
