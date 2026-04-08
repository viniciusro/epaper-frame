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
    libgpiod-dev git rsync \
    fonts-dejavu-core

echo ">>> System packages installed"

# ------------------------------------------------------------------ #
# Enable SPI                                                           #
# ------------------------------------------------------------------ #
sudo raspi-config nonint do_spi 0
echo ">>> SPI enabled"

# ------------------------------------------------------------------ #
# Self-signed TLS certificate for HTTPS                                #
# ------------------------------------------------------------------ #
mkdir -p "$REPO_DIR/data/ssl"
if [ ! -f "$REPO_DIR/data/ssl/cert.pem" ]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$REPO_DIR/data/ssl/key.pem" \
        -out    "$REPO_DIR/data/ssl/cert.pem" \
        -days 3650 \
        -subj "/CN=epaper-frame" \
        -addext "subjectAltName=IP:192.168.4.1,DNS:epaper-frame.local"
    chmod 600 "$REPO_DIR/data/ssl/key.pem"
    echo ">>> TLS certificate generated (valid 10 years)"
else
    echo ">>> TLS certificate already exists, skipping"
fi

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
