#!/bin/bash
# ============================================================
# Install cron jobs for the financial pipeline on Oracle Cloud
# Run this ON the Oracle instance (not locally)
# ============================================================
set -euo pipefail

PIPELINE_DIR="/home/ubuntu/finance-pipeline"
VENV="$PIPELINE_DIR/venv/bin"
LOG_DIR="/var/log/finance-pipeline"

echo "Setting up cron jobs for the financial pipeline"
echo "================================================"

# --- Create log directory ---
echo "[1/3] Creating log directory..."
sudo mkdir -p "$LOG_DIR"
sudo chown ubuntu:ubuntu "$LOG_DIR"

# --- Set up log rotation ---
echo "[2/3] Configuring log rotation..."
sudo tee /etc/logrotate.d/finance-pipeline > /dev/null << EOF
$LOG_DIR/*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
}
EOF

# --- Install cron jobs ---
echo "[3/3] Installing cron jobs..."

# Build the crontab entries
CRON_CONTENT=$(cat << EOF
# ============================================================
# Financial Data Pipeline - Automated Jobs
# ============================================================

# Daily 6:00 AM - Scrape and analyze high-priority companies
0 6 * * * cd $PIPELINE_DIR && $VENV/python3 -m cli.main run --tier high >> $LOG_DIR/daily.log 2>&1

# Weekly Sunday 2:00 AM - Scrape and analyze low-priority companies
0 2 * * 0 cd $PIPELINE_DIR && $VENV/python3 -m cli.main run --tier low >> $LOG_DIR/weekly.log 2>&1

# ============================================================
EOF
)

# Preserve any existing non-pipeline cron jobs
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -v "finance-pipeline\|Financial Data Pipeline\|cli.main\|======" || true)

# Write combined crontab
(
    if [ -n "$EXISTING_CRON" ]; then
        echo "$EXISTING_CRON"
        echo ""
    fi
    echo "$CRON_CONTENT"
) | crontab -

echo ""
echo "Cron jobs installed. Current crontab:"
echo "--------------------------------------"
crontab -l
echo "--------------------------------------"
echo ""
echo "Log files:"
echo "  Daily:  $LOG_DIR/daily.log"
echo "  Weekly: $LOG_DIR/weekly.log"
echo ""
echo "Useful commands:"
echo "  View logs:     tail -f $LOG_DIR/daily.log"
echo "  Edit cron:     crontab -e"
echo "  Remove cron:   crontab -r"
echo ""
