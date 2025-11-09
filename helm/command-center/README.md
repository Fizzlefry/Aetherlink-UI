# Command Center Helm Chart

This Helm chart deploys the AetherLink Command Center to a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+

## Installing the Chart

To install the chart with the release name `command-center`:

```bash
helm install command-center ./helm/command-center
```

## Configuration

The following table lists the configurable parameters of the Command Center chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `ghcr.io/your-org/aetherlink/command-center` |
| `image.tag` | Image tag | `main` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `8010` |
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.hosts` | Ingress hosts | `[]` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |
| `persistence.enabled` | Enable persistence | `true` |
| `persistence.size` | PVC size | `1Gi` |
| `healthCheck.livenessProbe.initialDelaySeconds` | Liveness probe initial delay | `30` |
| `healthCheck.readinessProbe.initialDelaySeconds` | Readiness probe initial delay | `5` |

## Health Checks

The chart includes Kubernetes liveness and readiness probes that use the `/healthz` endpoint with proper RBAC headers:

- **Liveness Probe**: Checks every 30s, initial delay 30s
- **Readiness Probe**: Checks every 10s, initial delay 5s

Both probes send the required `X-User-Roles: admin` header.

## Persistence

By default, the chart creates a PersistentVolumeClaim for SQLite database storage. The data is mounted at `/app/data`.

## Ingress

To enable ingress, set `ingress.enabled=true` and configure the hosts:

```yaml
ingress:
  enabled: true
  hosts:
    - host: command-center.example.com
      paths:
        - path: /
          pathType: Prefix
```

## Security

The chart includes security best practices:

- Non-root user execution
- Read-only root filesystem
- Dropped capabilities
- Security contexts for pods and containers

## Upgrading

To upgrade the chart:

```bash
helm upgrade command-center ./helm/command-center
```

## Uninstalling

To uninstall the chart:

```bash
helm uninstall command-center
```

## CI/CD Integration

This chart works seamlessly with the GitHub Actions CI/CD pipeline. The pipeline automatically updates image tags, and you can deploy new versions with:

```bash
helm upgrade command-center ./helm/command-center --set image.tag=main-$(git rev-parse --short HEAD)
```

## Production Deployment

For production deployments, consider:

1. **External Secrets**: Configure `env` values to reference external secrets
2. **TLS**: Enable ingress with TLS certificates
3. **Resource Limits**: Adjust CPU/memory limits based on load
4. **Horizontal Scaling**: Enable HPA with `autoscaling.enabled=true`
5. **Network Policies**: Enable network policies for security

Example production values:

```yaml
replicaCount: 3

ingress:
  enabled: true
  hosts:
    - host: command-center.prod.example.com
  tls:
    - secretName: command-center-tls
      hosts:
        - command-center.prod.example.com

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10

env:
  - name: ENVIRONMENT
    value: "production"
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: command-center-secrets
        key: database-url
```