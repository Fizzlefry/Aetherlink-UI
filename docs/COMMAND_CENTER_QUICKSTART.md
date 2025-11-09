# Command Center Quick Start Guide ⚡

**Spin up the AetherLink Command Center in under 5 minutes for local or production use.**

This guide provides copy-paste commands to get Command Center running immediately. Choose your preferred launch method below.

## ⚙️ Prerequisites

### Required
- **Docker & Docker Compose v2** (for containerized deployment)
- **Git** (to clone the repository)

### Optional
- **Node.js 18 + npm** (for local UI development)
- **kubectl + Helm 3** (for Kubernetes production deployment)

---

## 🚀 Quick Launch Options

### A. Docker Compose (Development)

**Perfect for evaluation, testing, and development work.**

```bash
# Clone and navigate to deploy directory
git clone https://github.com/AetherLink/Command-Center.git
cd Command-Center/deploy

# Launch all services
docker-compose -f docker-compose.dev.yml up -d

# Verify health
curl http://localhost:8010/healthz -H "X-User-Roles: admin"
```

**Access Points:**
- **Dashboard**: http://localhost:5173
- **API**: http://localhost:8010
- **API Docs**: http://localhost:8010/docs

### B. Kubernetes (Helm Chart Production)

**Production-ready deployment with auto-scaling and high availability.**

```bash
# Install with ingress
helm install command-center ./helm/command-center \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=command-center.local \
  --create-namespace \
  --namespace command-center

# Check deployment status
kubectl get pods -n command-center
kubectl get svc -n command-center
```

### C. Local Dev UI Startup

**Run just the frontend for UI development and testing.**

```bash
# Navigate to UI service
cd services/ui

# Install dependencies and start dev server
npm install
npm run dev
```

**Access:** http://localhost:5173

---

## 🔍 Health and Verification

### Container Status
```bash
# Check all containers are running
docker-compose -f deploy/docker-compose.dev.yml ps

# View container logs
docker-compose -f deploy/docker-compose.dev.yml logs -f
```

### API Health Check
```bash
# Basic health endpoint
curl http://localhost:8010/healthz -H "X-User-Roles: admin"

# Should return: {"status": "healthy", "timestamp": "...", "service": "command-center"}
```

### Prometheus Metrics
```bash
# View metrics endpoint
curl http://localhost:8010/metrics

# Key metrics to verify:
# - command_center_uptime_seconds
# - command_center_api_requests_total
# - command_center_events_total
```

### Grafana Dashboard
```bash
# Dashboard JSON location:
# observability/grafana/command-center-dashboard.json

# Import into your Grafana instance for visualizations
```

---

## 🔧 Troubleshooting Tips

### "Port 8010 already in use"
```bash
# Find what's using the port
netstat -tulpn | grep :8010

# Stop conflicting containers
docker-compose -f deploy/docker-compose.dev.yml down

# Or change ports in docker-compose.dev.yml
```

### "403 Forbidden" errors
```bash
# Ensure RBAC header is set
curl http://localhost:8010/healthz -H "X-User-Roles: admin"

# Valid roles: admin, operator, manager
# Case sensitive, comma-separated for multiple roles
```

### "Metrics missing" in Prometheus
```bash
# Check Prometheus scrape configuration
# Ensure metrics endpoint is accessible
curl http://localhost:8010/metrics

# Verify Prometheus can reach the service
```

### UI not loading
```bash
# Check if UI container is running
docker-compose -f deploy/docker-compose.dev.yml ps ui

# View UI logs
docker-compose -f deploy/docker-compose.dev.yml logs ui
```

### Database connection issues
```bash
# Check database container
docker-compose -f deploy/docker-compose.dev.yml ps db

# Reset database (development only)
docker-compose -f deploy/docker-compose.dev.yml down -v
docker-compose -f deploy/docker-compose.dev.yml up -d
```

---

## ⬆️ Upgrade & Redeploy

### Pull Latest Changes
```bash
# Update repository
git pull origin main

# Rebuild and restart containers
docker-compose -f deploy/docker-compose.dev.yml up -d --build
```

### Use CI/CD Images
```bash
# Pull specific tagged version
docker pull ghcr.io/aetherlink/command-center:main-<commit-sha>

# Or use latest main branch
docker pull ghcr.io/aetherlink/command-center:main
```

### Helm Chart Updates
```bash
# Upgrade existing release
helm upgrade command-center ./helm/command-center \
  --set image.tag=main-<commit-sha> \
  --namespace command-center

# Check rollout status
kubectl rollout status deployment/command-center -n command-center
```

---

## 📚 Related Documentation

### Core Documentation
- **[Command Center Ops Runbook](COMMAND_CENTER_OPS_RUNBOOK.md)** - Complete operations guide
- **[API Developer Guide](COMMAND_CENTER_API.md)** - Endpoint reference and examples
- **[Root README](../README.md)** - Executive overview and architecture

### Service Documentation
- **[Command Center API](../services/command-center/README.md)** - Backend service details
- **[Operator Dashboard](../services/ui/README.md)** - Frontend application guide
- **[Monitoring & Observability](../observability/README.md)** - Metrics and dashboards

### Deployment Guides
- **[Docker Deployment](../deploy/README.md)** - Container setup and configuration
- **[Kubernetes + Helm](../helm/command-center/README.md)** - Production deployment
- **[CI/CD Pipeline](../.github/workflows/command-center-ci.yml)** - Build and release automation

---

## 🎯 You're All Set!

**Next Steps:**
1. **Explore the dashboard** - Try different user roles and features
2. **Check API documentation** - Browse `/docs` for full endpoint reference
3. **Monitor metrics** - Set up Prometheus scraping and Grafana dashboards
4. **Customize deployment** - Adjust configurations for your environment

**Need Help?**
- **Issues**: [GitHub Issues](https://github.com/AetherLink/Command-Center/issues)
- **Discussions**: [GitHub Discussions](https://github.com/AetherLink/Command-Center/discussions)

---

**Built with ❤️ for reliable AI operations at scale.**