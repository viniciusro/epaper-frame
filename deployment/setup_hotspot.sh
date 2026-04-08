#!/bin/bash
# setup_hotspot.sh — run on Pi to configure the epaper-frame hotspot
# Can be re-run safely to recreate the profile.
set -e

SSID="epaper-frame"
PASSWORD="epaperframe"
CON_NAME="epaper-hotspot"

echo ">>> Removing old hotspot profile (if any)..."
sudo nmcli con delete "$CON_NAME" 2>/dev/null || true

echo ">>> Creating hotspot profile..."
sudo nmcli con add \
    type wifi \
    con-name "$CON_NAME" \
    ssid "$SSID" \
    mode ap \
    ipv4.method shared \
    ipv4.address "192.168.4.1/24" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    802-11-wireless.band bg \
    802-11-wireless.channel 6 \
    connection.autoconnect yes \
    connection.autoconnect-priority -10

echo ">>> Bringing hotspot up..."
sudo nmcli con up "$CON_NAME" || true

echo ">>> Current device status:"
nmcli device status

echo ""
echo "Hotspot '$SSID' configured."
echo "Password: $PASSWORD"
echo "If it doesn't appear immediately, try: sudo nmcli con up epaper-hotspot"
