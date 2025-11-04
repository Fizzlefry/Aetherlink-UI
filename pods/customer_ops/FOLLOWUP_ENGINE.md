# Auto Follow-Up Engine 🚀

**Status**: ✅ Shipped  
**Impact**: High-probability leads (pred_prob ≥ 0.70) receive automated follow-ups at configurable intervals  
**Architecture**: RQ-based background task system with fail-open resilience  

---

## Overview

The Auto Follow-Up Engine automatically schedules follow-up tasks for high-conversion-probability leads. When a lead is created with `pred_prob >= 0.70` (configurable), the system enqueues background tasks at specified delays (default: 30m, 2h).

**Key Benefits**:
- 📈 **Revenue Impact**: Automated nurturing of hot leads → higher conversion rates
- ⚡ **Low Risk**: Fail-open design (if Redis down, API continues, queue disabled)
- 🔧 **Extensible**: Hook-based architecture (easy swap to SMS/Email providers)
- 📊 **Observable**: Prometheus metrics + structured logs

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  POST /v1/lead                                          │
│  ├─ Enrichment (intent/sentiment/urgency)              │
│  ├─ Prediction (pred_prob via ML model)                │
│  ├─ Lead Storage (Redis)                               │
│  └─ IF pred_prob >= threshold:                         │
│      └─ Enqueue follow-up tasks (30m, 2h, ...)        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Redis Queue (RQ)     │
              │  - Scheduled tasks    │
              │  - Delay enforcement  │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Worker Process       │
              │  (worker.py)          │
              │  - Executes tasks     │
              │  - Calls HTTP hook    │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  POST /ops/followup-  │
              │  hook (callback)      │
              │  - Log timeline       │
              │  - Trigger webhook    │
              │  - Send SMS/Email     │
              └───────────────────────┘
```

---

## Configuration

All settings in `api/config.py`:

```python
FOLLOWUP_ENABLED: bool = True                  # Master switch
FOLLOWUP_QUEUE: str = "followups"              # RQ queue name
FOLLOWUP_RULE_TOP_P: float = 0.70              # Threshold (pred_prob >= 0.70)
FOLLOWUP_SCHEDULES: str = "30m,2h"             # Delays (CSV: m/h/d suffixes)
```

### Schedule Format

Supports flexible time units:
- `30m` → 30 minutes (1800 seconds)
- `2h` → 2 hours (7200 seconds)
- `1d` → 1 day (86400 seconds)
- `120` → raw seconds

Examples:
- `FOLLOWUP_SCHEDULES="30m,2h,1d"` → 3 follow-ups at 30min, 2hr, 1day
- `FOLLOWUP_SCHEDULES="15m,1h"` → 2 follow-ups at 15min, 1hr

---

## Components

### 1. Task Module (`api/tasks_followup.py`)

Background task executor:
```python
def run_followup(base_url, lead_id, strategy, message, api_key):
    """Execute follow-up task: POST to /ops/followup-hook."""
    # Posts to callback endpoint with lead context
    # Prometheus: FOLLOWUP_JOBS_TOTAL counter [strategy, result]
```

### 2. Worker Process (`worker.py`)

RQ worker entrypoint:
```python
def main():
    """Start RQ worker with scheduler support."""
    # Reads REDIS_URL, FOLLOWUP_QUEUE from env
    # Listens for scheduled tasks, executes run_followup()
```

Deployed as separate Docker container (`docker-compose.dev.yml`):
```yaml
worker:
  build:
    context: ../pods/customer-ops
    dockerfile: api/Dockerfile
  container_name: aetherlink-customerops-worker
  command: python worker.py
  env_file:
    - ../.env
  depends_on:
    - api
    - redis
  restart: unless-stopped
```

### 3. Main App Integration (`api/main.py`)

#### Queue Bootstrap (Fail-Open)
```python
# Runs at app startup (create_app)
q_followups = None
if s.FOLLOWUP_ENABLED and s.REDIS_URL:
    try:
        r_conn = redis.from_url(str(s.REDIS_URL), decode_responses=True, socket_connect_timeout=2)
        q_followups = Queue(s.FOLLOWUP_QUEUE, connection=r_conn)
        app.state.q_followups = q_followups
        logger.info("followup_queue_enabled")
    except Exception as e:
        logger.warning("followup_queue_disabled", extra={"error": str(e)})
        app.state.q_followups = None  # Graceful degradation
```

#### Enqueue Logic (Lead Creation)
```python
# In POST /v1/lead after lead storage
if app.state.q_followups and pred_prob >= s.FOLLOWUP_RULE_TOP_P:
    try:
        from datetime import timedelta
        from .tasks_followup import run_followup
        
        schedules = _parse_schedules(s.FOLLOWUP_SCHEDULES)
        for delay in schedules:
            app.state.q_followups.enqueue_in(
                timedelta(seconds=delay),
                run_followup,
                base_url=str(request.base_url).rstrip("/"),
                lead_id=lead_id,
                strategy=f"{delay}s",
                message=f"Auto follow-up at +{delay}s",
                api_key=request.headers.get("x-api-key", ""),
            )
        logger.info("followups_enqueued", extra={"lead_id": lead_id, "pred_prob": pred_prob, "count": len(schedules)})
    except Exception as e:
        logger.warning("followup_enqueue_error", extra={"error": str(e)})
```

### 4. Ops Endpoints

#### `POST /ops/followup-hook`
Receives follow-up task callbacks from worker:
```bash
curl -X POST http://localhost:8000/ops/followup-hook \
  -H "x-api-key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "lead_abc123",
    "strategy": "1800s",
    "message": "Auto follow-up at +1800s"
  }'
```

**Response**: `{"ok": true, "message": "Follow-up hook received"}`

**Use Cases**:
- Log to timeline (append_history)
- Trigger external webhook (Zapier/n8n)
- Send SMS (Twilio) or Email (SendGrid)
- Update CRM (Salesforce/HubSpot)

#### `GET /ops/followup/queue`
Query queue status (queued + scheduled tasks):
```bash
curl http://localhost:8000/ops/followup/queue \
  -H "x-api-key: dev-key-123"
```

**Response**:
```json
{
  "enabled": true,
  "queue": "followups",
  "jobs": {
    "queued": 0,
    "scheduled": 4
  }
}
```

---

## Deployment

### Prerequisites
- Redis (for queue persistence)
- RQ >= 1.16.2 (`requirements.txt` updated)

### Docker Compose
```bash
# Start all services (API + Worker)
cd deploy
docker-compose -f docker-compose.dev.yml up --build

# View worker logs
docker-compose logs -f worker

# Scale workers (optional)
docker-compose up --scale worker=3
```

### Environment Variables
```bash
# .env file
REDIS_URL=redis://localhost:6379/0
FOLLOWUP_ENABLED=true
FOLLOWUP_QUEUE=followups
FOLLOWUP_RULE_TOP_P=0.70
FOLLOWUP_SCHEDULES=30m,2h
```

---

## Testing

### Unit Tests
```bash
cd pods/customer_ops
python -m pytest tests/test_followup_rules.py -v
```

Tests cover:
- ✅ Schedule parsing (30m, 2h, 1d formats)
- ✅ Threshold triggering (pred_prob >= 0.70)
- ✅ Disabled flag handling
- ✅ Empty schedule handling

### Integration Test (PowerShell)
```powershell
.\scripts\test_followup.ps1
```

Validates:
1. Queue status endpoint accessibility
2. High-prob lead creation → follow-ups enqueued
3. Queue status shows scheduled tasks
4. Low-prob lead creation → follow-ups NOT enqueued

---

## Observability

### Prometheus Metrics

```prometheus
# Follow-up task completions
FOLLOWUP_JOBS_TOTAL{strategy="1800s", result="success"} 15
FOLLOWUP_JOBS_TOTAL{strategy="7200s", result="success"} 12
FOLLOWUP_JOBS_TOTAL{strategy="1800s", result="error"} 2

# Query examples
rate(FOLLOWUP_JOBS_TOTAL[5m])                  # Job execution rate
sum by (result) (FOLLOWUP_JOBS_TOTAL)          # Success vs error counts
```

Available at: `http://localhost:8000/metrics`

### Structured Logs

```json
// Queue enabled at startup
{"level": "info", "msg": "followup_queue_enabled", "queue": "followups"}

// Follow-ups enqueued after lead creation
{"level": "info", "msg": "followups_enqueued", "lead_id": "lead_xyz", "pred_prob": 0.85, "count": 2}

// Hook received by API
{"level": "info", "msg": "followup_hook_received", "lead_id": "lead_xyz", "strategy": "1800s"}

// Task execution in worker
{"level": "info", "msg": "followup_executed", "lead_id": "lead_xyz", "strategy": "1800s", "status_code": 200}
```

---

## Operations

### Monitoring

1. **Queue Health**:
   ```bash
   curl http://localhost:8000/ops/followup/queue -H "x-api-key: dev-key-123"
   ```

2. **Worker Logs**:
   ```bash
   docker-compose logs -f worker
   ```

3. **Metrics Dashboard**:
   - Grafana: `http://localhost:3000`
   - Prometheus: `http://localhost:9090`
   - Query: `FOLLOWUP_JOBS_TOTAL`

### Troubleshooting

#### No tasks being enqueued?
1. Check `FOLLOWUP_ENABLED=true` in `.env`
2. Verify Redis connection: `docker-compose logs redis`
3. Confirm pred_prob >= threshold: check API logs for `followups_enqueued`
4. Query `/ops/followup/queue` to see scheduled count

#### Worker not executing tasks?
1. Verify worker is running: `docker-compose ps worker`
2. Check worker logs: `docker-compose logs worker`
3. Ensure `REDIS_URL` matches API's Redis instance
4. Restart worker: `docker-compose restart worker`

#### Tasks executing but hook failing?
1. Check API logs for `followup_hook_received`
2. Verify network connectivity (worker → API)
3. Check API key is passed correctly
4. Monitor `FOLLOWUP_JOBS_TOTAL{result="error"}`

---

## Customization

### Swap HTTP Hook for SMS/Email

**Current** (HTTP hook):
```python
# In tasks_followup.py
resp = requests.post(f"{base_url}/ops/followup-hook", json=payload, headers=headers)
```

**Twilio SMS**:
```python
from twilio.rest import Client
client = Client(account_sid, auth_token)
message = client.messages.create(
    body=f"Hi {lead['name']}, still interested in booking?",
    from_='+1234567890',
    to=lead['phone']
)
```

**SendGrid Email**:
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
message = Mail(
    from_email='team@example.com',
    to_emails=lead['email'],
    subject='Your booking inquiry',
    html_content='<p>Hi, just following up...</p>'
)
sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
response = sg.send(message)
```

### Adjust Threshold

Lower threshold = more follow-ups (higher coverage, more noise):
```bash
FOLLOWUP_RULE_TOP_P=0.60  # Trigger at 60% prob (was 70%)
```

Raise threshold = fewer follow-ups (less noise, higher precision):
```bash
FOLLOWUP_RULE_TOP_P=0.85  # Trigger only at 85%+ prob
```

### Add More Delays

```bash
FOLLOWUP_SCHEDULES=15m,1h,6h,1d,3d  # 5 follow-ups over 3 days
```

---

## Future Enhancements

### Phase 2: Intelligence
- [ ] Dynamic scheduling (adjust delays based on engagement)
- [ ] A/B testing (test different message strategies)
- [ ] Outcome feedback loop (learn which follow-ups convert)

### Phase 3: Multi-Channel
- [ ] SMS via Twilio
- [ ] Email via SendGrid
- [ ] WhatsApp via Twilio API
- [ ] Slack/Discord webhooks

### Phase 4: Personalization
- [ ] Template engine (Jinja2) for message customization
- [ ] Lead segmentation (different strategies by intent/urgency)
- [ ] Time-zone awareness (send at optimal local time)

---

## Dependencies

Added to `requirements.txt`:
```
rq>=1.16.2  # Redis Queue for background tasks
```

Existing dependencies leveraged:
- `redis==5.0.8` (connection pooling)
- `fastapi-limiter` (rate limiting)
- `prometheus-client` (metrics)

---

## References

- **RQ Documentation**: https://python-rq.org/
- **Redis Queue Patterns**: https://redis.io/docs/manual/patterns/
- **FastAPI Background Tasks**: https://fastapi.tiangolo.com/tutorial/background-tasks/
- **Prometheus Best Practices**: https://prometheus.io/docs/practices/naming/

---

## Changelog

### v1.0.0 (Current)
- ✅ RQ-based task queue with scheduler support
- ✅ Configurable threshold (FOLLOWUP_RULE_TOP_P)
- ✅ Flexible schedule parsing (m/h/d suffixes)
- ✅ HTTP hook callback endpoint
- ✅ Queue status monitoring endpoint
- ✅ Prometheus metrics (FOLLOWUP_JOBS_TOTAL)
- ✅ Fail-open resilience (continues if Redis down)
- ✅ Docker Compose worker service
- ✅ Unit tests (10 tests, 100% pass)
- ✅ Integration verification script (PowerShell)

---

## License

Internal use only. Part of AetherLink CustomerOps AI Agent.
