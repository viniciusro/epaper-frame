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
    dnsmasq \
    wireless-tools          # provides iwlist for WiFi scanning

echo ">>> System packages installed"

# ------------------------------------------------------------------ #
# Enable SPI                                                           #
# ------------------------------------------------------------------ #
sudo raspi-config nonint do_spi 0
echo ">>> SPI enabled"

# ------------------------------------------------------------------ #
# AP+STA via NetworkManager (Bookworm default)                         #
# ------------------------------------------------------------------ #
# Create a hotspot connection profile on wlan0.
# NetworkManager handles the virtual interface internally.
# ipv4.method=shared enables built-in DHCP + NAT for clients.

nmcli_hotspot() {
    sudo nmcli con delete "epaper-hotspot" 2>/dev/null || true
    sudo nmcli con add \
        type wifi \
        ifname wlan0 \
        con-name "epaper-hotspot" \
        autoconnect yes \
        ssid "epaper-frame" \
        mode ap \
        802-11-wireless.band bg \
        802-11-wireless.channel 6 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "epaperframe" \
        ipv4.method shared \
        ipv4.address "192.168.4.1/24"
}

nmcli_hotspot
echo ">>> NetworkManager hotspot profile created (SSID: epaper-frame, password: epaperframe)"

# ------------------------------------------------------------------ #
# dnsmasq: resolve epaper-frame.local on AP network                   #
# ------------------------------------------------------------------ #
# NetworkManager's shared mode already provides DHCP to AP clients.
# We only add a hostname alias so http://epaper-frame.local works
# from phones connected to the hotspot.
sudo mkdir -p /etc/dnsmasq.d
sudo cp "$REPO_DIR/deployment/dnsmasq/epaper-frame.conf" /etc/dnsmasq.d/epaper-frame.conf

# Tell NetworkManager not to touch dnsmasq so our config is respected
if ! grep -q "dns=dnsmasq" /etc/NetworkManager/NetworkManager.conf 2>/dev/null; then
    sudo sed -i '/\[main\]/a dns=dnsmasq' /etc/NetworkManager/NetworkManager.conf
fi
echo ">>> dnsmasq configured"

# ------------------------------------------------------------------ #
# sudoers: allow pi to reboot + run iwlist without password            #
# ------------------------------------------------------------------ #
SUDOERS_FILE="/etc/sudoers.d/epaper-frame"
cat <<'EOF' | sudo tee "$SUDOERS_FILE" > /dev/null
pi ALL=(ALL) NOPASSWD: /sbin/reboot
pi ALL=(ALL) NOPASSWD: /sbin/iwlist
pi ALL=(ALL) NOPASSWD: /usr/sbin/iwlist
EOF
sudo chmod 440 "$SUDOERS_FILE"
echo ">>> sudoers entry added"

# ------------------------------------------------------------------ #
# wpa_supplicant.conf write access via nmcli (not tee)                 #
# On Bookworm, WiFi is managed by NetworkManager — we use nmcli to    #
# add networks, not wpa_supplicant.conf directly.                      #
# Allow pi to run nmcli networking commands without password.          #
# ------------------------------------------------------------------ #
cat <<'EOF' | sudo tee -a "$SUDOERS_FILE" > /dev/null
pi ALL=(ALL) NOPASSWD: /usr/bin/nmcli
EOF
echo ">>> nmcli sudoers entry added"

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
