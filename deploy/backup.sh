#!/bin/bash
# PostgreSQL backup script for Tokamak Analysis
# Backs up to MinIO S3-compatible storage with AES-256 encryption
# Usage: ./backup.sh [--restore <backup_file>]
# Cron: 0 3 * * * /opt/tokamak-analysis/deploy/backup.sh
# Retention: 7 daily + 4 weekly backups

set -euo pipefail

DEPLOY_DIR="/opt/tokamak-analysis"
BACKUP_DIR="/tmp/tokamak_backups"
DATE=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)
BACKUP_FILE="tokamak_db_${DATE}.sql.gz.enc"
MINIO_BUCKET="backups"
DAILY_RETENTION=7
WEEKLY_RETENTION=28
LOG_FILE="/var/log/tokamak_backup.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$level] $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$ts] [$level] $*"
}

log_info()  { log "INFO"  "$@"; }
log_error() { log "ERROR" "$@"; }
log_warn()  { log "WARN"  "$@"; }

# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Backup failed with exit code $exit_code"
    fi
    # Remove partial backup file on failure
    if [ $exit_code -ne 0 ] && [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        rm -f "$BACKUP_DIR/$BACKUP_FILE"
        log_warn "Removed partial backup file"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
if [ -f "$DEPLOY_DIR/.env" ]; then
    source "$DEPLOY_DIR/.env"
else
    log_warn ".env file not found at $DEPLOY_DIR/.env, using defaults"
fi

PG_USER=${POSTGRES_USER:-tokamak}
PG_DB=${POSTGRES_DB:-tokamak_db}
ENCRYPTION_KEY=${BACKUP_ENCRYPTION_KEY:-}

if [ -z "$ENCRYPTION_KEY" ]; then
    log_error "BACKUP_ENCRYPTION_KEY is not set. Aborting backup."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# ---------------------------------------------------------------------------
# Restore mode
# ---------------------------------------------------------------------------
if [ "${1:-}" == "--restore" ]; then
    RESTORE_FILE="${2:-}"
    if [ -z "$RESTORE_FILE" ]; then
        log_error "Usage: $0 --restore <backup_file>"
        exit 1
    fi
    if [ ! -f "$RESTORE_FILE" ]; then
        log_error "Restore file not found: $RESTORE_FILE"
        exit 1
    fi
    log_info "=== Restoring from $RESTORE_FILE ==="
    openssl enc -aes-256-cbc -d -pbkdf2 -in "$RESTORE_FILE" -pass "pass:$ENCRYPTION_KEY" | \
        gunzip | \
        docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T postgres psql -U "$PG_USER" "$PG_DB"
    log_info "Restore complete"
    exit 0
fi

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
log_info "=== PostgreSQL Backup: $DATE ==="

# Verify postgres is accessible
if ! docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T postgres pg_isready -U "$PG_USER" > /dev/null 2>&1; then
    log_error "PostgreSQL is not ready, aborting backup"
    exit 1
fi

# Dump, compress, encrypt
docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T postgres \
    pg_dump -U "$PG_USER" "$PG_DB" --clean --if-exists | \
    gzip | \
    openssl enc -aes-256-cbc -pbkdf2 -pass "pass:$ENCRYPTION_KEY" \
    > "$BACKUP_DIR/$BACKUP_FILE"

# Verify file is non-empty
if [ ! -s "$BACKUP_DIR/$BACKUP_FILE" ]; then
    log_error "Backup file is empty, aborting"
    rm -f "$BACKUP_DIR/$BACKUP_FILE"
    exit 1
fi

SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
log_info "Backup created: $BACKUP_FILE ($SIZE)"

# ---------------------------------------------------------------------------
# Upload to MinIO
# ---------------------------------------------------------------------------
upload_to_minio() {
    local src_file="$1"
    local dest_path="$2"

    # Ensure bucket exists
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T minio-init sh -c "
        mc alias set local http://minio:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD 2>/dev/null
        mc mb --ignore-existing local/$MINIO_BUCKET 2>/dev/null
    " 2>/dev/null || true

    # Copy into minio container and upload
    local minio_container
    minio_container=$(docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps -q minio)
    docker cp "$src_file" "$minio_container:/tmp/$(basename "$src_file")"
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T minio sh -c \
        "mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD 2>/dev/null && \
         mc cp /tmp/$(basename "$src_file") local/$MINIO_BUCKET/$dest_path 2>/dev/null && \
         rm -f /tmp/$(basename "$src_file")"
}

# Upload daily backup
if upload_to_minio "$BACKUP_DIR/$BACKUP_FILE" "daily/$BACKUP_FILE"; then
    log_info "Uploaded daily backup to MinIO: daily/$BACKUP_FILE"
else
    log_warn "MinIO upload failed (manual backup available at $BACKUP_DIR/$BACKUP_FILE)"
fi

# On Sundays (day 7), also copy as weekly backup
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    WEEKLY_FILE="tokamak_db_weekly_${DATE}.sql.gz.enc"
    if cp "$BACKUP_DIR/$BACKUP_FILE" "$BACKUP_DIR/$WEEKLY_FILE" && \
       upload_to_minio "$BACKUP_DIR/$WEEKLY_FILE" "weekly/$WEEKLY_FILE"; then
        log_info "Uploaded weekly backup to MinIO: weekly/$WEEKLY_FILE"
    else
        log_warn "Weekly MinIO upload failed"
    fi
    rm -f "$BACKUP_DIR/$WEEKLY_FILE"
fi

# ---------------------------------------------------------------------------
# Retention: keep last 7 daily, 4 weekly
# ---------------------------------------------------------------------------
log_info "Applying retention policy: $DAILY_RETENTION days daily, $WEEKLY_RETENTION days weekly"

# Local daily cleanup
deleted_count=$(find "$BACKUP_DIR" -name "tokamak_db_[0-9]*.sql.gz.enc" -mtime +$DAILY_RETENTION -print -delete 2>/dev/null | wc -l)
if [ "$deleted_count" -gt 0 ]; then
    log_info "Removed $deleted_count local daily backups older than $DAILY_RETENTION days"
fi

# Local weekly cleanup
deleted_weekly=$(find "$BACKUP_DIR" -name "tokamak_db_weekly_*.sql.gz.enc" -mtime +$WEEKLY_RETENTION -print -delete 2>/dev/null | wc -l)
if [ "$deleted_weekly" -gt 0 ]; then
    log_info "Removed $deleted_weekly local weekly backups older than $WEEKLY_RETENTION days"
fi

# MinIO retention (remove old daily backups from MinIO)
docker compose -f "$DEPLOY_DIR/docker-compose.yml" exec -T minio sh -c "
    mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD 2>/dev/null
    mc rm --older-than ${DAILY_RETENTION}d --force local/$MINIO_BUCKET/daily/ 2>/dev/null || true
    mc rm --older-than ${WEEKLY_RETENTION}d --force local/$MINIO_BUCKET/weekly/ 2>/dev/null || true
" 2>/dev/null || log_warn "MinIO retention cleanup skipped"

log_info "=== Backup complete ==="
