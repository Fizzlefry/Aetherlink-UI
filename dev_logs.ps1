# Tails container logs and pings API health every 5s
Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'SilentlyContinue'

function Ping-Url($url) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
    $s = $r.StatusCode
    $lat = if ($r.RawContentLength) { "$($r.RawContentLength)B" } else { "-" }
    Write-Host ("[{0:HH:mm:ss}] {1} -> {2} ({3})" -f (Get-Date), $url, $s, $lat)
  } catch {
    Write-Host ("[{0:HH:mm:ss}] {1} -> FAIL" -f (Get-Date), $url)
  }
}

Write-Host "📜 Tailing docker logs (Ctrl+C to stop)..."
$jobs = @()
$jobs += Start-Job { docker logs -f aether-redis }
$jobs += Start-Job { docker logs -f aether-postgres }

try {
  while ($true) {
    Ping-Url 'http://localhost:8000/health'
    Ping-Url 'http://localhost:8000/ops/model-status'
    Start-Sleep -Seconds 5
    Receive-Job -Job $jobs -Keep | ForEach-Object { $_ }
  }
} finally {
  $jobs | Remove-Job -Force 2>$null
}