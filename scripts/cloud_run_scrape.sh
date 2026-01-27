#!/bin/bash
# Cloud Run Scrape Job - Underdog + PrizePicks only
# Runs every 4 hours to get fresh lines (no Odds API credits used)

set -e

echo "=== NBA Stats - Props Scraping ==="
echo "Starting at $(date)"
echo "GCS Bucket: ${GCS_BUCKET:-nba-stats-pipeline-data}"

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
    echo "ERROR: No database found in GCS."
    exit 1
fi

# Run scraping (Underdog + PrizePicks only, no Odds API)
echo ""
echo ">>> Scraping Underdog + PrizePicks..."
python -m src.cli.main --db "${DB_PATH}" scrape no-odds

# Upload updated database back to Cloud Storage
echo ""
echo ">>> Uploading database to GCS..."
gsutil cp "${DB_PATH}" "${GCS_DB_PATH}"
echo "Database uploaded successfully"

echo ""
echo "=== Scraping completed at $(date) ==="
