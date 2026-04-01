#!/bin/bash
PI_HOST="${PI_HOST:-epaper-frame.local}"
PI_USER="${PI_USER:-pi}"
REMOTE_DIR="/home/pi/epaper-frame"

echo ">>> Syncing to $PI_USER@$PI_HOST:$REMOTE_DIR"
rsync -avz --exclude '.git' --exclude '__pycache__' \
      --exclude '*.pyc' --exclude 'data/' \
      --exclude 'config.yaml' \
      ./ "$PI_USER@$PI_HOST:$REMOTE_DIR/"

echo ">>> Restarting service"
ssh "$PI_USER@$PI_HOST" "sudo systemctl restart epaper-frame"

echo ">>> Done"
