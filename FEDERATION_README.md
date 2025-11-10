# AetherLink Federation Configuration

## Overview
AetherLink Command Centers can form a federated mesh to share monitoring data across multiple deployments. This enables global awareness and coordinated operations.

## Configuration Environment Variables

```bash
# Federation control
AETHERLINK_FEDERATION_ENABLED=true
AETHERLINK_FEDERATION_PEERS=http://aether-command-center:8010,http://cc-prod:8010
AETHERLINK_FEDERATION_KEY=<shared-secret-key>
AETHERLINK_NODE_ID=cc-local
AETHERLINK_FEDERATION_INTERVAL=15
```

## Endpoints

### Federation Data
- `GET /federation/feed` - Global feed combining local + peer data (requires federation key)
- `GET /federation/feed/explain` - Human-readable global status explanation
- `GET /federation/peers` - Current peer configuration
- `GET /federation/health` - Federation connectivity health check

### Local Endpoints (Federation-Aware)
- `GET /ops/feed` - Local feed (accepts federation key for cross-node access)
- `GET /ops/feed/explain` - Local status explanation

## Security
- Federation requests require `x-fed-key` header with shared secret
- Local operator endpoints remain protected by RBAC
- Federation keys enable secure cross-node communication

## Architecture
- **Polling-based**: Nodes periodically fetch data from peers
- **Shared keys**: Simple authentication without complex PKI
- **Merge logic**: Deduplicates alerts by (alertname, service) pairs
- **Origin tagging**: Tracks which node originated each alert

## Use Cases
- Multi-region deployments
- Development/staging/production coordination
- Disaster recovery awareness
- Global incident response
