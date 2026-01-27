#!/bin/bash
# Sync database from Cloud Storage to local Mac
# Run this after the Cloud Run pipeline completes to get the latest data

set -e

# Configuration
PROJECT_DIR="/Users/ducvu/Projects/nba_stats_dashboard"
GCS_BUCKET="nba-stats-pipeline-data"
LOCAL_DB="${PROJECT_DIR}/data/nba_stats.db"
BACKUP_DIR="${PROJECT_DIR}/data/backups"
LOG_FILE="${PROJECT_DIR}/logs/sync.log"

cd "${PROJECT_DIR}"

# Create log directory if needed
mkdir -p "$(dirname ${LOG_FILE})"
mkdir -p "${BACKUP_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting database sync from Cloud Storage..."

# Check if gsutil is available
if ! command -v gsutil &> /dev/null; then
    log "ERROR: gsutil not found. Install Google Cloud SDK: brew install google-cloud-sdk"
    exit 1
fi

# Backup current database if it exists
if [ -f "${LOCAL_DB}" ]; then
    BACKUP_FILE="${BACKUP_DIR}/nba_stats_$(date +%Y%m%d_%H%M%S).db"
    log "Backing up current database to ${BACKUP_FILE}"
    cp "${LOCAL_DB}" "${BACKUP_FILE}"

    # Keep only last 7 backups
    ls -t "${BACKUP_DIR}"/nba_stats_*.db 2>/dev/null | tail -n +8 | xargs -r rm
fi

# Download from GCS
log "Downloading from gs://${GCS_BUCKET}/nba_stats.db..."
if gsutil cp "gs://${GCS_BUCKET}/nba_stats.db" "${LOCAL_DB}"; then
    SIZE=$(du -h "${LOCAL_DB}" | cut -f1)
    log "Database synced successfully (${SIZE})"
else
    log "ERROR: Failed to download database from GCS"
    exit 1
fi

# Also sync trained models if they exist in cloud
if gsutil -q stat "gs://${GCS_BUCKET}/trained_models/*.joblib" 2>/dev/null; then
    log "Syncing trained models..."
    gsutil -m cp "gs://${GCS_BUCKET}/trained_models/*.joblib" "${PROJECT_DIR}/trained_models/"
    log "Models synced"
fi

log "Sync completed successfully"
