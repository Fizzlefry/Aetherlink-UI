# AetherLink Hardening + Rollout Playbook

This guide focuses on making the existing AetherLink features (scheduler, audit, RBAC, persistence, SQLite adapter, replication, analytics) reliable for production use. No new features — just hardening what we have.

## 1. Lock the Runtime Shape

**Keep these endpoints exactly as-is:**

### Public Endpoints (no auth required):
* `GET /ops/ping`
* `GET /ops/health`
* `GET /api/crm/import/acculynx/schedule/status`

### RBAC-Protected Endpoints (require `x-ops: 1` or `x-role: ops|admin`):
* `POST /api/crm/import/acculynx/schedule`
* `POST /api/crm/import/acculynx/pause`
* `POST /api/crm/import/acculynx/resume`
* `POST /api/crm/import/acculynx/run-now`
* `DELETE /api/crm/import/acculynx/schedule`
* `GET /api/crm/import/acculynx/audit`
* `GET /ops/db`
* `GET /ops/replication`
* `POST /ops/restart`
* `GET /analytics/summary`
* `GET /analytics/tenants/{tenant}`
* `GET /analytics/audit`

**Note:** Tell anyone else "don't depend on anything else yet." This is the clean "outer API" for this version.

## 2. Standard Environment Variables for First Field Run

Use these safe defaults for initial deployment on Windows:

```text
# Storage
COMMAND_CENTER_STORE=sqlite
COMMAND_CENTER_DSN=./data/command_center.db
COMMAND_CENTER_DATA_DIR=./data
COMMAND_CENTER_MAX_SNAPSHOTS=5

# Scheduler + Health
COMMAND_CENTER_HEALTH_INTERVAL=30
COMMAND_CENTER_AUTO_RECOVER=true
COMMAND_CENTER_SCHEDULER_STALL_SEC=30

# Replication (OFF for first field run)
COMMAND_CENTER_REPLICATION=off

# Restart
COMMAND_CENTER_ALLOW_RESTART=true
COMMAND_CENTER_RESTART_DELAY_SEC=3
```

**Why:** SQLite + JSON backups + self-heal provides both human-readable files and real DB tables. Replication stays off until network/hosting is solid.

## 3. Minimal Test Matrix

Run these **in order** after starting `uvicorn ...:app`. All should pass before field use.

### 1. Health Checks
```sh
curl http://localhost:8000/ops/ping
curl http://localhost:8000/ops/health
```
Expect: `{"ok": true}` and health sections with status 1.

### 2. Create Schedule (with ops header)
```sh
curl -X POST http://localhost:8000/api/crm/import/acculynx/schedule \
  -H "x-tenant: field-tenant" \
  -H "x-ops: 1" \
  -H "Content-Type: application/json" \
  -d '{"interval_sec": 120}'
```

### 3. Check Status
```sh
curl http://localhost:8000/api/crm/import/acculynx/schedule/status
```
Expect: Your tenant with `interval_sec`, `last_run_iso`, maybe a "stub" message.

### 4. Pause → Run-now → Resume
```sh
curl -X POST http://localhost:8000/api/crm/import/acculynx/pause  -H "x-tenant: field-tenant" -H "x-ops: 1"
curl -X POST http://localhost:8000/api/crm/import/acculynx/run-now -H "x-tenant: field-tenant" -H "x-ops: 1"
curl -X POST http://localhost:8000/api/crm/import/acculynx/resume -H "x-tenant: field-tenant" -H "x-ops: 1"
```

### 5. Audit
```sh
curl http://localhost:8000/api/crm/import/acculynx/audit -H "x-ops: 1"
```

### 6. Persistence Check
* Stop server
* Start server again
* Hit `GET /api/crm/import/acculynx/schedule/status` — schedule should persist
* Hit `GET /api/crm/import/acculynx/audit` — audit entries should persist

If all pass, the system is field-ready.

## 4. What to Freeze (Protect Quality)

Until you've run on one real machine for a day:
* **Don't** turn on `COMMAND_CENTER_REPLICATION=on`
* **Don't** point `COMMAND_CENTER_DSN` to a shared network drive
* **Don't** add new background loops
* **Don't** relax RBAC — UI already sends `x-ops: 1`

This keeps the reliability envelope small and understandable.

## 5. Observability to Watch

You have Prometheus counters (persistence, scheduler, analytics) and Grafana dashboard. For first field test, monitor:

* `/metrics` → Confirm counters exist
* `/ops/health` → Confirm scheduler/db/replication are 1
* React panel → Confirm countdown and pause/resume buttons reflect server state

Three independent views of the same truth.

## 6. Known-Good Deployment Steps (Windows)

```powershell
cd "c:\Users\jonmi\OneDrive\Documents\AetherLink"
$env:PYTHONPATH = "."
$env:COMMAND_CENTER_STORE = "sqlite"
python -m uvicorn services.command-center.main:app --host 0.0.0.0 --port 8000 --log-level info
```

Then open your UI (with scheduler + audit panels) — it should "just work" with the built endpoints.

## 7. After First Field Run (Stabilization Only)

Once 1-2 real tenants are running and data flows:

1. **Real AccuLynx importer**: Replace stub in `acculynx_pull_for_tenant(...)` with actual fetch/import
2. **Turn on replication** (only if you know the destination)
3. **Lower interval** for health loop if tighter detection needed

Everything else can wait — the skeleton is strong.

## Summary

We're not adding surface area; we're ensuring the current system starts, persists, secures, and integrates with the UI. Field-test safely without compromising future-proofing.