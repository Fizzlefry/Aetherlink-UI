# AetherLink — Local Dev

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
