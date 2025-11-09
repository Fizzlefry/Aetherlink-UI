# scripts/dev-gpt.ps1
# Launch AetherLink dev shell in GPT/OpenAI mode

param(
    [string]$Repo = "C:\Users\jonmi\OneDrive\Documents\AetherLink",
    [switch]$Reload = $true
)

# === provider/env ===
$env:OPENAI_API_KEY  = $env:OPENAI_API_KEY  # if already set in profile, keep it
$env:MODEL_PROVIDER  = "openai"
$env:MODEL_NAME      = "gpt-4o-mini"    # change if you use a different label
Remove-Item Env:\ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

Write-Host "🔁 AetherLink dev in GPT/OpenAI mode" -ForegroundColor Green

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
