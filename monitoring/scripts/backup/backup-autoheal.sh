#!/bin/bash
# Autoheal Backup Script - Nightly rotation and cloud sync
# Run via cron: 0 2 * * * /path/to/backup-autoheal.sh

set -euo pipefail

# Configuration
BACKUP_DIR="/backups/autoheal"
AUDIT_DATA_DIR="/data/autoheal"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Cloud backup (optional - configure rclone)
CLOUD_BACKUP_ENABLED="${CLOUD_BACKUP_ENABLED:-false}"
RCLONE_REMOTE="${RCLONE_REMOTE:-s3:aetherlink-backups/autoheal}"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

log "Starting autoheal backup..."

# 1. Backup audit trail (compressed)
if [ -f "$AUDIT_DATA_DIR/audit.jsonl" ]; then
    log "Backing up audit trail..."
    cp "$AUDIT_DATA_DIR/audit.jsonl" "$BACKUP_DIR/audit_${TIMESTAMP}.jsonl"
    gzip "$BACKUP_DIR/audit_${TIMESTAMP}.jsonl"
    log "Audit trail backed up: audit_${TIMESTAMP}.jsonl.gz"
else
    log "WARNING: Audit trail not found at $AUDIT_DATA_DIR/audit.jsonl"
fi

# 2. Backup rotated audit archives
if ls "$AUDIT_DATA_DIR"/audit.jsonl-* 1> /dev/null 2>&1; then
    log "Backing up rotated archives..."
    for archive in "$AUDIT_DATA_DIR"/audit.jsonl-*; do
        filename=$(basename "$archive")
        cp "$archive" "$BACKUP_DIR/${filename}_${TIMESTAMP}"
        log "Archived: ${filename}"
    done
fi

# 3. Clean up old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "audit_*.jsonl.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "audit.jsonl-*" -mtime +$RETENTION_DAYS -delete

# 4. Cloud sync (if enabled)
if [ "$CLOUD_BACKUP_ENABLED" = "true" ]; then
    log "Syncing to cloud storage: $RCLONE_REMOTE"
    if command -v rclone &> /dev/null; then
        rclone sync "$BACKUP_DIR" "$RCLONE_REMOTE" \
            --log-level INFO \
            --stats 1m \
            --exclude "*.tmp"
        log "Cloud sync complete"
    else
        log "WARNING: rclone not installed, skipping cloud sync"
    fi
fi

# 5. Generate backup manifest
log "Generating backup manifest..."
cat > "$BACKUP_DIR/manifest_${TIMESTAMP}.txt" <<EOF
Autoheal Backup Manifest
Generated: $(date)
Backup Directory: $BACKUP_DIR
Retention Days: $RETENTION_DAYS

Files Backed Up:
$(ls -lh "$BACKUP_DIR" | grep -E "audit_.*\.jsonl\.gz|audit\.jsonl-")

Disk Usage:
$(du -sh "$BACKUP_DIR")
EOF

log "Backup complete!"
log "Manifest: $BACKUP_DIR/manifest_${TIMESTAMP}.txt"
