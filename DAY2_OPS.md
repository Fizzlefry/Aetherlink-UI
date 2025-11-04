# Day-2 Operations Guide

Quick reference for running, monitoring, and recovering the AetherLink CustomerOps API in production.

## Run & Watch

### Tail logs
```powershell
docker logs -f aether-customer-ops
```

### Quick health + metrics
```powershell
# Health check
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing

# Key metrics
(Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content |
  Select-String "api_tenants_count|http_requests_total|lead_enrich_total"
```

## Auth Operations (Hot-Reload & Tenants)

### Rotate in a temp key and reload
```powershell
$adm = @{ "x-api-key" = $env:API_KEY_EXPERTCO; "x-admin-key" = $env:API_ADMIN_KEY }
$env:API_KEY_TEMP = "NEWKEY123"
Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $adm | ConvertTo-Json
```

### Verify the new key works
```powershell
Invoke-RestMethod http://localhost:8000/ops/model-status -Headers @{ "x-api-key"="NEWKEY123" } | ConvertTo-Json
```

### List tenants (admin)
```powershell
Invoke-RestMethod http://localhost:8000/ops/tenants -Headers $adm | ConvertTo-Json
```

### Use rotate-keys helper
```powershell
# Add a new tenant key
.\rotate-keys.ps1 -AddTenants "NEWCO:NEWKEY123"

# Remove a stale key
.\rotate-keys.ps1 -RemoveKeys "OLDKEY1"
```

## Rate Limit Sanity

Expect some 429s after ~5 requests (if rate limiting is active):
```powershell
$h = @{ "x-api-key" = $env:API_KEY_EXPERTCO }
1..8 | % {
  try { Invoke-RestMethod http://localhost:8000/ops/model-status -Headers $h -ErrorAction Stop | Out-Null; "OK" }
  catch { try { $_.Exception.Response.StatusCode.Value__ } catch { 'Err' } }
}
```

## Production Switches

When you're ready to harden for production:

1. **Require keys**: Set `REQUIRE_API_KEY=true`
2. **CORS/hosts**: Set `CORS_ORIGINS=https://your-ui.example`, `ALLOWED_HOSTS=your-api.example,*.your-api.example`
3. **Admin guard**: Set a strong `API_ADMIN_KEY`
4. **Database**: Point `DATABASE_URL` to Postgres (compose or managed service)
5. **Redis limiter**: Ensure `REDIS_URL` points at your prod Redis
6. **Secrets**: Move env vars to a secret store (GitHub Actions/Key Vault/AWS Secrets Manager)

## Prometheus Quick Checks

### Tenants count
```promql
api_tenants_count
```

### Lead enrichment rate (5-minute window)
```promql
rate(lead_enrich_total[5m])
```

### Error ratio (5xx responses)
```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

### Request rate by endpoint
```promql
rate(http_requests_total[5m])
```

## Rollback & Diagnostics

### Health failing
```powershell
# Check recent container logs
docker logs aether-customer-ops --since=10m

# Try readyz if implemented
Invoke-WebRequest http://localhost:8000/readyz -UseBasicParsing
```

### Auth issues
```powershell
# Confirm the in-memory tenant map
$adm = @{ "x-api-key" = $env:API_KEY_EXPERTCO; "x-admin-key" = $env:API_ADMIN_KEY }
Invoke-RestMethod http://localhost:8000/ops/tenants -Headers $adm | ConvertTo-Json

# Reload auth after fixing env
Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $adm | ConvertTo-Json
```

### Rate limiter behavior
If Redis is down, the fallback keeps endpoints live (no blocks). When Redis returns, limits resume automatically.

### Container restart
```powershell
# Restart the API container
docker compose restart api

# Or full stack restart
docker compose down
docker compose up -d
```

## CI/CD Quick Reference

### Build & tag
```powershell
# Build from repo root
docker build -f pods/customer_ops/Dockerfile -t aether/customer-ops:dev .

# Tag for registry
docker tag aether/customer-ops:dev <registry>/aether/customer-ops:<version>

# Push to registry
docker push <registry>/aether/customer-ops:<version>
```

### Deploy
```powershell
# Update image tag in compose file or pass as env
# Then deploy
docker compose up -d
```

## VS Code One-Click Tasks

Use the following tasks from the VS Code Command Palette (`Ctrl+Shift+P` → "Tasks: Run Task"):
- **AetherLink: Health Check** - Quick health probe
- **AetherLink: Reload Auth Keys** - Hot-reload API keys
- **AetherLink: List Tenants** - View active tenants (admin)
- **AetherLink: Check Metrics** - View key Prometheus metrics

## Useful Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `api_tenants_count` | Gauge | Number of active tenants (unique API keys) |
| `lead_enrich_total` | Counter | Count of lead enrichment operations |
| `lead_outcome_total` | Counter | Count of lead outcomes by type |
| `http_requests_total` | Counter | Total HTTP requests by endpoint, method, status |
| `http_request_duration_seconds` | Histogram | Request duration distribution |

## Common Troubleshooting

### "Unable to connect" on localhost:8000
- Check if container is running: `docker ps | findstr aether-customer-ops`
- Check container logs: `docker logs aether-customer-ops`
- Verify port binding: `netstat -ano | findstr ":8000"`

### "Invalid or missing API key" (when REQUIRE_API_KEY=true)
- Confirm key is set: `echo $env:API_KEY_EXPERTCO`
- Check the in-memory map: `/ops/tenants` endpoint
- Reload auth: `/ops/reload-auth` endpoint

### Rate limit not working
- Check Redis connectivity: `docker logs aether-customer-ops | Select-String redis`
- Fallback mode keeps API live; limits resume when Redis is healthy

### Database connection errors
- Check `DATABASE_URL` env var
- For Postgres, ensure host is reachable from container
- For SQLite, check file permissions and path

---

**Quick smoke test**: Run the 60-second verification script:
```powershell
.\verify_production_ready.ps1
```

For detailed metric setup and Grafana dashboards, see [METRICS_GUIDE.md](./METRICS_GUIDE.md).
