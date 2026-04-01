#!/bin/bash
set -e
echo ">>> epaper-frame Pi setup"

# System deps
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev \
    libgpiod-dev git rsync

# Enable SPI
sudo raspi-config nonint do_spi 0
echo ">>> SPI enabled"

# Python venv
cd /home/pi/epaper-frame
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo ">>> Python venv ready"

# Create directories
mkdir -p /home/pi/photos
mkdir -p data/cache/nextcloud
mkdir -p logs
echo ">>> Directories created"

# Copy config if not exists
if [ ! -f config.yaml ]; then
    cp config.yaml.example config.yaml
    echo ">>> config.yaml created from example — edit it before starting service"
fi

# Install systemd service
sudo cp deployment/epaper-frame.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable epaper-frame
echo ">>> Service installed and enabled"

echo ""
echo "Setup complete. Next steps:"
echo "  1. Edit config.yaml (add OpenWeatherMap API key, set photo path)"
echo "  2. sudo systemctl start epaper-frame"
echo "  3. sudo journalctl -u epaper-frame -f"
