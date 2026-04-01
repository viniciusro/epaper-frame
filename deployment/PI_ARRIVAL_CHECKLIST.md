# Pi arrival checklist

## Hardware
- [ ] Pi Zero 2W + HAT + display connected
- [ ] USB-C power connected
- [ ] HAT seated on all 40 GPIO pins
- [ ] Ribbon cable connected

## First boot
- [ ] Flash Raspberry Pi OS Lite 64-bit via Imager
- [ ] Set hostname: epaper-frame, enable SSH, configure WiFi
- [ ] Boot and confirm: ping epaper-frame.local
- [ ] SSH in: ssh pi@epaper-frame.local

## Deploy
- [ ] git clone https://github.com/viniciusro/epaper-frame.git
- [ ] cd epaper-frame && bash deployment/pi_setup.sh
- [ ] Edit config.yaml — set API key, photo path, Nextcloud if needed
- [ ] sudo systemctl start epaper-frame
- [ ] sudo journalctl -u epaper-frame -f  ← watch first boot

## Validate
- [ ] Display shows test pattern (python -c "from core.display import Display; Display().test_pattern()")
- [ ] Web UI accessible at http://epaper-frame.local
- [ ] First photo renders on display
- [ ] Bottom strip shows live weather + S8 + Pi IP/temp
- [ ] Photo changes after interval
- [ ] Reboot → service restarts automatically

## If SPI errors:
  sudo raspi-config → Interface Options → SPI → Yes → reboot

## If display shows nothing:
  Check ribbon cable seated fully on both ends
  Check PWR LED on HAT is lit
