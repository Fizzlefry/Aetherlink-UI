# ---- CONFIG ----
$ApiBase = "http://localhost:8000"
$UseApiKey = $false          # set to $true if REQUIRE_API_KEY=true
$ApiKey   = "ACME_KEY"       # set to a valid key if $UseApiKey

# ---- 1) Up stack (detached) ----
$pushed = $false
if ($PWD.Path -notlike "*\pods\customer_ops") {
  Push-Location pods/customer_ops
  $pushed = $true
}
docker compose up --build -d

# ---- 2) Wait for healthz (up to 90s) ----
$healthy = $false
for ($i=0; $i -lt 90; $i++) {
  try {
    $resp = Invoke-RestMethod "$ApiBase/healthz" -TimeoutSec 2
    if ($resp) { $healthy = $true; break }
  } catch {}
  Start-Sleep -Seconds 1
}
if (-not $healthy) {
  Write-Host "`n❌ Timed out waiting for $ApiBase/healthz" -ForegroundColor Red
  docker compose ps
  docker compose logs api --no-color | Select-String -Context 2,2 -Pattern "ERROR|Exception|Traceback"
  if ($pushed) { Pop-Location }
  exit 1
}
Write-Host "✅ Health OK:" -ForegroundColor Green
$resp | ConvertTo-Json -Compress | Write-Host

# ---- Headers (optional API key) ----
$headers = @{"content-type"="application/json"}
if ($UseApiKey) { $headers["x-api-key"] = $ApiKey }

# ---- 3) Create lead ----
$body = '{"name":"Jon","phone":"7632801272","details":"Metal roof"}'
try {
  $leadResp = Invoke-RestMethod -Uri "$ApiBase/v1/lead" -Method Post -Headers $headers -Body $body -ContentType 'application/json'
  Write-Host "`n✅ Create Lead OK:" -ForegroundColor Green
  $leadResp | ConvertTo-Json -Depth 6
} catch {
  Write-Host "`n❌ Create Lead failed:" -ForegroundColor Red
  $_.Exception.Message
  if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ }
}

# ---- 4) List leads ----
try {
  $listResp = Invoke-RestMethod -Uri "$ApiBase/v1/lead" -Method Get -Headers $headers
  Write-Host "`n✅ List Leads OK:" -ForegroundColor Green
  $listResp | ConvertTo-Json -Depth 6
} catch {
  Write-Host "`n❌ List Leads failed:" -ForegroundColor Red
  $_.Exception.Message
}

# ---- 5) Metrics (filter intent counter) ----
try {
  $metricsRaw = Invoke-WebRequest -Uri "$ApiBase/metrics" -UseBasicParsing
  Write-Host "`n✅ Metrics (agent_intent_total):" -ForegroundColor Green
  ($metricsRaw.Content -split "`n" | Select-String "agent_intent_total") -join "`n"
} catch {
  Write-Host "`n❌ Metrics failed:" -ForegroundColor Red
  $_.Exception.Message
}

# ---- 6) Down stack ----
docker compose down
if ($pushed) { Pop-Location }
