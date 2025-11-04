# RELEASE.md

## Production Release Checklist

This document outlines the deployment ritual for releasing AetherLink CustomerOps to production.

---

## Pre-Release Checklist

### 1. Code Quality & Testing
- [ ] All tests passing locally
  ```powershell
  cd pods/customer_ops
  pytest test_duckdb_vectors.py -v    # 4/4 tests
  pytest test_admin_overview.py -v    # 3/3 tests
  pytest test_audit_log.py -v         # 3/3 tests
  ```
- [ ] No lint errors or warnings
- [ ] Code reviewed (if team environment)

### 2. Configuration Review
- [ ] `.env` file reviewed and secrets updated
  - [ ] `ADMIN_KEY` changed from default
  - [ ] `EMBED_PROVIDER` configured correctly
  - [ ] `DUCKDB_PATH` points to production data directory
  - [ ] `AUDIT_PATH` configured for audit logging
- [ ] `.env.example` updated with any new variables
- [ ] `docker-compose.yml` healthchecks enabled

### 3. Security Hardening
- [ ] Rate limiting enabled on `/search` endpoint (60 req/min per IP)
- [ ] RBAC roles verified (Admin, Viewer, AnyRole)
- [ ] Audit log tamper detection tested
  ```powershell
  cd pods/customer_ops
  python -c "from audit import verify_chain; print(verify_chain('data/audit/ops.jsonl'))"
  ```

---

## Release Steps

### Step 1: Tag Release
Create a git tag for version tracking:
```powershell
git tag -a v1.0.0 -m "Production release: DuckDB+VSS, Admin Dashboard, Audit Log, Hardening"
git push origin v1.0.0
```

### Step 2: Build Docker Images
Build fresh images without cache to ensure clean build:
```powershell
cd pods/customer_ops
docker compose build --no-cache
```

**Expected output:** `Successfully tagged aether/customer-ops:dev`

### Step 3: Start Services with Healthchecks
Start all services and verify healthchecks:
```powershell
docker compose up -d
Start-Sleep -Seconds 30  # Wait for services to start
docker compose ps
```

**Expected output:** All services showing `(healthy)` status
- `aether-customer-ops` (api) - healthy
- `aether-customer-ops-worker` (worker) - healthy
- `aether-redis` - healthy

**Healthcheck verification:**
```powershell
# API healthcheck (wget on /health)
docker exec aether-customer-ops wget -qO- http://localhost:8000/health

# Worker healthcheck (Redis ping)
docker exec aether-customer-ops-worker python -c "import redis; r=redis.Redis.from_url('redis://redis:6379/0'); print('OK' if r.ping() else 'FAIL')"
```

### Step 4: Verify Audit Log Integrity
Check that audit log chain is valid:
```powershell
cd pods/customer_ops
docker exec aether-customer-ops python -c "from pods.customer_ops.audit import verify_chain; result = verify_chain('/app/data/audit/ops.jsonl'); print(f'Valid: {result[\"valid\"]}, Entries: {result[\"total_entries\"]}')"
```

**Expected output:** `Valid: True, Entries: <count>`

### Step 5: Create Pre-Release Backup
Run backup script before deployment:
```powershell
cd pods/customer_ops
.\BACKUP.ps1
```

**Expected output:**
- Backup folder created with timestamp
- DuckDB and audit log copied
- Compressed to `.zip` file
- Old backups (>7 days) cleaned up

**Verify backup:**
```powershell
Get-ChildItem C:\Users\jonmi\OneDrive\Documents\AetherLink\backups -Filter "backup_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

---

## Post-Release Verification (Smoke Tests)

### Test 1: API Health
```powershell
curl http://localhost:8000/health
```
**Expected:** `{"status":"ok"}`

### Test 2: Admin Dashboard
```powershell
curl -H "x-api-key: admin-secret-123" http://localhost:8000/admin/overview
```
**Expected:** JSON with `documents` array and recent ingests

### Test 3: Semantic Search (Rate Limiting)
Test rate limiting by hitting search 61 times:
```powershell
# First 60 requests should succeed
for ($i=1; $i -le 60; $i++) {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/search?q=test&k=3" -Method GET -Headers @{"x-api-key"="test-key"} -UseBasicParsing
    if ($response.StatusCode -ne 200) { Write-Host "Failed at request $i" }
}

# 61st request should return 429 (Rate Limit Exceeded)
try {
    Invoke-WebRequest -Uri "http://localhost:8000/search?q=test&k=3" -Method GET -Headers @{"x-api-key"="test-key"} -UseBasicParsing
    Write-Host "FAIL: Should have been rate limited"
} catch {
    if ($_.Exception.Response.StatusCode -eq 429) {
        Write-Host "PASS: Rate limiting working (429 returned)"
    } else {
        Write-Host "FAIL: Unexpected error: $($_.Exception.Message)"
    }
}
```

### Test 4: Document Ingestion & Audit
Ingest a test URL and verify audit log:
```powershell
# Ingest URL
$body = @{
    url = "https://example.com"
    source = "smoke-test"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/ingest-url" -Method POST -Body $body -ContentType "application/json" -Headers @{"x-api-key"="test-key"}

# Wait for job to complete
Start-Sleep -Seconds 5

# Check audit log
docker exec aether-customer-ops tail -n 1 /app/data/audit/ops.jsonl
```
**Expected:** New audit entry with `event_type: ingest_url`

### Test 5: DuckDB Vector Search
Query the ingested document:
```powershell
curl "http://localhost:8000/search?q=example&k=5" -H "x-api-key: test-key"
```
**Expected:** JSON with `results` array containing semantic matches

---

## Rollback Procedure

If issues are detected post-release:

### Step 1: Stop Services
```powershell
cd pods/customer_ops
docker compose down
```

### Step 2: Restore from Backup
```powershell
# Extract latest backup
$latestBackup = Get-ChildItem C:\Users\jonmi\OneDrive\Documents\AetherLink\backups -Filter "backup_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Expand-Archive -Path $latestBackup.FullName -DestinationPath "C:\temp\restore" -Force

# Copy files back
Copy-Item "C:\temp\restore\backup_*\knowledge.duckdb" -Destination "data\knowledge.duckdb" -Force
Copy-Item "C:\temp\restore\backup_*\audit\ops.jsonl" -Destination "data\audit\ops.jsonl" -Force
```

### Step 3: Revert Code (if needed)
```powershell
git checkout <previous-tag>
docker compose build --no-cache
docker compose up -d
```

---

## Monitoring Checklist

After release, monitor for:
- [ ] API response times (Prometheus metrics at `/metrics`)
- [ ] Error rates (`errors_total` counter)
- [ ] Rate limit hits (`429` responses)
- [ ] Healthcheck failures in `docker compose ps`
- [ ] Audit log integrity (run `verify_chain()` daily)
- [ ] Disk space for DuckDB and audit logs

---

## Scheduled Maintenance

### Daily Tasks
- [ ] Run `BACKUP.ps1` (schedule in Windows Task Scheduler at 2 AM)
- [ ] Verify audit log integrity
  ```powershell
  docker exec aether-customer-ops python -c "from pods.customer_ops.audit import verify_chain; print(verify_chain('/app/data/audit/ops.jsonl'))"
  ```

### Weekly Tasks
- [ ] Review backup retention (keep last 7 days)
- [ ] Check DuckDB size and performance
  ```powershell
  docker exec aether-customer-ops python -c "import duckdb; conn = duckdb.connect('/app/data/knowledge.duckdb'); print(conn.execute('SELECT COUNT(*) FROM chunks').fetchone())"
  ```

### Monthly Tasks
- [ ] Update dependencies (`pip list --outdated`)
- [ ] Security audit (check for CVEs)
- [ ] Review rate limit thresholds based on usage

---

## Troubleshooting

### Healthcheck Failures
**API healthcheck failing:**
```powershell
docker logs aether-customer-ops --tail 50
```
Check for errors in startup or `/health` endpoint.

**Worker healthcheck failing:**
```powershell
docker logs aether-customer-ops-worker --tail 50
docker exec aether-redis redis-cli ping
```
Verify Redis connection and worker startup.

### Audit Log Issues
**Chain verification failed:**
```powershell
docker exec aether-customer-ops python pods/customer_ops/audit_verify.py
```
Review output for first error index and message.

### Rate Limiting Issues
**Too aggressive (legitimate users blocked):**
- Increase `SEARCH_RATE_LIMIT` in `main.py` (currently 60 req/min)
- Consider IP whitelisting for internal services

**Not working (abuse detected):**
- Check logs for rate limit hits
- Verify client IP detection in load balancer setup

---

## Emergency Contacts

- **Ops Lead:** [Your contact]
- **On-Call Engineer:** [Your contact]
- **Backup Admin:** [Your contact]

---

## Version History

| Version | Date       | Changes                                      |
|---------|------------|----------------------------------------------|
| v1.0.0  | 2024-01-XX | Initial production release with hardening    |
