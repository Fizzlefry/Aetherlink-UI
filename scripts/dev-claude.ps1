# scripts/dev-claude.ps1
# Launch AetherLink dev shell in Claude/Anthropic mode

param(
    [string]$Repo = "C:\Users\jonmi\OneDrive\Documents\AetherLink",
    [switch]$Reload = $true
)

# === provider/env ===
$env:ANTHROPIC_API_KEY = $env:ANTHROPIC_API_KEY  # pulled from your profile
$env:MODEL_PROVIDER    = "anthropic"
$env:MODEL_NAME        = "claude-3-5-sonnet-20241022"
Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue

Write-Host "🤖 AetherLink dev in Claude/Anthropic mode" -ForegroundColor Cyan

# === go to repo ===
Set-Location $Repo

if ($Reload) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8000/ops/reload" -Method GET
        Write-Host "✅ CustomerOps reloaded: $($r.StatusCode)" -ForegroundColor Yellow
    } catch {
        Write-Host "⚠️ Reload failed (is http://localhost:8000 up?)" -ForegroundColor Red
    }
}

Write-Host "You can now run your normal dev commands (docker-compose, uvicorn, npm/vite)..." -ForegroundColor Cyan
