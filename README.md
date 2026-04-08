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
**Refresh time:** ~24 seconds (full global refresh).

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

This installs all dependencies, sets up the systemd service, and enables SPI.

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

Copy `config.yaml.example` → `config.yaml` (never committed). Key settings:

| Key | Description |
|-----|-------------|
| `display.interval_minutes` | How often to change photo (default: 60) |
| `display.no_repeat_days` | Days before a photo can repeat (default: 7) |
| `display.strip_text_color` | Hex color for info strip text (default: `#ffffff`) |
| `display.sleep_start` / `sleep_end` | HH:MM hours — display blanks during this window |
| `display.strip.*` | Enable/disable individual strip elements (weather, transit, IP, CPU, AQI, location) |
| `sources.local_folder.path` | Path to local photo folder |
| `sources.nextcloud.*` | WebDAV credentials for Nextcloud sync |
| `sources.nga.enabled` | Enable National Gallery of Art collection |
| `sources.nga.cache_size` | Number of NGA artworks to keep on disk (default: 50) |
| `weather.api_key` | OpenWeatherMap API key (also used for air quality) |
| `weather.city` | City name for weather |
| `transit.mvg_global_id` | MVG stop identifier |
| `transit.direction_filter` | Filter departures by destination |
| `telegram.bot_token` | Telegram bot token from @BotFather — leave blank to disable |
| `web.port` | Web UI port (default: 5000) |

Most settings can be changed live from the web UI without restarting the service.

## Web UI

Access at `https://epaper-frame.local:5000` (or by IP). Uses a self-signed TLS certificate — accept the browser warning once.

- **Status** — current photo, countdown, weather + AQI, S-Bahn departures, Pi stats
- **Gallery** — browse and delete photos from the local folder
- **Preview** — PNG of what's currently on the display
- **Next Photo** — skip to next photo immediately
- **Upload** — add a photo directly from the browser
- **Config** — all settings: display, strip toggles, sleep schedule, weather, transit, Nextcloud, NGA, Telegram bot token

## Photo sources

| Source | Description | Priority |
|--------|-------------|----------|
| **Upload** | Photos added via web UI or Telegram bot | Highest — always shown next |
| **National Gallery of Art** | ~50k open-access public domain artworks, downloaded automatically via IIIF API | High — exclusive when enabled |
| **Local folder** | Photos from a folder on the Pi (default: `/home/pi/photos`) | Normal |
| **Nextcloud** | Synced from a WebDAV/Nextcloud server | Normal |

When NGA is enabled it takes over the display exclusively — disable it in Config to return to personal photos. Uploaded photos (web or Telegram) always jump to the front of the queue.

## Telegram bot

Create a bot via @BotFather, paste the token into Config. Send any photo to the bot and it will appear on the display at the next refresh cycle.

## Info strip

The bottom 150px of the display shows live info overlaid on the photo:

- **Left:** weather (temp, city, condition) + next 2 S-Bahn departures with delay
- **Right:** IP address, CPU temperature, and one of: GPS location (from photo EXIF) / AQI / last updated time

Each element can be individually enabled or disabled in Config → Info strip.

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
sudo journalctl -u epaper-frame -f        # follow logs
sudo systemctl restart epaper-frame       # restart
sudo systemctl status epaper-frame        # check status
curl -X POST http://epaper-frame.local/next  # force next photo
```
