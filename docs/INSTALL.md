# AetherLink – Production-style Install Guide

This document explains how to run the AetherLink stack using the production-ish
Compose file you added in Phase IV.

It assumes you have already built/pushed the Docker images that correspond to:
- services/command-center
- services/ai-orchestrator
- services/auto-heal
- services/ui

## 1. Prerequisites

- Docker 25+ and Docker Compose v2+
- Git repo with the AetherLink sources
- A shell with permission to access `/var/run/docker.sock` (for auto-heal)
- (Optional) Access to your AI model backends (Claude, Ollama, OpenAI)

## 2. Prepare Environment

1. Copy the template:

   ```bash
   cp config/.env.prod.template config/.env.prod
   ```

2. Edit `config/.env.prod` and set:
   - AI provider URLs (if you have them)
   - Any external dashboards (Grafana, Prometheus)
   - Any API keys (OpenAI, etc.)

## 3. Build Images (local option)

If you don't push to a registry yet:

```bash
docker build -t aetherlink/command-center:latest services/command-center
docker build -t aetherlink/ai-orchestrator:latest services/ai-orchestrator
docker build -t aetherlink/auto-heal:latest services/auto-heal
docker build -t aetherlink/ui:latest services/ui
```

If you do push to a registry, just change the image names in
`deploy/docker-compose.prod.yml` to match your registry:

```yaml
ghcr.io/your-org/aetherlink/command-center:1.11.0
```

## 4. Start the Stack

From the `deploy/` folder:

```bash
docker compose -f docker-compose.prod.yml up -d
```

This will start:
- Command Center on http://localhost:8010
- AI Orchestrator on http://localhost:8011
- Auto-Heal on http://localhost:8012
- UI on http://localhost:5173

## 5. Verify Services

### 5.1 Command Center

```bash
curl http://localhost:8010/ops/ping
curl http://localhost:8010/ops/health -H "X-User-Roles: operator"
```

### 5.2 AI Orchestrator

```bash
curl http://localhost:8011/ping
curl http://localhost:8011/providers/health -H "X-User-Roles: operator"
```

### 5.3 Auto-Heal

```bash
curl http://localhost:8012/ping
curl http://localhost:8012/autoheal/status
```

### 5.4 UI

```bash
curl http://localhost:5173/health.json
```

If all four respond, your Phase II + Phase III services are up.

## 6. Auto-Heal Behavior

- Auto-Heal polls every `AUTOHEAL_INTERVAL_SECONDS` (30s default)
- If `aether-crm-ui` or `aether-command-center` or `aether-ai-orchestrator`
  fails health, it will attempt a Docker restart
- You can view the recent actions in:

```bash
curl http://localhost:8012/autoheal/history
curl http://localhost:8012/autoheal/stats
```

## 7. Security / Audit (v1.11.0)

Because we added audit logging to the ops services, you can also check:

```bash
curl http://localhost:8010/audit/stats -H "X-User-Roles: operator"
```

This shows:
- total requests
- 401 / 403 attempts
- per-path usage

This is useful to spot people hitting `/ops/health` without permissions.

## 8. Stopping / Updating

To stop:

```bash
docker compose -f docker-compose.prod.yml down
```

To update a single service (e.g. AI Orchestrator):

```bash
docker build -t aetherlink/ai-orchestrator:latest services/ai-orchestrator
docker compose -f deploy/docker-compose.prod.yml up -d ai-orchestrator
```

## 9. Notes for Real Prod

- Put this behind Nginx / Traefik with TLS
- Store secrets outside of `.env.prod` (Vault / AWS Secrets Manager)
- Push images to a registry instead of building on the prod host
- Hook Docker logs into your ELK/Splunk stack (we already log audit there)
