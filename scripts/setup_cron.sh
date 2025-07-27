#!/bin/bash

# Simple Cron Setup for Canvas Scraper
# Runs the scraper daily at 2 AM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up Canvas scraper cron job..."
echo "Project directory: $PROJECT_DIR"

# Create the cron entry
CRON_ENTRY="0 2 * * * cd $PROJECT_DIR && python3 scripts/run_scraper.py >> logs/cron.log 2>&1"

# Add to crontab if not already present
(crontab -l 2>/dev/null | grep -v "run_scraper.py"; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job added successfully!"
echo "Canvas scraper will run daily at 2:00 AM"
echo "Check logs in: $PROJECT_DIR/logs/"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo "To view current cron jobs: crontab -l"
echo "To remove cron job: crontab -e (then delete the line)"