#!/bin/bash
set -e
echo ">>> epaper-frame Pi setup"

REPO_DIR="/home/pi/epaper-frame"

# ------------------------------------------------------------------ #
# System dependencies                                                  #
# ------------------------------------------------------------------ #
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv python3-dev \
    libgpiod-dev git rsync

echo ">>> System packages installed"

# ------------------------------------------------------------------ #
# Enable SPI                                                           #
# ------------------------------------------------------------------ #
sudo raspi-config nonint do_spi 0
echo ">>> SPI enabled"

# ------------------------------------------------------------------ #
# Python venv                                                          #
# ------------------------------------------------------------------ #
cd "$REPO_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ">>> Python venv ready"

# ------------------------------------------------------------------ #
# Directories                                                          #
# ------------------------------------------------------------------ #
mkdir -p /home/pi/photos
mkdir -p data/cache/nextcloud
mkdir -p data/cache/nga
mkdir -p logs
echo ">>> Directories created"

# ------------------------------------------------------------------ #
# Config                                                               #
# ------------------------------------------------------------------ #
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml
    echo ">>> config.yaml created from example — edit it before starting service"
fi

# ------------------------------------------------------------------ #
# epaper-frame systemd service                                         #
# ------------------------------------------------------------------ #
sudo cp "$REPO_DIR/deployment/epaper-frame.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable epaper-frame
echo ">>> epaper-frame service installed and enabled"

echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Next steps:"
echo "   1. Edit config.yaml with your API keys"
echo "   2. sudo reboot"
