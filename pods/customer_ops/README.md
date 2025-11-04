# Customer Ops — Local development

![CI](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/YOUR_ORG/YOUR_REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_ORG/YOUR_REPO)
[![Security](https://img.shields.io/badge/security-trivy%20%2B%20bandit-blue)](https://github.com/YOUR_ORG/YOUR_REPO/security)

Run the API and its dependencies locally. Two common options are supported: (A) Docker Compose for a reproducible stack, and (B) a local Python environment.

## Quick Start with Just

If you have [just](https://github.com/casey/just) installed:

```bash
# Setup everything
just setup

# Run tests
just test

# Start stack
just up

# Run smoke tests
just smoke
```

See `just --list` for all available commands.

Prereqs
- Docker (for Option A)
- Python 3.11+ and pip (for Option B)

Option A — Docker (recommended for parity)

From `pods/customer_ops`:

```powershell
# Build and start the API + Redis
docker compose up --build
```

The API will be available on http://localhost:8000. Metrics: http://localhost:8000/metrics

Option B — Local (fast iteration)

Install dependencies and run the app directly. On Windows PowerShell set env vars with `$env:...`.

PowerShell (Windows):

```powershell
pip install -r pods/customer_ops/requirements.txt
$env:ENV = 'dev'
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:REQUIRE_API_KEY = 'false'
uvicorn pods.customer_ops.api.main:app --reload
```

POSIX (macOS/Linux):

```bash
pip install -r pods/customer_ops/requirements.txt
export ENV=dev REDIS_URL=redis://localhost:6379/0 REQUIRE_API_KEY=false
uvicorn pods.customer_ops.api.main:app --reload
```

Notes
- If you change environment variables while the app is running, hit the reload endpoint to pick up new settings:

```powershell
curl http://localhost:8000/ops/reload
```

- The compose file mounts the repository for live code edits. For production builds we recommend creating a smaller build context and using a multi-stage Dockerfile.

## Development

### Error Handling & Observability

**Unified JSON Errors**: All errors return structured JSON:
```json
{"error": {"type": "...", "message": "...", "trace_id": "..."}}
```

**SSE Error Events**: Streaming endpoints emit `event: error` with the same structure for graceful client handling.

**PII Redaction**: Emails, phone numbers, and SSNs are automatically redacted from prompts and logs. Monitor redactions via the `pii_redactions_total` Prometheus metric.

**Metrics**: Error counters available at `/metrics`:
- `errors_total{type,endpoint}` - API error counts by type and endpoint
- `pii_redactions_total` - PII redaction events

### Quick Start Script

Use the `dev.ps1` helper for one-touch stack management:

```powershell
# Start stack and verify
.\scripts\dev.ps1 -Up -Verify

# Stop stack
.\scripts\dev.ps1 -Down

# Verify existing stack
.\scripts\dev.ps1 -Verify
```

### Running Tests

```powershell
# Hermetic unit tests (no external services)
$env:PYTHONPATH='../..'; $env:DATABASE_URL='sqlite:///:memory:'; $env:REQUIRE_API_KEY='false'; $env:REDIS_URL=''; pytest -q -m "not integration"

# With coverage
$env:PYTHONPATH='../..'; $env:DATABASE_URL='sqlite:///:memory:'; $env:REQUIRE_API_KEY='false'; $env:REDIS_URL=''; pytest -q -m "not integration" --cov=api --cov-report=term

# All tests (including integration)
$env:PYTHONPATH='../..'; $env:DATABASE_URL='sqlite:///:memory:'; $env:REQUIRE_API_KEY='false'; $env:REDIS_URL=''; pytest -q
```

### Pre-commit Hooks

We use pre-commit for code quality checks:

```powershell
# Install (one-time)
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks include:
- `ruff` - Fast Python linter with auto-fix
- `ruff-format` - Code formatter
- `pyright` - Static type checking
- Standard checks (trailing whitespace, YAML validation, etc.)

## CI/CD Pipeline

The repository includes a comprehensive CI pipeline with:

### Jobs
- **Lint**: Ruff, Pyright, and Hadolint (Dockerfile linting)
- **Unit Tests**: Fast hermetic tests with 70% code coverage
- **Security Scans**: Trivy (filesystem) and Bandit (Python SAST)
- **Smoke Tests**: Full Docker Compose stack integration testing

### Dependency Management
- **Dependabot**: Automated weekly dependency updates for Python packages and GitHub Actions
- **Requirements Lock**: `requirements.lock.txt` for reproducible builds
- **Generate lock file**: `just lock` or `pip-compile -o requirements.lock.txt requirements.txt`

### Security Features
- Trivy scans for critical/high vulnerabilities
- Bandit static analysis for Python security issues
- Results uploaded to GitHub Security tab (SARIF format)
- Configurable via `.bandit` file

### Artifacts
On CI failure, diagnostic artifacts are uploaded:
- Lint: Ruff/Mypy caches
- Unit: Pytest cache, coverage reports
- Security: Trivy/Bandit scan results
- Smoke: Docker Compose logs and configuration
