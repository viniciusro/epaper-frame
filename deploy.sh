#!/bin/bash
set -e
PI_HOST="${PI_HOST:-epaper-frame.local}"
PI_USER="${PI_USER:-pi}"
REMOTE_DIR="/home/pi/epaper-frame"

echo ">>> Deploying to $PI_USER@$PI_HOST"

# Sync code
rsync -avz --exclude '.git' \
           --exclude '__pycache__' \
           --exclude '*.pyc' \
           --exclude 'data/' \
           --exclude 'config.yaml' \
           --exclude 'logs/' \
           --exclude 'venv/' \
           --exclude '*.db' \
           ./ "$PI_USER@$PI_HOST:$REMOTE_DIR/"

# Install any new dependencies
ssh "$PI_USER@$PI_HOST" \
    "cd $REMOTE_DIR && source venv/bin/activate && pip install -r requirements.txt -q"

# Restart service
ssh "$PI_USER@$PI_HOST" "sudo systemctl restart epaper-frame"

# Show last 20 log lines
echo ">>> Last 20 log lines:"
ssh "$PI_USER@$PI_HOST" "sudo journalctl -u epaper-frame -n 20 --no-pager"

echo ">>> Deploy complete"
