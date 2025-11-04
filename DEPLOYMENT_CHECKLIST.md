# 🚀 Auto Follow-Up Engine - Deployment Checklist

## Pre-Deployment

### ✅ Code Complete
- [x] Task module created (`api/tasks_followup.py`)
- [x] Worker process created (`worker.py`)
- [x] Main app integration (`api/main.py`)
- [x] Config flags added (`api/config.py`)
- [x] Docker service added (`docker-compose.dev.yml`)
- [x] Tests written (`tests/test_followup_rules.py`)
- [x] Verification script (`scripts/test_followup.ps1`)
- [x] Documentation (`FOLLOWUP_ENGINE.md`)

### ✅ Tests Pass
- [x] Unit tests (10/10 passed)
- [ ] Integration test (run after deployment)

---

## Deployment Steps

### 1. Install Dependencies
```bash
cd pods/customer_ops
pip install -r requirements.txt
```

**Expected**: RQ >= 1.16.2 installed

### 2. Configure Environment
Edit `.env` file:
```bash
# Required
REDIS_URL=redis://localhost:6379/0

# Follow-Up Engine
FOLLOWUP_ENABLED=true
FOLLOWUP_QUEUE=followups
FOLLOWUP_RULE_TOP_P=0.70
FOLLOWUP_SCHEDULES=30m,2h
```

**Verify**: `cat .env | grep FOLLOWUP`

### 3. Build Docker Images
```bash
cd deploy
docker-compose -f docker-compose.dev.yml build
```

**Expected**: `aetherlink-customerops-api` and `worker` images built

### 4. Start Services
```bash
docker-compose -f docker-compose.dev.yml up -d
```

**Expected**: All services running (db, redis, api, worker, grafana, prometheus)

### 5. Verify Services
```bash
# Check all services are up
docker-compose ps

# Check API logs
docker-compose logs api | grep "followup_queue_enabled"

# Check worker logs
docker-compose logs worker | grep "RQ worker"
```

**Expected**:
- API log: `"msg": "followup_queue_enabled", "queue": "followups"`
- Worker log: `RQ worker 'rq:worker:...' started`

---

## Post-Deployment Verification

### 1. Test Queue Status Endpoint
```bash
curl http://localhost:8000/ops/followup/queue \
  -H "x-api-key: dev-key-123"
```

**Expected**:
```json
{
  "enabled": true,
  "queue": "followups",
  "jobs": {"queued": 0, "scheduled": 0}
}
```

### 2. Create High-Prob Lead
```bash
curl -X POST http://localhost:8000/v1/lead \
  -H "x-api-key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alex Rivera",
    "phone": "+1-555-0199",
    "details": "Urgent: Need to book immediately for tomorrow morning. Budget $5000, credit card ready."
  }'
```

**Expected**:
- Response includes `pred_prob` >= 0.70
- API logs show: `"msg": "followups_enqueued", "count": 2`

### 3. Check Queue Status Again
```bash
curl http://localhost:8000/ops/followup/queue \
  -H "x-api-key: dev-key-123"
```

**Expected**:
```json
{
  "enabled": true,
  "queue": "followups",
  "jobs": {"queued": 0, "scheduled": 2}
}
```

### 4. Run Full Verification Script
```powershell
cd scripts
pwsh test_followup.ps1
```

**Expected**: All 4 checks pass ✓

### 5. Monitor Worker Execution (after delay)
```bash
# Wait for first follow-up (30 minutes)
sleep 1800

# Check worker logs
docker-compose logs worker | grep "followup_executed"

# Check API logs for hook callback
docker-compose logs api | grep "followup_hook_received"
```

**Expected**:
- Worker log: `"msg": "followup_executed", "status_code": 200`
- API log: `"msg": "followup_hook_received", "strategy": "1800s"`

### 6. Check Prometheus Metrics
```bash
curl http://localhost:8000/metrics | grep FOLLOWUP_JOBS_TOTAL
```

**Expected**:
```
FOLLOWUP_JOBS_TOTAL{strategy="1800s",result="success"} 1.0
```

---

## Troubleshooting

### Issue: Queue not enabled
**Symptom**: `/ops/followup/queue` returns `{"enabled": false}`

**Fix**:
1. Check `.env` has `FOLLOWUP_ENABLED=true`
2. Verify Redis is running: `docker-compose ps redis`
3. Check API logs for `followup_queue_disabled` error
4. Restart API: `docker-compose restart api`

### Issue: Tasks not enqueued
**Symptom**: High-prob lead created but scheduled count = 0

**Fix**:
1. Verify `pred_prob >= 0.70` in API response
2. Check API logs for `followups_enqueued` message
3. Confirm queue is enabled (see above)
4. Check `FOLLOWUP_SCHEDULES` is set: `echo $FOLLOWUP_SCHEDULES`

### Issue: Worker not executing tasks
**Symptom**: Scheduled tasks don't execute after delay

**Fix**:
1. Verify worker is running: `docker-compose ps worker`
2. Check worker logs: `docker-compose logs worker`
3. Ensure `REDIS_URL` in worker matches API
4. Restart worker: `docker-compose restart worker`

### Issue: Hook callback fails
**Symptom**: Worker logs show `status_code: 500` or connection error

**Fix**:
1. Check API is reachable from worker container
2. Verify API key is passed correctly
3. Check API logs for error details
4. Test hook manually:
   ```bash
   curl -X POST http://api:8000/ops/followup-hook \
     -H "x-api-key: dev-key-123" \
     -H "Content-Type: application/json" \
     -d '{"lead_id": "test", "strategy": "test", "message": "test"}'
   ```

---

## Rollback Plan

If issues occur, disable follow-up engine:

### Option 1: Environment Variable
```bash
# In .env
FOLLOWUP_ENABLED=false

# Restart services
docker-compose restart api worker
```

### Option 2: Stop Worker Only
```bash
docker-compose stop worker
```

**Effect**: API continues, no follow-ups enqueued, existing tasks remain in queue

### Option 3: Full Rollback
```bash
# Revert code changes
git revert <commit-hash>

# Rebuild and restart
docker-compose down
docker-compose up --build
```

---

## Monitoring

### Dashboard Queries (Prometheus)

```promql
# Follow-up execution rate
rate(FOLLOWUP_JOBS_TOTAL[5m])

# Success vs error ratio
sum by (result) (FOLLOWUP_JOBS_TOTAL)

# Strategy distribution
sum by (strategy) (FOLLOWUP_JOBS_TOTAL)
```

### Key Metrics to Watch

1. **FOLLOWUP_JOBS_TOTAL** - Task execution counter
   - Target: Increasing over time (proportional to high-prob leads)
   - Alert: High error rate (result="error")

2. **Queue Status** (`/ops/followup/queue`)
   - Target: scheduled count matches expected (2x high-prob leads)
   - Alert: Scheduled count growing unbounded (worker down)

3. **API Logs** - `followups_enqueued` messages
   - Target: 1-2 per high-prob lead
   - Alert: None logged despite high-prob leads

4. **Worker Logs** - `followup_executed` messages
   - Target: 1 per scheduled task after delay
   - Alert: No executions after expected delay

---

## Success Criteria

- [x] Worker starts without errors
- [ ] Queue status endpoint returns `enabled: true`
- [ ] High-prob lead triggers follow-ups (scheduled count increases)
- [ ] Low-prob lead does NOT trigger follow-ups
- [ ] Worker executes tasks after delay
- [ ] Hook callback succeeds (status_code: 200)
- [ ] Metrics show FOLLOWUP_JOBS_TOTAL increasing
- [ ] No errors in API or worker logs

---

## Next Steps After Deployment

### Short-Term (1-2 days)
1. Monitor metrics for 24-48 hours
2. Validate task execution timing (30m, 2h)
3. Check hook callbacks are received
4. Verify no memory leaks or performance issues

### Medium-Term (1-2 weeks)
1. Analyze conversion impact (outcome tracking)
2. Adjust threshold if needed (current: 0.70)
3. Tune schedule delays based on engagement
4. Consider adding more follow-up steps

### Long-Term (1-3 months)
1. Implement Twilio SMS integration
2. Add email follow-ups (SendGrid)
3. Build A/B testing framework
4. Add outcome feedback loop (learn from results)

---

## Sign-Off

- [ ] Code reviewed
- [ ] Tests pass (10/10)
- [ ] Documentation complete
- [ ] Environment configured
- [ ] Services deployed
- [ ] Verification script passes
- [ ] Monitoring configured
- [ ] Team trained on ops endpoints

**Deployment Date**: ___________  
**Deployed By**: ___________  
**Verified By**: ___________  

---

## Support

- **Documentation**: `pods/customer_ops/FOLLOWUP_ENGINE.md`
- **Tests**: `pods/customer_ops/tests/test_followup_rules.py`
- **Verification**: `scripts/test_followup.ps1`
- **Logs**: `docker-compose logs -f api worker`
- **Metrics**: `http://localhost:8000/metrics`

---

**🎉 Auto Follow-Up Engine Deployment Checklist Complete!**
