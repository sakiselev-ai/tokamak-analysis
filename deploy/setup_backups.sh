#!/bin/bash
# Install daily backup cron job
DEPLOY_DIR="/opt/tokamak-analysis"
CRON_CMD="0 3 * * * $DEPLOY_DIR/deploy/backup.sh >> /var/log/tokamak_backup.log 2>&1"

# Add cron if not already present
(crontab -l 2>/dev/null | grep -v "tokamak_backup" ; echo "$CRON_CMD") | crontab -
echo "Daily backup cron installed (3:00 AM)"
echo "Log: /var/log/tokamak_backup.log"
