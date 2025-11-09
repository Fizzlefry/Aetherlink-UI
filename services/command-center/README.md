# Command Center CI/CD

This GitHub Actions workflow automatically builds and deploys the Command Center Docker image.

## How It Works

### Triggers
- **Push to main/master**: Builds and pushes new image, updates deployment manifests
- **Pull Requests**: Builds image (but doesn't push) for testing
- **Path-based**: Only runs when files in `services/command-center/` change

### Image Tagging Strategy
- `latest`: Latest build on main branch
- `main`: Current main branch
- `main-<short-sha>`: Specific commit on main (used in deployments)
- `pr-<number>`: Pull request builds

### Container Registry
Images are pushed to **GitHub Container Registry (ghcr.io)**:
```
ghcr.io/your-org/AetherLink/command-center:main-abc1234
```

## Manual Deployment

After CI/CD completes, deploy with:

```bash
# Pull latest image
docker pull ghcr.io/your-org/AetherLink/command-center:main

# Or use specific SHA
docker pull ghcr.io/your-org/AetherLink/command-center:main-abc1234

# Run with docker-compose (will auto-update to latest)
docker-compose -f deploy/docker-compose.prod.yml up -d

# Or specify exact version
TAG=main-abc1234 docker-compose -f deploy/docker-compose.prod.yml up -d
```

## Local Development

For local development, the CI/CD pipeline doesn't interfere. Continue using:

```bash
cd services/command-center
docker build -t command-center:dev .
```

## Security Notes

- Uses `GITHUB_TOKEN` for authentication (no secrets needed)
- Images are public in GHCR (change visibility in repo settings if needed)
- Automatic manifest updates ensure deployments always use latest tested image