#!/bin/bash
# PostgreSQL backup script for Tokamak Analysis
# Backs up to MinIO S3-compatible storage with AES-256 encryption
# Usage: ./backup.sh [--restore <backup_file>]
# Cron: 0 3 * * * /opt/tokamak-analysis/deploy/backup.sh

set -e
DEPLOY_DIR="/opt/tokamak-analysis"
BACKUP_DIR="/tmp/tokamak_backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="tokamak_db_${DATE}.sql.gz.enc"

# Load env
source "$DEPLOY_DIR/.env" 2>/dev/null || true
PG_USER=${POSTGRES_USER:-tokamak}
PG_DB=${POSTGRES_DB:-tokamak_db}
ENCRYPTION_KEY=${BACKUP_ENCRYPTION_KEY:-$(openssl rand -hex 32)}

mkdir -p "$BACKUP_DIR"

if [ "$1" == "--restore" ]; then
    echo "=== Restoring from $2 ==="
    # Decrypt and decompress
    openssl enc -aes-256-cbc -d -pbkdf2 -in "$2" -pass "pass:$ENCRYPTION_KEY" | \
        gunzip | \
        docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T postgres psql -U "$PG_USER" "$PG_DB"
    echo "Restore complete"
    exit 0
fi

echo "=== PostgreSQL Backup: $DATE ==="

# Dump
docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T postgres \
    pg_dump -U "$PG_USER" "$PG_DB" --clean --if-exists | \
    gzip | \
    openssl enc -aes-256-cbc -pbkdf2 -pass "pass:$ENCRYPTION_KEY" \
    > "$BACKUP_DIR/$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "Backup created: $BACKUP_FILE ($SIZE)"

# Upload to MinIO
docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T minio-init sh -c "
    mc alias set local http://minio:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD 2>/dev/null
    mc mb --ignore-existing local/backups 2>/dev/null
" 2>/dev/null || true

# Copy backup into minio container and upload
docker cp "$BACKUP_DIR/$BACKUP_FILE" \
    $(docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps -q minio):/tmp/$BACKUP_FILE 2>/dev/null && \
docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T minio \
    mc cp /tmp/$BACKUP_FILE local/backups/$BACKUP_FILE 2>/dev/null || \
echo "MinIO upload skipped (manual backup available at $BACKUP_DIR/$BACKUP_FILE)"

# Cleanup old backups
find "$BACKUP_DIR" -name "tokamak_db_*.sql.gz.enc" -mtime +$RETENTION_DAYS -delete
echo "Cleaned up backups older than $RETENTION_DAYS days"

echo "=== Backup complete ==="
