#!/bin/bash
# Wrapper script to load .env and run CLI commands
# Used by launchd jobs to ensure environment variables are set

cd /Users/ducvu/Projects/nba_stats_dashboard

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run the command with all arguments
exec ./venv/bin/python -m src.cli.main "$@"
