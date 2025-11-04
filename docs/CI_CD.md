# AetherLink CI/CD Pipeline

## Overview

AetherLink uses GitHub Actions for continuous integration and deployment. The pipeline ensures all Phase I and Phase II components remain functional with every commit.

## Pipeline Structure

### Phase I Jobs (Customer Ops Pod)

1. **Lint** - Code quality checks
   - Ruff (Python linter)
   - Pyright (type checking)
   - Hadolint (Dockerfile linting)

2. **Unit Tests** - Fast feedback with coverage
   - Pytest with coverage reporting
   - SQLite in-memory database
   - Codecov integration

3. **Security Scan** - Vulnerability detection
   - Trivy (filesystem scan)
   - Bandit (Python security)
   - SARIF upload to GitHub Security

4. **Smoke Tests** - Docker Compose validation
   - Full stack deployment
   - Health endpoint verification
   - API endpoint exercises
   - Auth flow validation

5. **Windows Validation** - Dev loop on Windows
   - Python environment setup
   - Docker Desktop compatibility
   - PowerShell makefile validation

### Phase II Jobs (Command Center + AI + RBAC + Auto-Heal)

6. **Phase II Services** - M1-M4 validation
   - Command Center tests (M1)
   - AI Orchestrator tests (M2)
   - RBAC tests (M3)
   - Auto-Heal tests (M4)
   - Service readiness checks
   - Playwright report artifacts

7. **Phase II Build Images** - Docker image validation
   - Command Center image
   - AI Orchestrator image
   - Auto-Heal image
   - Build caching with GitHub Actions cache

## Test Coverage

### Phase I Tests
- ✅ Unit tests with pytest
- ✅ API endpoint validation
- ✅ Health checks
- ✅ Metrics endpoints
- ✅ Auth flows

### Phase II Tests (Playwright)
- ✅ Command Center - 3 tests
  - Ping endpoint
  - Health aggregation
  - Service status validation

- ✅ AI Orchestrator - 4 tests
  - Ping endpoint
  - Health endpoint
  - Request validation
  - Response structure

- ✅ RBAC - 11 tests
  - Command Center: 6 role tests
  - AI Orchestrator: 5 role tests
  - Header validation
  - Permission enforcement

- ✅ Auto-Heal - 5 tests
  - Ping endpoint
  - Health status
  - Watch list validation
  - Service monitoring
  - Healing attempt structure

- ✅ Auto-Heal History (v1.9.0) - 13 tests
  - History endpoint structure (5 tests)
  - Statistics endpoint validation (5 tests)
  - Backward compatibility (1 test)
  - Data integrity checks (2 tests)

**Total: 36 Playwright tests + comprehensive pytest suite**

## Workflow Triggers

```yaml
on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]
```

### When CI Runs
- ✅ Every push to `main` or `master`
- ✅ Every pull request
- ✅ Manual workflow dispatch (optional)

### Concurrency Control
```yaml
concurrency:
  group: customer-ops-${{ github.ref }}
  cancel-in-progress: true
```
- Only one CI run per branch at a time
- Newer runs cancel older ones

## Service Readiness Checks

Phase II services use health endpoints with retry logic:

```bash
# Command Center - http://localhost:8010/ops/ping
# AI Orchestrator - http://localhost:8011/ping
# Auto-Heal - http://localhost:8012/ping

# Wait up to 60 seconds for each service
for i in {1..30}; do
  if curl -f http://localhost:8010/ops/ping > /dev/null 2>&1; then
    echo "✅ Service ready"
    break
  fi
  sleep 2
done
```

## Artifacts

### On Test Failure
- Service logs (Docker container logs)
- Playwright HTML reports
- Test-results directory
- Coverage reports

### Retention
- Playwright reports: 7 days
- Diagnostic artifacts: 7 days

## Local Testing

### Run Phase II tests locally:
```bash
# Start services
cd deploy
docker-compose -f docker-compose.dev.yml up -d command-center ai-orchestrator aether-auto-heal

# Wait for services
sleep 10

# Run tests
npx playwright test tests/command-center.spec.ts
npx playwright test tests/ai-orchestrator.spec.ts
npx playwright test tests/rbac.spec.ts
npx playwright test tests/auto-heal.spec.ts

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Run Phase I tests locally:
```bash
cd pods/customer_ops

# Unit tests
pytest -m "not integration" --cov=api

# Smoke tests
docker compose up -d
curl http://localhost:8000/healthz
docker compose down
```

## Docker Image Builds

Phase II images are built and tested but **not pushed** (yet):

```yaml
strategy:
  matrix:
    service:
      - name: command-center
        context: ./services/command-center
      - name: ai-orchestrator
        context: ./services/ai-orchestrator
      - name: auto-heal
        context: ./services/auto-heal
```

### Image Tags
- `aetherlink/<service>:${{ github.sha }}` - Commit-specific
- Cache: GitHub Actions cache (type=gha)

### Future: Push to Registry
To enable pushing to Docker Hub or GHCR:

```yaml
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKER_USERNAME }}
    password: ${{ secrets.DOCKER_PASSWORD }}

- name: Build and push
  uses: docker/build-push-action@v5
  with:
    push: true  # Enable pushing
    tags: aetherlink/${{ matrix.service.name }}:latest
```

## Debugging Failed Runs

### View Logs
1. Go to GitHub Actions tab
2. Click the failed run
3. Expand the failed job
4. Download artifacts (Playwright reports, logs)

### Common Issues

**Services not ready:**
```bash
# Check service logs in CI
docker logs aether-command-center
docker logs aether-ai-orchestrator
docker logs aether-auto-heal
```

**Port conflicts:**
```bash
# Ensure ports are free: 8010, 8011, 8012
docker ps
docker-compose down
```

**Module import errors:**
```bash
# Check Dockerfile COPY statements
# Ensure rbac.py is copied for RBAC-protected services
```

## GitHub Actions Caching

### npm dependencies
```yaml
cache: "npm"  # Automatically caches node_modules
```

### Docker layer caching
```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

### pip dependencies (Phase I)
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

## Success Criteria

### Phase I
✅ Lint passes (ruff, pyright, hadolint)
✅ Unit tests pass with >80% coverage
✅ Security scans pass (Trivy, Bandit)
✅ Smoke tests pass (Docker Compose)
✅ Windows validation passes

### Phase II
✅ All 3 Command Center tests pass
✅ All 4 AI Orchestrator tests pass
✅ All 11 RBAC tests pass
✅ All 5 Auto-Heal tests pass
✅ All 3 Docker images build successfully

## Status Badge

Add to README.md:
```markdown
[![CI](https://github.com/<your-org>/AetherLink/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-org>/AetherLink/actions/workflows/ci.yml)
```

## Future Enhancements

### Planned (Phase III)
- [ ] Deploy to staging environment on `main` push
- [ ] E2E tests with full UI (React app)
- [ ] Performance benchmarks
- [ ] Load testing with K6
- [ ] Database migration validation
- [ ] Multi-environment testing (dev, staging, prod)

### Nice to Have
- [ ] Slack/Discord notifications on failure
- [ ] PR comments with test results
- [ ] Deployment approval gates
- [ ] Rollback automation
- [ ] Canary deployments

## Maintenance

### Update dependencies
```bash
# Node (Playwright)
npm update

# Python (Phase I)
cd pods/customer_ops
pip install --upgrade -r requirements.txt
pip freeze > requirements.lock.txt
```

### Update browsers
```bash
npx playwright install --with-deps
```

### Update GitHub Actions
Dependabot will create PRs for:
- actions/checkout
- actions/setup-node
- actions/setup-python
- docker/build-push-action
- etc.

## Contact

For CI/CD issues, create an issue with:
- Failed workflow link
- Error logs
- Steps to reproduce locally
