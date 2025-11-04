# AetherLink — Local Dev

[![Monitoring Smoke Test](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/monitoring-smoke.yml/badge.svg)](https://github.com/YOUR_ORG_OR_USER/AetherLink/actions/workflows/monitoring-smoke.yml)

This repo contains the AetherLink prototype. The `pods/customer-ops` directory is a FastAPI-based microservice.

Quick start (recommended)

1. Create and activate the virtualenv (if you don't have `.venv`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dev dependencies (we exclude `psycopg2-binary` locally on Windows; use Docker for full stack):

```powershell
pip install -r tools/requirements_no_psycopg2.txt
pip install pytest
```

3. Start services with Docker Compose (Postgres, Redis, Minio):

```powershell
docker compose -f deploy/docker-compose.dev.yml up -d
```

4. Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Quickstart (Windows, PowerShell)

```powershell
# from repo root
.\dev_setup.ps1 -Watch
# quick health check
.\makefile.ps1 health
# stop everything
.\dev_stop.ps1
# reset DB
.\dev_reset_db.ps1
# live logs
.\dev_logs.ps1
```

Notes
- For DB integration tests or running the API that connects to Postgres, run the Docker Compose file above. The Postgres service credentials are configured in `deploy/docker-compose.dev.yml`.
- To install `psycopg2-binary` locally on Windows you will need PostgreSQL dev tools (pg_config) available; using Docker avoids that requirement.

Getting started (developer)

Prerequisites
- Docker / Docker Compose
- Python 3.11
- (optional) Node.js / npm if you want to enable pyright pre-commit hooks

Start the full dev stack

```powershell
docker compose -f deploy/docker-compose.dev.yml up -d --build
```

Stop and remove the dev stack

```powershell
docker compose -f deploy/docker-compose.dev.yml down -v
```

Health check

After the `api` service starts the health endpoint will be available on http://localhost:8000/health and should return JSON:

```json
{"ok": true}
```

Prometheus & Grafana

- Prometheus UI: http://localhost:9090
- Grafana UI: http://localhost:3000

Prometheus is configured to scrape the API's `/metrics` endpoint. The API exposes `/metrics` via an observability helper (see `pods/customer-ops/api/observability.py`).

Running tests locally

1. Create and activate virtualenv and install dev deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tools/requirements_no_psycopg2.txt
pip install pytest
```

2. Start the dev stack (see above).

3. Run pytest (integration tests expect the dev stack to be running):

```powershell
pytest -q
```

### Migrations & Seed
```powershell
# create a new revision
.\dev_migrate.ps1 -RevMsg "add initial tables"

# apply latest migrations
.\dev_migrate.ps1

# apply migrations + run idempotent seeds
.\dev_migrate.ps1 -Seed
```

### Verify models vs DB
```powershell
# fails if Alembic would autogenerate a migration
.\dev_check_schema.ps1
```

### Dev Quality (pre-commit)

```powershell
# one-time setup
python -m pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files   # verify everything passes

# CI-style local check
pre-commit run --all-files

# Typecheck only
mypy .

# Ruff (lint+format) only
ruff check .
ruff format .
```

---

## 6) (Optional) GitHub Actions step

If you want the same checks in CI, add a job step after Python setup (and after starting Docker services for Alembic drift):

```yaml
- name: Install dev deps
  run: python -m pip install -r requirements-dev.txt

- name: Pre-commit (repo-wide)
  run: pre-commit run --all-files
```

---

## Notes / gotchas

- **Alembic config**: Make sure `alembic.ini` points `script_location` correctly (e.g. `alembic`) and your `alembic/env.py` reads `DATABASE_URL = os.environ["DATABASE_URL"]`.
- **Imports** in `scripts/seed.py` should match your real modules. Use lazy imports (inside functions) if you’ve got import cycles.
- **Idempotency**: Always *upsert* in seeds. No blind inserts.

### Tests
```powershell
.\test.ps1               # pytest + coverage (HTML in htmlcov/)
.\test.ps1 -k "customer" # subset

Database snapshots
.\pg_backup.ps1                  # writes ./backups/aetherlink_YYYYmmdd_HHMMSS.dump (keeps last 10)
.\pg_restore.ps1 -File .\backups\aetherlink_YYYYmmdd_HHMMSS.dump

(You can also run these from VS Code tasks or via the PowerShell Makefile: .\makefile.ps1 backup, .\makefile.ps1 restore -Msg .\backups\file.dump.)
```

### One-shot E2E verify
```powershell
# backup → restore-latest → health check
.\verify_e2e.ps1

# via Makefile
.\makefile.ps1 verify

# via VS Code
# Tasks: Run Task → "AetherLink: Verify E2E (backup→restore→health)"
```

### Stop / Restart
```powershell
# stop API/Worker + stop containers
.\dev_stop.ps1

# also remove containers (non-destructive to volumes)
.\dev_stop.ps1 -Prune

# stop then start
.\dev_restart.ps1
```

### Hot-reload API keys
```powershell
# Add or change API keys in environment, then reload without restarting
$env:API_KEY_NEWCLIENT = "SECRET456"
$headers = @{ "x-api-key" = $env:API_KEY_EXPERTCO }
Invoke-RestMethod -Method Post http://localhost:8000/ops/reload-auth -Headers $headers

# Test the new key
.\test_hot_reload_auth.ps1
```

### Observability
Every response includes an `x-request-id` header for correlation. You can supply your own or let the API generate one:
```powershell
# Auto-generated request ID
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing | Select-Object -ExpandProperty Headers

# Supply your own for end-to-end tracing
Invoke-RestMethod http://localhost:8000/health -Headers @{ "x-request-id" = "my-trace-123" }
```

Rate-limited endpoints (`/ops/*`) return JSON 429 responses with the request ID. Tune limits via environment (e.g., `RATE_LIMIT_FAQ=10/minute`).

For Prometheus metrics, Grafana panels, and alert examples, see [METRICS_GUIDE.md](METRICS_GUIDE.md).

### Nightly DB Backups (Windows Scheduled Task)
```powershell
# install or update nightly backup (2:30 AM, keep last 10)
.\schedule_nightly_backup.ps1

# customize time and retention
.\schedule_nightly_backup.ps1 -Time "01:15" -Keep 20

# remove the scheduled task
.\unschedule_nightly_backup.ps1

# run a backup immediately
.\pg_backup.ps1
```

Notes
- The task runs under your current user with elevated privileges and sets the working directory to your repo before invoking `pg_backup.ps1`.
- Backup logs land in `backups\\scheduled_*.log`; dumps are timestamped by `pg_backup.ps1`.
- If your machine is asleep at the scheduled time, StartWhenAvailable will run the task shortly after wake.
### Coverage
```powershell
.\coverage.ps1              # opens htmlcov\index.html (runs tests first if needed)
```

### Nightly backup + sync
```powershell
# backup task @ 02:30 (already set up)
.\schedule_nightly_backup.ps1

# sync task @ 02:45 → OneDrive (or any folder)
.\schedule_post_backup_sync.ps1 -Dest "C:\\Users\\You\\OneDrive\\AetherLink\\backups"

# remove sync task
.\unschedule_post_backup_sync.ps1
```

### Restore latest backup
```powershell
.\pg_restore_latest.ps1

# Sync latest backup to OneDrive (or any folder)
.\post_backup_sync.ps1 -Dest "C:\\Users\\You\\OneDrive\\AetherLink\\backups" -Keep 20
```

---

## 📊 Monitoring & Observability

### Quick Start
```powershell
# Navigate to monitoring directory
cd monitoring

# Start monitoring stack (Prometheus, Grafana, Alertmanager)
docker compose up -d

# Open Grafana dashboard
make open-crm-kpis

# Check system health
make health

# Run comprehensive validation
make smoke-test
```

### Monitoring Stack Components

- **Prometheus** (http://localhost:9090): Metrics collection & alerting
- **Grafana** (http://localhost:3000): Dashboards & visualization
  - Default login: admin/admin
  - Dashboard: PeakPro CRM - KPIs
- **Alertmanager** (http://localhost:9093): Alert routing & Slack notifications

### Sprint 5 Finance Monitoring

**4 Production-Ready Dashboards:**
- 📊 Invoices Created (24h)
- 💰 Invoices Paid (24h)
- 💵 Revenue (7 days)
- 📈 Payment Rate (30d)

**Performance:** Sub-second load times via 8 recording rules (10-100x faster than raw queries)

**Proactive Alerts:**
- `LowInvoicePaymentRate`: < 50% payment rate for 24h
- `RevenueZeroStreak`: Zero revenue for 48h (critical)
- `InvoiceGenerationStalled`: Zero invoices for 24h
- `CrmApiDown`: Scrape target down for 5m

### Common Commands

```powershell
# From monitoring/ directory
make open-crm-kpis      # Open Grafana CRM dashboard
make open-alerts        # Open Prometheus alerts page
make check-metrics      # Show current finance metrics
make smoke-test         # Full monitoring stack validation
make health             # Quick health check
make reload-prom        # Restart Prometheus & Alertmanager
make logs-crm           # View CRM API logs
make restart-all        # Restart all monitoring services
```

### Continuous Integration

The monitoring stack includes automated smoke tests that run on every push:

- ✅ Validates Prometheus rule groups & recording rules
- ✅ Checks Grafana datasource connectivity
- ✅ Verifies Alertmanager configuration
- ✅ Tests CRM API metrics exposure
- ✅ Optional: Sends synthetic Slack alert

**Manual smoke test:**
```powershell
.\scripts\test_monitoring_stack.ps1

# With Slack test alert
$env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
.\scripts\test_monitoring_stack.ps1 -FireSlack
```

### Documentation

- **Quick Reference**: [docs/QUICK_REFERENCE_FINANCE_MONITORING.md](docs/QUICK_REFERENCE_FINANCE_MONITORING.md)
- **Alert Runbook**: [docs/runbooks/ALERTS_CRM_FINANCE.md](docs/runbooks/ALERTS_CRM_FINANCE.md) (300+ lines)
- **Production Summary**: [docs/SPRINT5_PRODUCTION_HARDENING_SUMMARY.md](docs/SPRINT5_PRODUCTION_HARDENING_SUMMARY.md)

### Slack Integration

Configure Slack notifications:

```bash
# Set webhook URL
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Restart Alertmanager
cd monitoring
docker compose restart alertmanager

# Test with synthetic alert
.\scripts\test_monitoring_stack.ps1 -FireSlack
```

**Alert Channels:**
- `#crm-alerts`: CRM-specific alerts (2h repeat interval)
- `#ops-alerts`: General system alerts (4h repeat interval)

### Troubleshooting

**Dashboard panels empty?**
```powershell
make check-metrics      # Verify metrics are being collected
make logs-crm           # Check CRM API logs
make smoke-test         # Run full validation
```

**Alerts not firing?**
```powershell
make open-alerts        # Check alert status in Prometheus
make logs-alert         # Check Alertmanager logs
make reload-prom        # Reload Prometheus config
```

**Need help?**
- Review runbook: `docs/runbooks/ALERTS_CRM_FINANCE.md`
- Check logs: `make logs-prom`, `make logs-alert`, `make logs-crm`
- Restart services: `make restart-all`

---
