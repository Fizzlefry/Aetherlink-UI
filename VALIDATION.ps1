# AetherLink — 60-second validation

# 1) Launch
.\makefile.ps1 up

# 2) Health + status (will use API_KEY_EXPERTCO from environment if set)
.\makefile.ps1 health

# Or check manually:
# Invoke-RestMethod http://localhost:8000/health
# $h = @{ "x-api-key" = "ABC123" }
# Invoke-RestMethod http://localhost:8000/ops/model-status -Headers $h

# 2b) Optional: Test hot-reload auth
# .\test_hot_reload_auth.ps1

# 3) One-shot verify (backup → restore → health)
.\makefile.ps1 verify

# 4) Restart loop
.\makefile.ps1 restart

# 5) Clean stop (and prune, if you like)
.\makefile.ps1 down
.\makefile.ps1 down-prune
