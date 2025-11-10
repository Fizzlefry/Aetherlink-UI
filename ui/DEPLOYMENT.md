# AetherLink CRM UI Deployment

## Production Deployment

The CRM UI is containerized and production-ready. It serves the React SPA and proxies API calls to the Command Center backend.

### Quick Start

```bash
# Build and run the CRM UI + Command Center
docker-compose -f docker-compose.ui.yml up -d

# Access the CRM at http://localhost
# Command Center API at http://localhost:8010
```

### Architecture

- **Frontend**: React SPA served by Nginx (port 80)
- **Backend**: FastAPI Command Center (port 8010)
- **Proxy**: Nginx forwards `/api/*` and `/ui/bundle` to backend
- **CORS**: Configured for cross-origin requests

### Services

#### crm-ui
- **Image**: Multi-stage Node → Nginx
- **Port**: 80 (HTTP)
- **Health Check**: `/health` endpoint
- **Static Assets**: Gzipped and cached for 1 year
- **SPA Routing**: Handles React Router client-side routing

#### command-center
- **Port**: 8011
- **Health Check**: `/healthz` endpoint
- **Data**: Persistent volume for events/alerts DB
- **Environment**: `AETHERLINK_ENV=docker`

### API Proxy Configuration

Nginx automatically proxies:
- `/api/ui/bundle` → `http://command-center:8010/ui/bundle` (preferred)
- `/ui/bundle` → `http://command-center:8010/ui/bundle` (legacy)
- `/api/*` → `http://command-center:8010/`

### Environment Variables

#### UI Container
- `NODE_ENV=production`

#### Backend Container
- `EVENT_DB_PATH=./data/events.db`
- `ALERT_DB_PATH=./data/alerts.db`
- `AETHERLINK_ENV=docker`

### Health Checks

Both services include health checks:
- UI: `curl -f http://localhost/healthz` or `/health`
- Backend: `curl -f http://localhost:8010/healthz`

### Volumes

- `command-center-data`: Persistent storage for event/alert databases

### Security Headers

Nginx adds security headers:
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `X-Content-Type-Options: nosniff`
- `Content-Security-Policy: default-src 'self' http: https: data: blob: 'unsafe-inline'`

### Scaling

For production scaling:
1. Add load balancer in front of `crm-ui`
2. Scale `command-center` horizontally
3. Use external database for persistence
4. Enable SSL/TLS termination

### Development

For development with hot reload:
```bash
cd ui
npm run dev  # Runs on http://localhost:5173
```

Backend development:
```bash
cd services/command-center
python main.py  # Runs on http://localhost:8011
```
