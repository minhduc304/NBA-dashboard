#!/bin/bash
# Cloud Run Entrypoint Script
# Downloads database from GCS, runs ML pipeline, uploads updated database

set -e

echo "=== NBA Stats Pipeline - Cloud Run ==="
echo "Starting at $(date)"
echo "GCS Bucket: ${GCS_BUCKET:-nba-stats-pipeline-data}"
echo "DB Path: ${DB_PATH:-/app/data/nba_stats.db}"

# Configuration
GCS_BUCKET="${GCS_BUCKET:-nba-stats-pipeline-data}"
DB_PATH="${DB_PATH:-/app/data/nba_stats.db}"
GCS_DB_PATH="gs://${GCS_BUCKET}/nba_stats.db"

# Download database from Cloud Storage
echo ""
echo ">>> Downloading database from GCS..."
if gsutil -q stat "${GCS_DB_PATH}"; then
    gsutil cp "${GCS_DB_PATH}" "${DB_PATH}"
    echo "Database downloaded successfully ($(du -h ${DB_PATH} | cut -f1))"
else
    echo "WARNING: No existing database found in GCS. Starting fresh."
fi

# Run the ML pipeline
echo ""
echo ">>> Running ML pipeline..."
python -m src.cli.main --db "${DB_PATH}" ml pipeline

# Upload updated database back to Cloud Storage
echo ""
echo ">>> Uploading database to GCS..."
gsutil cp "${DB_PATH}" "${GCS_DB_PATH}"
echo "Database uploaded successfully"

# Also upload trained models if they were updated (Sunday retraining)
if [ "$(date +%u)" = "7" ]; then
    echo ""
    echo ">>> Sunday detected - uploading trained models..."
    gsutil -m cp trained_models/*.joblib "gs://${GCS_BUCKET}/trained_models/"
    echo "Models uploaded successfully"
fi

echo ""
echo "=== Pipeline completed at $(date) ==="
