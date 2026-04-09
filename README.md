# epaper-frame

13.3" 6-color e-Paper digital photo frame running on Raspberry Pi Zero 2W.

Displays photos from a local folder, web uploads, Nextcloud, or the National Gallery of Art open-access collection — with a live info strip showing weather, S-Bahn departures, and Pi stats. Controlled via a web UI.

## Hardware

| Component | Model |
|-----------|-------|
| Display | Waveshare 13.3" Spectra 6 e-Paper HAT (1200×1600, 6-color) |
| Computer | Raspberry Pi Zero 2W |
| Connection | SPI via GPIO header |

**Display colors:** black, white, red, green, blue, yellow — Floyd-Steinberg dithered.
**Refresh time:** ~30 seconds (full global refresh).
**Rated lifetime:** 1,000,000 refreshes (tracked in web UI).

## Setup

### 1. Prepare the Pi

Flash Raspberry Pi OS Lite (64-bit), enable SSH and set hostname to `epaper-frame`.

```bash
# On the Pi after first boot
git clone https://github.com/viniciusro/epaper-frame.git
cd epaper-frame
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys and settings
```

### 2. Run the setup script

```bash
cd /home/pi/epaper-frame
sudo bash deployment/pi_setup.sh
sudo reboot
```

This installs all dependencies, sets up the systemd service, enables SPI, generates the self-signed TLS certificate, and configures sudoers for web UI reboot/restart.

### 3. Deploy updates (from Windows)

```bash
# In Git Bash from the project root:
./deploy.sh

# Override Pi address if needed:
PI_HOST=192.168.1.x ./deploy.sh
```

Or pull directly on the Pi:
```bash
ssh pi@epaper-frame.local "cd epaper-frame && git pull && sudo systemctl restart epaper-frame"
```

## Configuration

Copy `config.yaml.example` → `config.yaml` (never committed). All settings can also be changed live from the web UI without restarting the service.

| Key | Description |
|-----|-------------|
| `display.interval_minutes` | How often to change photo (default: 60) |
| `display.no_repeat_days` | Days before a photo can repeat (default: 7) |
| `display.strip_text_color` | `auto` (detect from photo), `#ffffff`, `#000000`, or any hex color |
| `display.sleep_start` / `sleep_end` | HH:MM — display blanks during this window; click Wake Up to exit early |
| `display.strip.*` | Enable/disable individual strip elements (weather, transit, IP, CPU temp, AQI, location) |
| `sources.local_folder.path` | Path to local photo folder (default: `/home/pi/photos`) |
| `sources.nextcloud.*` | WebDAV credentials, remote path, sync interval, cache size |
| `sources.nga.enabled` | Enable National Gallery of Art collection (exclusive mode) |
| `sources.nga.cache_size` | Number of NGA artworks to keep on disk (default: 50) |
| `weather.api_key` | OpenWeatherMap API key (also used for air quality index) |
| `weather.city` | City name for weather |
| `transit.mvg_global_id` | MVG stop identifier |
| `transit.line` | S-Bahn line to filter (default: S8) |
| `transit.direction_filter` | Filter departures by destination — use "Load from MVG" in Config |
| `telegram.bot_token` | Telegram bot token from @BotFather — leave blank to disable |
| `web.port` | Web UI port (default: 80) |

## Web UI

Access at `https://epaper-frame.local` (or by IP). Uses a self-signed TLS certificate — accept the browser warning once.

| Page | Description |
|------|-------------|
| **Status** | Current photo, photo source, display health, next refresh countdown, weather + AQI, S-Bahn departures, Pi stats (IP, CPU temp, CPU load, SD card usage) |
| **Gallery** | Browse and delete photos from the local folder with thumbnails |
| **Logs** | Live service log viewer (last 200 lines, auto-refresh every 5s, color-coded by level) |
| **Preview** | PNG of what's currently rendered on the display |
| **Config** | All settings — display, sleep schedule, strip toggles, weather, transit, Nextcloud, NGA, Telegram |

**Actions on the status page:**
- **Next Photo / Wake Up** — skip to next photo, or wake from sleep immediately
- **Upload** — add a photo directly from the browser
- **Config → Restart Service** — restart the epaper-frame process (~10s)
- **Config → Reboot Pi** — full Pi reboot (~30s)

## Photo sources

Sources are exclusive — only one active pool at a time:

| Mode | Active when | What shows |
|------|-------------|-----------|
| **NGA** | `sources.nga.enabled: true` | National Gallery of Art (~50k public domain artworks) |
| **Nextcloud** | `sources.nextcloud.enabled: true` | Photos from configured WebDAV folder |
| **Local** | Neither NGA nor Nextcloud enabled | Local folder + uploads |

Uploaded photos (web UI or Telegram bot) always jump to the front of the queue regardless of mode.

## Telegram bot

Create a bot via @BotFather, paste the token into Config → Telegram Bot. Send any photo to the bot and it will appear on the display at the next refresh cycle.

The bot also sends alerts to your chat if:
- The display has not refreshed in 24 hours
- The display loop crashes (before systemd restarts the service)

## Info strip

The bottom 150px of the display shows live info overlaid on the photo:

- **Left:** weather (temp, city, condition) + next 2 S-Bahn departures with real-time delay
- **Right:** IP address, CPU temperature, and one of: GPS location (from photo EXIF) / AQI label / nothing

Text color is auto-detected from photo brightness by default (switches between black and white for contrast). Can be overridden in Config.

Each element can be individually enabled or disabled in Config → Info strip.

## Display health

The web UI status page shows a refresh counter (e.g. `42 / 1,000,000 — 0.0% used`). The Waveshare Spectra 6 panel is rated for 1 million full refreshes. Counter is stored in `data/refresh_count.txt` and survives reboots.

## Sleep schedule

Set `sleep_start` and `sleep_end` (HH:MM, 24h) in Config to blank the display during those hours. Supports midnight-crossing windows (e.g. 23:00 → 07:00). Click **Wake Up** on the status page to exit sleep early.

## Local development (no hardware)

```bash
pip install -r requirements.txt -r requirements-dev.txt
EPAPER_MOCK=1 python main.py
# Preview saved to system temp dir as epaper_preview.png

pytest                        # run all tests
pytest tests/test_renderer.py # run a single test file
```

## Service management (on Pi)

```bash
sudo journalctl -u epaper-frame -f        # follow logs (or use Logs page in web UI)
sudo systemctl restart epaper-frame       # restart
sudo systemctl status epaper-frame        # check status
curl -X POST https://epaper-frame.local/next -k  # force next photo
```
