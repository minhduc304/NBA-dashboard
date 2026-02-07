#!/bin/bash
# Sync database from Cloud Storage to local Mac
# Merges cloud-managed tables without overwriting local-only data.

set -e

PROJECT_DIR="/Users/ducvu/Projects/nba_stats_dashboard"
cd "${PROJECT_DIR}"

python -m src.cli.main sync pull "$@"
