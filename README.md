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

### 2. Install the systemd service

```bash
sudo cp deployment/epaper-frame.service /etc/systemd/system/
sudo systemctl enable epaper-frame
sudo systemctl start epaper-frame
```

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
| `sources.local_folder.path` | Path to local photo folder |
| `sources.nextcloud.*` | WebDAV credentials for Nextcloud sync |
| `sources.nga.enabled` | Enable National Gallery of Art collection |
| `sources.nga.cache_size` | Number of NGA artworks to keep on disk (default: 50) |
| `weather.api_key` | OpenWeatherMap API key |
| `weather.city` | City name for weather |
| `transit.mvg_global_id` | MVG stop identifier |
| `transit.direction_filter` | Filter departures by destination |
| `web.port` | Web UI port (default: 80) |

Most settings can be changed live from the web UI at `http://epaper-frame.local` without restarting the service.

## Web UI

Access at `http://epaper-frame.local` (or by IP).

- **Status page** — current photo, countdown to next refresh, weather, S-Bahn departures, Pi stats
- **Preview** — PNG of what's currently on the display
- **Next Photo** — skip to next photo immediately
- **Upload** — add a photo directly from the browser
- **Config** — edit all settings including strip text color picker and photo source selection

## Photo sources

| Source | Description | Priority |
|--------|-------------|----------|
| **Upload** | Photos added via the web UI upload form | Highest — always shown next |
| **National Gallery of Art** | ~50k open-access public domain artworks, downloaded automatically via IIIF API | High — exclusive when enabled |
| **Local folder** | Photos from a folder on the Pi (default: `/home/pi/photos`) | Normal |
| **Nextcloud** | Synced from a WebDAV/Nextcloud server | Normal |

When NGA is enabled it takes over the display exclusively — disable it in Config to return to personal photos. Uploaded photos always jump to the front of the queue regardless of which other sources are active.

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
