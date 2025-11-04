param(
    [switch]$Watch   # Keep monitoring & auto-restart every 60s
)

Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'
Write-Host "Launching AetherLink local stack..."

# ---------- Helpers ----------
function Ensure-Docker {
    try { docker version *>$null } catch { throw "Docker Desktop isn't running. Start it, then retry." }
}

function Test-TcpPort($HostName, $Port, $TimeoutSec = 2) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect($HostName, $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds($TimeoutSec))) { $c.EndConnect($iar); $c.Close(); return $true }
        $c.Close(); return $false
    }
    catch { return $false }
}

function Wait-ForPort($Name, $HostName, $Port, $Retries = 30) {
    for ($i = 1; $i -le $Retries; $i++) {
        if (Test-TcpPort $HostName $Port 2) { Write-Host "$Name is accepting connections on ${HostName}:${Port}"; return }
        Start-Sleep -Milliseconds 500
    }
    throw "❌ $Name did not become ready on ${HostName}:${Port}"
}

function Start-Or-RunDocker($name, $runArgs, $readyHost, $readyPort) {
    Write-Host "Ensuring $name container is running..."
    $exists = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $name }
    if ($exists) {
        $running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $name }
        if (-not $running) { docker start $name | Out-Null }
    }
    else {
        docker run -d --name $name @$runArgs | Out-Null
    }
    Wait-ForPort $name $readyHost $readyPort
}

function Start-ChildWindow($title, $cmd) {
    Start-Process powershell -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-Command', $cmd) -WindowStyle Normal
    Write-Host "Started: $title"
}

function Wait-ForUrlHealthy($url, $tries = 30) {
    for ($i = 1; $i -le $tries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -in 200..204) { return $true }
        }
        catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

# ---------- Prep ----------
Ensure-Docker
try { docker pull redis:7 *>$null } catch {}
try { docker pull postgres:15 *>$null } catch {}

$ROOT = (Get-Location).Path
$PY = Join-Path $ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $PY)) { throw "Could not find venv python at $PY" }

$env:PYTHONPATH = $ROOT
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:DATABASE_URL = 'postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink'

# ---------- Quick import sanity ----------
$check = @'
import importlib, sys
for m in ("uvicorn","psycopg2","backoff","sqlalchemy"):
    try:
        importlib.import_module(m)
    except Exception as e:
        print(f"[WARN] Missing/failed import: {m} -> {e}", file=sys.stderr)
'@
$check | & $PY -

# ---------- Start Docker services ----------
Start-Or-RunDocker `
    -name 'aether-redis' `
    -runArgs @('-p', '6379:6379', 'redis:7') `
    -readyHost 'localhost' -readyPort 6379

Start-Or-RunDocker `
    -name 'aether-postgres' `
    -runArgs @(
    '-e', 'POSTGRES_USER=aether', '-e', 'POSTGRES_PASSWORD=aetherpass', '-e', 'POSTGRES_DB=aetherlink',
    '-p', '5432:5432',
    '-v', 'aetherlink_pgdata:/var/lib/postgresql/data',
    'postgres:15'
) `
    -readyHost 'localhost' -readyPort 5432

# ---------- Launch API & Worker ----------
$commonEnv = @"
`$env:PYTHONPATH = '$ROOT'
`$env:REDIS_URL = 'redis://localhost:6379/0'
`$env:DATABASE_URL = 'postgresql+psycopg2://aether:aetherpass@localhost:5432/aetherlink'
"@

$apiCmd = @"
$commonEnv
& '$PY' -m uvicorn pods.customer_ops.api.main:app --host 0.0.0.0 --port 8000 --reload
"@
Start-ChildWindow "API" $apiCmd

$workerCmd = @"
$commonEnv
& '$PY' pods\customer_ops\worker.py
"@
Start-ChildWindow "Worker" $workerCmd

# ---------- Health gates ----------
Write-Host "Waiting for API health..."
if (Wait-ForUrlHealthy 'http://localhost:8000/health') {
    Write-Host "API health OK"
}
else {
    Write-Host "API did not report healthy. Check the API window for tracebacks."
}

# ---------- Optional watch ----------
if ($Watch) {
    Write-Host "Watch mode enabled (checks every 60s). Press Ctrl+C in THIS window to stop."
    while ($true) {
        Start-Sleep -Seconds 60
        if (-not (Wait-ForUrlHealthy 'http://localhost:8000/health' 5)) {
            Write-Host "API unhealthy—restarting..."
            Start-ChildWindow "API (restart)" $apiCmd
        }
        if (-not (Wait-ForUrlHealthy 'http://localhost:8000/ops/model-status' 5)) {
            Write-Host "Worker unhealthy—restarting..."
            Start-ChildWindow "Worker (restart)" $workerCmd
        }
    }
}

Write-Host "AetherLink environment launched."
Write-Host "Health:  http://localhost:8000/health"
Write-Host "Status:  http://localhost:8000/ops/model-status"
