#!/bin/bash
# Prometheus Snapshot Script - Create timestamped snapshots
# Run before version upgrades or major configuration changes

set -euo pipefail

# Configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
SNAPSHOT_DIR="/backups/prometheus"
RETENTION_COUNT=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

mkdir -p "$SNAPSHOT_DIR"

log "Creating Prometheus snapshot..."

# Trigger snapshot via API
SNAPSHOT_NAME=$(curl -sS -X POST "$PROMETHEUS_URL/api/v1/admin/tsdb/snapshot" | jq -r '.data.name')

if [ -z "$SNAPSHOT_NAME" ] || [ "$SNAPSHOT_NAME" = "null" ]; then
    log "ERROR: Failed to create snapshot"
    exit 1
fi

log "Snapshot created: $SNAPSHOT_NAME"

# Copy snapshot from container
docker cp aether-prometheus:/prometheus/snapshots/"$SNAPSHOT_NAME" "$SNAPSHOT_DIR/snapshot_${TIMESTAMP}"

# Compress snapshot
log "Compressing snapshot..."
tar -czf "$SNAPSHOT_DIR/snapshot_${TIMESTAMP}.tar.gz" -C "$SNAPSHOT_DIR" "snapshot_${TIMESTAMP}"
rm -rf "$SNAPSHOT_DIR/snapshot_${TIMESTAMP}"

# Clean up old snapshots (keep last N)
log "Cleaning old snapshots (keeping $RETENTION_COUNT)..."
ls -t "$SNAPSHOT_DIR"/snapshot_*.tar.gz | tail -n +$((RETENTION_COUNT + 1)) | xargs -r rm

log "Snapshot complete: snapshot_${TIMESTAMP}.tar.gz"
log "Size: $(du -h "$SNAPSHOT_DIR/snapshot_${TIMESTAMP}.tar.gz" | cut -f1)"
