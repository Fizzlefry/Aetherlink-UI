# AetherLink Deployment Guide

## Overview

AetherLink uses centralized environment configuration to run consistently across different environments (development, Docker, CI, production).

---

## Environment Files

All configuration is stored in the `config/` directory:

```
config/
  .env.dev     - Local development (Windows, VS Code, localhost)
  .env.docker  - Docker Compose (container-to-container networking)
  .env.ci      - GitHub Actions CI (localhost with exposed ports)
```

### Configuration Keys

All services read from these standardized environment variables:

#### Phase II Service URLs
- `COMMAND_CENTER_URL` - Command Center API base URL
- `AI_ORCHESTRATOR_URL` - AI Orchestrator API base URL
- `AUTO_HEAL_URL` - Auto-Heal service base URL
- `AI_SUMMARIZER_URL` - AI Summarizer service base URL
- `UI_URL` - React UI base URL

#### Health Endpoints (Command Center)
- `UI_HEALTH_URL` - UI health check endpoint
- `AI_SUMMARIZER_HEALTH_URL` - AI Summarizer health endpoint
- `NOTIFICATIONS_URL` - Notifications service health endpoint
- `APEXFLOW_URL` - ApexFlow service health endpoint
- `KAFKA_URL` - Kafka health endpoint

#### Auto-Heal Configuration
- `AUTOHEAL_SERVICES` - JSON array of container names to monitor
- `AUTOHEAL_HEALTH_ENDPOINTS` - JSON map of service → health URL
- `AUTOHEAL_INTERVAL_SECONDS` - Check interval (default: 30)

#### Optional
- `GRAFANA_ANNOTATIONS_URL` - Grafana API for annotations

---

## Environment-Specific Configuration

### Development (`.env.dev`)
**Use for:** Local development on Windows, VS Code debugging

**Characteristics:**
- Uses `localhost` URLs
- Exposed ports (8010, 8011, 8012, etc.)
- Direct access from host machine

**Example:**
```bash
COMMAND_CENTER_URL=http://localhost:8010
AI_ORCHESTRATOR_URL=http://localhost:8011
AUTO_HEAL_URL=http://localhost:8012
```

**Usage:**
```bash
# Services read from their own .env files or environment
export $(cat config/.env.dev | xargs)
cd services/command-center
python main.py
```

### Docker (`.env.docker`)
**Use for:** Docker Compose deployments

**Characteristics:**
- Uses container names as hostnames
- Internal container ports (8000, 8001, 8002)
- Container-to-container networking

**Example:**
```bash
COMMAND_CENTER_URL=http://aether-command-center:8000
AI_ORCHESTRATOR_URL=http://aether-ai-orchestrator:8001
AUTO_HEAL_URL=http://aether-auto-heal:8002
```

**Usage:**
```bash
cd deploy
docker-compose -f docker-compose.dev.yml up -d
# Services automatically load config/.env.docker via env_file
```

### CI (`.env.ci`)
**Use for:** GitHub Actions automated testing

**Characteristics:**
- Uses `127.0.0.1` instead of `localhost`
- Exposed ports (8010, 8011, 8012)
- Host networking for CI runners

**Example:**
```bash
COMMAND_CENTER_URL=http://127.0.0.1:8010
AI_ORCHESTRATOR_URL=http://127.0.0.1:8011
AUTO_HEAL_URL=http://127.0.0.1:8012
```

**Usage:**
```yaml
# In .github/workflows/ci.yml
- name: Copy CI environment config
  run: cp config/.env.ci config/.env.docker
```

---

## Deployment Scenarios

### Scenario 1: Local Development (Windows/Mac/Linux)

**Goal:** Run services natively on your machine

```bash
# 1. Export environment variables
export $(cat config/.env.dev | xargs)

# 2. Start dependencies (DB, Redis, etc.)
cd deploy
docker-compose up -d db redis minio

# 3. Start Phase II services
cd ../services/command-center
python main.py  # Port 8010

cd ../ai-orchestrator
python main.py  # Port 8011

cd ../auto-heal
python main.py  # Port 8012

# 4. Verify
curl http://localhost:8010/ops/ping
curl http://localhost:8011/ping
curl http://localhost:8012/ping
```

### Scenario 2: Docker Compose (Full Stack)

**Goal:** Run entire AetherLink platform in containers

```bash
# 1. Ensure config/.env.docker exists
ls config/.env.docker

# 2. Start all services
cd deploy
docker-compose -f docker-compose.dev.yml up -d

# 3. Verify services
docker ps | grep aether
curl http://localhost:8010/ops/health  # Requires operator role header
curl http://localhost:8011/ping
curl http://localhost:8012/ping

# 4. View logs
docker logs aether-command-center
docker logs aether-ai-orchestrator
docker logs aether-auto-heal

# 5. Stop services
docker-compose -f docker-compose.dev.yml down
```

### Scenario 3: CI/CD Pipeline

**Goal:** Automated testing in GitHub Actions

```yaml
# In .github/workflows/ci.yml
steps:
  - name: Copy CI environment config
    run: cp config/.env.ci config/.env.docker
  
  - name: Start services
    run: docker-compose -f deploy/docker-compose.dev.yml up -d
  
  - name: Run tests
    run: npx playwright test
```

**CI automatically:**
- Copies `.env.ci` to override `.env.docker`
- Starts services with CI-specific URLs
- Runs Playwright tests
- Cleans up containers

---

## Adding New Services

When adding a new Phase II service:

### 1. Add URL to all env files

**config/.env.dev:**
```bash
NEW_SERVICE_URL=http://localhost:8013
```

**config/.env.docker:**
```bash
NEW_SERVICE_URL=http://new-service:8003
```

**config/.env.ci:**
```bash
NEW_SERVICE_URL=http://127.0.0.1:8013
```

### 2. Update docker-compose.dev.yml

```yaml
  new-service:
    build:
      context: ../services/new-service
    container_name: aether-new-service
    env_file:
      - ../config/.env.docker
    ports:
      - "8013:8003"
    restart: unless-stopped
```

### 3. Update service code to read env

```python
import os

NEW_SERVICE_URL = os.getenv("NEW_SERVICE_URL")
```

### 4. Add to CI tests

```yaml
- name: Run New Service tests
  run: npx playwright test tests/new-service.spec.ts
```

---

## Troubleshooting

### Service can't connect to another service

**Symptom:** Connection refused, timeout, or DNS resolution failure

**Check:**
1. Verify you're using the correct env file
   ```bash
   # In container
   env | grep URL
   ```

2. Check container networking
   ```bash
   docker network ls
   docker network inspect deploy_default
   ```

3. Verify ports are exposed
   ```bash
   docker ps
   # Should see: 0.0.0.0:8010->8000/tcp
   ```

**Fix:**
- Local dev: Use `localhost` URLs
- Docker: Use container names
- CI: Use `127.0.0.1` URLs

### Environment variables not loading

**Symptom:** Service using default/hardcoded values

**Check:**
1. Verify env_file path in docker-compose
   ```yaml
   env_file:
     - ../config/.env.docker  # Relative to docker-compose.dev.yml
   ```

2. Check file exists
   ```bash
   ls -la config/.env.docker
   ```

3. Check file format (no spaces around `=`)
   ```bash
   # Good
   COMMAND_CENTER_URL=http://localhost:8010
   
   # Bad
   COMMAND_CENTER_URL = http://localhost:8010
   ```

**Fix:**
```bash
# Recreate containers to reload env
cd deploy
docker-compose down
docker-compose up -d
```

### CI tests failing with connection errors

**Symptom:** Tests pass locally but fail in CI

**Check:**
1. Verify CI uses correct env file
   ```yaml
   - name: Copy CI environment config
     run: cp config/.env.ci config/.env.docker
   ```

2. Check service readiness wait loops
   ```bash
   for i in {1..30}; do
     if curl -f http://127.0.0.1:8010/ops/ping; then
       break
     fi
     sleep 2
   done
   ```

**Fix:**
- Ensure `.env.ci` uses `127.0.0.1` not `localhost`
- Increase wait time for service startup
- Check GitHub Actions logs for actual error

### Auto-Heal not restarting services

**Symptom:** Service down but not restarted

**Check:**
1. Verify Docker socket mounted
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
   ```

2. Check health endpoints configured
   ```bash
   curl http://localhost:8012/autoheal/status
   # Should show: watching: [...], last_report: {...}
   ```

3. View auto-heal logs
   ```bash
   docker logs aether-auto-heal
   ```

**Fix:**
- Add missing health endpoints to `AUTOHEAL_HEALTH_ENDPOINTS`
- Verify container names match `AUTOHEAL_SERVICES`
- Ensure health endpoints return 200 OK

---

## Production Deployment

### Create `.env.prod` (not in repo)

```bash
# Production environment (example)
COMMAND_CENTER_URL=https://ops.aetherlink.io
AI_ORCHESTRATOR_URL=https://ai.aetherlink.io
AUTO_HEAL_URL=https://heal.aetherlink.io

# Add production secrets
GRAFANA_API_KEY=your-api-key
DATABASE_URL=postgres://prod-db:5432/aetherlink
```

### Use secrets management

```bash
# Don't commit .env.prod to git!
echo "config/.env.prod" >> .gitignore

# Use GitHub Secrets or Azure Key Vault
# Inject at deployment time
```

### Update docker-compose for production

```yaml
services:
  command-center:
    env_file:
      - ../config/.env.prod  # Production config
    restart: always  # Auto-restart on failure
```

---

## Configuration Management Best Practices

### 1. Never hardcode URLs
❌ **Bad:**
```python
url = "http://aether-command-center:8000"
```

✅ **Good:**
```python
url = os.getenv("COMMAND_CENTER_URL")
```

### 2. Provide sensible defaults
```python
url = os.getenv("COMMAND_CENTER_URL", "http://localhost:8010")
```

### 3. Document all env vars
Add to this guide when adding new variables.

### 4. Keep env files in sync
When adding a new variable, add to all three:
- `.env.dev`
- `.env.docker`
- `.env.ci`

### 5. Use .env.example for templates
```bash
# config/.env.example
COMMAND_CENTER_URL=http://localhost:8010
AI_ORCHESTRATOR_URL=http://localhost:8011
# ... etc
```

### 6. Validate required vars on startup
```python
def validate_config():
    required = ["COMMAND_CENTER_URL", "AI_ORCHESTRATOR_URL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise ValueError(f"Missing required env vars: {missing}")
```

---

## Testing Configuration

### Verify local dev config
```bash
export $(cat config/.env.dev | xargs)
echo $COMMAND_CENTER_URL  # Should be http://localhost:8010
```

### Verify Docker config
```bash
docker-compose -f deploy/docker-compose.dev.yml config
# Shows resolved configuration with env vars
```

### Verify CI config
```bash
# Simulate CI environment
cp config/.env.ci .env
cat .env | grep COMMAND_CENTER_URL
```

---

## Migration from Hardcoded Values

If upgrading from hardcoded configuration:

### 1. Find hardcoded URLs
```bash
# Search for hardcoded localhost URLs
grep -r "localhost:80" services/
grep -r "aether-" services/
```

### 2. Replace with env vars
```python
# Before
url = "http://aether-command-center:8000"

# After
url = os.getenv("COMMAND_CENTER_URL", "http://aether-command-center:8000")
```

### 3. Update docker-compose
```yaml
# Before
environment:
  AI_SUMMARIZER_URL: "http://aether-ai-summarizer:9108"

# After
env_file:
  - ../config/.env.docker
```

### 4. Test each environment
```bash
# Test local
export $(cat config/.env.dev | xargs)
python services/command-center/main.py

# Test Docker
docker-compose up -d command-center
curl http://localhost:8010/ops/ping

# Test CI (manual)
cp config/.env.ci config/.env.docker
docker-compose up -d
npx playwright test
```

---

## Summary

✅ **Single source of truth** - All URLs in `config/` folder  
✅ **Environment-specific** - Different configs for dev/docker/ci  
✅ **Portable** - Works on any machine, any OS  
✅ **CI-friendly** - Automated testing uses correct URLs  
✅ **Production-ready** - Template for prod deployment  

**Next Steps:**
- Phase III M3: Add UI health endpoint
- Phase III M4: Enrich Command Center observability
- Phase III M5: AI Orchestrator v2 with provider fallback
