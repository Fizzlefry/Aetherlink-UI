#!/bin/bash
# AetherLink Installer Script
# Phase XXX: Minimal Helm-like installer for multi-env deployment

set -e

# Default values
ENVIRONMENT="dev"
DOMAIN="aetherlink.local"
NAMESPACE="aetherlink"
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "AetherLink Installer v${VERSION}"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --env ENV        Environment tier (dev|staging|prod) [default: dev]"
    echo "  --domain DOMAIN  Domain name for ingress [default: aetherlink.local]"
    echo "  --namespace NS   Kubernetes namespace [default: aetherlink]"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --env staging --domain ops.company.com"
    echo "  $0 --env prod --domain aetherlink.company.com --namespace production"
}

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    dev|staging|prod)
        log "Environment set to: $ENVIRONMENT"
        ;;
    *)
        error "Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
        exit 1
        ;;
esac

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        error "Docker is required but not installed."
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        warn "kubectl not found. Will install for local Docker Desktop."
    fi

    log "Prerequisites check complete."
}

# Generate configuration
generate_config() {
    log "Generating configuration for environment: $ENVIRONMENT"

    # Create config directory
    mkdir -p "deploy/${ENVIRONMENT}"

    # Copy base config
    cp deploy/config.yml "deploy/${ENVIRONMENT}/config.yml"

    # Environment-specific overrides
    case $ENVIRONMENT in
        dev)
            sed -i 's/environment: "dev"/environment: "dev"/' "deploy/${ENVIRONMENT}/config.yml"
            ;;
        staging)
            sed -i 's/environment: "dev"/environment: "staging"/' "deploy/${ENVIRONMENT}/config.yml"
            sed -i 's/adaptive_dry_run: true/adaptive_dry_run: false/' "deploy/${ENVIRONMENT}/config.yml"
            ;;
        prod)
            sed -i 's/environment: "dev"/environment: "prod"/' "deploy/${ENVIRONMENT}/config.yml"
            sed -i 's/adaptive_dry_run: true/adaptive_dry_run: false/' "deploy/${ENVIRONMENT}/config.yml"
            sed -i 's/demo_data: true/demo_data: false/' "deploy/${ENVIRONMENT}/config.yml"
            ;;
    esac

    log "Configuration generated in deploy/${ENVIRONMENT}/"
}

# Build and push container image
build_image() {
    log "Building container image..."

    IMAGE_TAG="aetherlink/command-center:${VERSION}-${ENVIRONMENT}"

    docker build -t "$IMAGE_TAG" \
        --label "com.aetherlink.environment=${ENVIRONMENT}" \
        --label "com.aetherlink.domain=${DOMAIN}" \
        .

    log "Image built: $IMAGE_TAG"
}

# Generate Kubernetes manifests
generate_k8s_manifests() {
    log "Generating Kubernetes manifests..."

    cat > "deploy/${ENVIRONMENT}/deployment.yml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aetherlink-command-center
  namespace: ${NAMESPACE}
  labels:
    app: aetherlink
    component: command-center
    environment: ${ENVIRONMENT}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aetherlink
      component: command-center
  template:
    metadata:
      labels:
        app: aetherlink
        component: command-center
        environment: ${ENVIRONMENT}
        com.aetherlink.service: command-center
        com.aetherlink.version: ${VERSION}
    spec:
      containers:
      - name: command-center
        image: aetherlink/command-center:${VERSION}-${ENVIRONMENT}
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "${ENVIRONMENT}"
        - name: DOMAIN
          value: "${DOMAIN}"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/env
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

    cat > "deploy/${ENVIRONMENT}/service.yml" << EOF
apiVersion: v1
kind: Service
metadata:
  name: aetherlink-command-center
  namespace: ${NAMESPACE}
  labels:
    app: aetherlink
    component: command-center
    environment: ${ENVIRONMENT}
spec:
  selector:
    app: aetherlink
    component: command-center
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
EOF

    cat > "deploy/${ENVIRONMENT}/ingress.yml" << EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: aetherlink-command-center
  namespace: ${NAMESPACE}
  labels:
    app: aetherlink
    component: command-center
    environment: ${ENVIRONMENT}
spec:
  rules:
  - host: ${DOMAIN}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: aetherlink-command-center
            port:
              number: 80
EOF

    log "Kubernetes manifests generated in deploy/${ENVIRONMENT}/"
}

# Deploy to Kubernetes
deploy_k8s() {
    log "Deploying to Kubernetes namespace: ${NAMESPACE}"

    # Create namespace if it doesn't exist
    kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

    # Apply manifests
    kubectl apply -f "deploy/${ENVIRONMENT}/"

    log "Deployment complete. Waiting for rollout..."
    kubectl rollout status deployment/aetherlink-command-center -n "${NAMESPACE}" --timeout=300s

    log "🎉 AetherLink deployed successfully!"
    log "🌐 Access at: http://${DOMAIN}"
    log "🔍 Health check: http://${DOMAIN}/health/env"
}

# Main installation process
main() {
    log "🚀 Starting AetherLink installation (v${VERSION})"
    log "Environment: ${ENVIRONMENT}"
    log "Domain: ${DOMAIN}"
    log "Namespace: ${NAMESPACE}"

    check_prerequisites
    generate_config
    build_image
    generate_k8s_manifests
    deploy_k8s

    log "✅ Installation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Configure DNS for ${DOMAIN}"
    echo "2. Set up monitoring stack (Prometheus/Grafana)"
    echo "3. Configure tenant API keys"
    echo "4. Test AI guardrails: curl http://${DOMAIN}/health/env"
}

# Run main function
main "$@"
