# 🔄 Background Ingestion (Async Job Queue)

**Status**: ✅ Operational  
**Queue**: Redis-backed RQ (Redis Queue)  
**Worker**: Separate container processing jobs

---

## Overview

Large file uploads and URL fetches can block API requests for seconds or minutes. Background ingestion queues these operations to a Redis-backed worker, returning immediately with a `job_id` for status polling.

### Benefits

- **Snappy UX**: API returns instantly, no client timeouts
- **More reliable**: Long ingests won't fail under load
- **Scales out**: Run N workers without touching the API
- **Observable**: Poll job status for support/debugging

---

## Architecture

```
Client → API (enqueue) → Redis Queue → Worker (process) → Vector Store
         ↓ (instant)                    ↓ (async)
         job_id                          result
```

1. **API**: Receives request, enqueues job to Redis, returns `job_id`
2. **Worker**: Picks job from queue, processes (download/extract/embed), stores result
3. **Client**: Polls `/ops/jobs/{job_id}` to check status

---

## Usage

### 1. Enqueue Text Ingestion

```bash
curl -X POST http://localhost:8000/knowledge/ingest-text-async \
  -H "x-api-key: test-key" \
  -H "x-role: editor" \
  -H "Content-Type: application/json" \
  -d '{"text":"Large document content...","source":"docs"}'

# Response:
{
  "ok": true,
  "job_id": "abc-123-def",
  "queued": true,
  "type": "text",
  "tenant": "default",
  "source": "docs"
}
```

###2. Enqueue URL Ingestion

```bash
curl -X POST http://localhost:8000/knowledge/ingest-url-async \
  -H "x-api-key: test-key" \
  -H "x-role: editor" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/docs","source":"web"}'

# Response:
{
  "ok": true,
  "job_id": "xyz-456-ghi",
  "queued": true,
  "type": "url",
  "tenant": "default",
  "source": "web",
  "url": "https://example.com/docs"
}
```

### 3. Enqueue File Ingestion

```bash
curl -X POST http://localhost:8000/knowledge/ingest-file-async \
  -H "x-api-key: test-key" \
  -H "x-role: editor" \
  -F "file=@document.pdf" \
  -F "source=uploads"

# Response:
{
  "ok": true,
  "job_id": "file-789-jkl",
  "queued": true,
  "type": "file",
  "filename": "document.pdf",
  "tenant": "default",
  "source": "uploads"
}
```

### 4. Poll Job Status

```bash
curl http://localhost:8000/ops/jobs/abc-123-def \
  -H "x-admin-key: admin-secret-123"

# Response (queued):
{
  "id": "abc-123-def",
  "status": "queued",
  "enqueued_at": "2025-01-15 10:30:00",
  "started_at": null,
  "ended_at": null
}

# Response (finished):
{
  "id": "abc-123-def",
  "status": "finished",
  "enqueued_at": "2025-01-15 10:30:00",
  "started_at": "2025-01-15 10:30:02",
  "ended_at": "2025-01-15 10:30:15",
  "result": {
    "ok": true,
    "ingested_chunks": 42,
    "tenant": "default",
    "source": "docs",
    "latency_ms": 12500.5
  }
}

# Response (failed):
{
  "id": "xyz-456-ghi",
  "status": "failed",
  "enqueued_at": "2025-01-15 10:35:00",
  "started_at": "2025-01-15 10:35:01",
  "ended_at": "2025-01-15 10:35:10",
  "error": "HTTPError: 404 Not Found"
}
```

---

## PowerShell Examples

```powershell
# Enqueue URL ingest
$h = @{'x-api-key'='test-key'; 'x-role'='editor'; 'Content-Type'='application/json'}
$body = @{url='https://example.com'; source='web'} | ConvertTo-Json
$job = Invoke-RestMethod http://localhost:8000/knowledge/ingest-url-async -Method Post -Headers $h -Body $body

# Poll job status (admin)
$adm = @{'x-admin-key'='admin-secret-123'}
$job_id = $job.job_id
1..20 | % {
    $status = Invoke-RestMethod "http://localhost:8000/ops/jobs/$job_id" -Headers $adm
    if ($status.status -in @('finished','failed')) {
        $status | ConvertTo-Json -Depth 6
        break
    }
    Start-Sleep -Milliseconds 500
}
```

---

## RBAC Protection

| Endpoint | Required Role |
|----------|--------------|
| `POST /knowledge/ingest-text-async` | `editor` or `admin` |
| `POST /knowledge/ingest-url-async` | `editor` or `admin` |
| `POST /knowledge/ingest-file-async` | `editor` or `admin` |
| `GET /ops/jobs/{job_id}` | `admin` only |

Viewers cannot enqueue jobs (403 Forbidden).

---

## Job Lifecycle

1. **queued**: Job in Redis queue, waiting for worker
2. **started**: Worker picked up job and is processing
3. **finished**: Job completed successfully, `result` available
4. **failed**: Job failed with error, `error` message available

---

## Testing

Run the comprehensive async ingestion test suite:

```bash
python test_async_ingest.py
```

Expected output:
```
🔄 Background Ingestion Tests
✅ PASS  Async text ingest
✅ PASS  Async URL ingest
✅ PASS  Async file ingest
✅ PASS  Job not found
✅ PASS  Viewer blocked

Score: 5/5 tests passed
🎉 ALL BACKGROUND INGESTION TESTS PASSED!
```

---

## Worker Configuration

The worker is a separate Docker container sharing the same image and database:

```yaml
worker:
  image: aether/customer-ops:dev
  command: ["python", "-m", "pods.customer_ops.worker"]
  environment:
    - REDIS_URL=redis://redis:6379/0
    - DATABASE_URL=sqlite:////app/local.db
  depends_on:
    - redis
```

### Scaling Workers

Run multiple workers for higher throughput:

```bash
docker compose up --scale worker=3 -d
```

Each worker processes jobs independently from the same queue.

---

## Monitoring

### Check Queue Status

```bash
# Redis CLI
docker exec -it aether-redis redis-cli

# Check queue length
LLEN rq:queue:ingest

# View failed jobs
LRANGE rq:queue:failed 0 -1
```

### Worker Logs

```bash
docker logs aether-customer-ops-worker --tail 50 --follow
```

Look for:
- `Starting ingest_text_job: tenant=...` (job started)
- `ingest_text_job done: chunks=42 latency_ms=500` (success)
- `ingest_text_job failed: error=...` (failure)

---

## Troubleshooting

### "Job not found" (404)

- Job ID expired (Redis TTL, default 500s)
- Wrong job ID (typo)
- Redis restarted (jobs lost)

### Worker not processing jobs

```bash
# Check worker is running
docker ps | grep worker

# Check worker logs
docker logs aether-customer-ops-worker

# Ensure Redis is accessible
docker exec aether-customer-ops-worker redis-cli -h redis ping
```

### Jobs stuck in "queued"

- Worker container not running
- Worker crashed (check logs)
- Redis connection issue

### Jobs fail immediately

- Check worker logs for Python errors
- Verify DATABASE_URL is correct
- Ensure embedder is configured (EMBED_PROVIDER)

---

## Implementation Details

### Worker Jobs

Three job functions in `worker.py`:

1. **`ingest_text_job(text, source, tenant)`**: Chunk + embed + store text
2. **`ingest_url_job(url, source, tenant)`**: Fetch URL + extract + ingest
3. **`ingest_file_job(file_bytes, filename, source, tenant)`**: Parse file + ingest

### Queue Configuration

- **Queue name**: `ingest`
- **Default timeout**: 600 seconds (10 minutes)
- **Redis connection**: Shared with API via `REDIS_URL`

### Job Result Schema

```json
{
  "ok": true,
  "ingested_chunks": 42,
  "tenant": "default",
  "source": "docs",
  "latency_ms": 1234.5,
  "filename": "document.pdf",  // for file jobs
  "url": "https://example.com"  // for URL jobs
}
```

---

## Future Enhancements

- **Priority queues**: High/low priority ingestion
- **Batch processing**: Ingest multiple files in one job
- **Webhooks**: Notify client when job completes
- **Dashboard UI**: Live queue status + job history
- **Retry logic**: Auto-retry failed jobs with backoff

---

**Next Upgrade**: URL Readability (trafilatura) for cleaner webpage extraction
