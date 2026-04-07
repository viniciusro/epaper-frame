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
    hostapd dnsmasq \
    wireless-tools          # provides iwlist for WiFi scanning

echo ">>> System packages installed"

# ------------------------------------------------------------------ #
# Enable SPI                                                           #
# ------------------------------------------------------------------ #
sudo raspi-config nonint do_spi 0
echo ">>> SPI enabled"

# ------------------------------------------------------------------ #
# AP+STA: virtual uap0 interface                                       #
# ------------------------------------------------------------------ #

# Install create-uap0 systemd service
sudo cp "$REPO_DIR/deployment/services/create-uap0.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable create-uap0
echo ">>> uap0 interface service installed"

# Configure static IP for uap0 via systemd-networkd
sudo mkdir -p /etc/systemd/network
sudo cp "$REPO_DIR/deployment/network/12-uap0.network" /etc/systemd/network/
sudo systemctl enable systemd-networkd
echo ">>> uap0 network config installed"

# ------------------------------------------------------------------ #
# hostapd                                                              #
# ------------------------------------------------------------------ #
sudo systemctl unmask hostapd
sudo cp "$REPO_DIR/deployment/hostapd/hostapd.conf" /etc/hostapd/hostapd.conf
# Point hostapd at our config
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd > /dev/null
sudo systemctl enable hostapd
echo ">>> hostapd configured (SSID: epaper-frame, password: epaperframe)"

# ------------------------------------------------------------------ #
# dnsmasq                                                              #
# ------------------------------------------------------------------ #
sudo mkdir -p /etc/dnsmasq.d
sudo cp "$REPO_DIR/deployment/dnsmasq/epaper-frame.conf" /etc/dnsmasq.d/epaper-frame.conf
sudo systemctl enable dnsmasq
echo ">>> dnsmasq configured"

# ------------------------------------------------------------------ #
# sudoers: allow pi to reboot + write wpa_supplicant without password  #
# ------------------------------------------------------------------ #
SUDOERS_LINE="pi ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/iwlist, /usr/bin/tee /etc/wpa_supplicant/wpa_supplicant.conf"
echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/epaper-frame > /dev/null
sudo chmod 440 /etc/sudoers.d/epaper-frame
echo ">>> sudoers entry added"

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
echo " The Pi will broadcast WiFi: epaper-frame"
echo " Password: epaperframe"
echo ""
echo " On first boot without home WiFi:"
echo "   1. Connect phone to 'epaper-frame' hotspot"
echo "   2. Open http://192.168.4.1:5000/wifi"
echo "   3. Select your network and enter password"
echo "   4. Frame reboots and connects automatically"
echo ""
echo " Next steps:"
echo "   sudo reboot"
