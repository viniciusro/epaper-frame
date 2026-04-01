# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

13.3" 6-color e-Paper digital photo frame running on Raspberry Pi Zero 2W. The display is a Waveshare Spectra 6 (1200×1600px, 4-bit color: black, white, red, green, blue, yellow). Most of the codebase is still stub/skeleton — see `IMPLEMENTATION_PLAN.md` for what's done and what's next.

## Commands

```bash
# Run tests
pytest

# Run a single test file
pytest tests/test_renderer.py

# Run locally with mock display (no hardware needed)
EPAPER_MOCK=1 python main.py

# Deploy to Pi (from Git Bash on Windows)
./deploy.sh
# Override defaults: PI_HOST=192.168.1.x PI_USER=pi ./deploy.sh

# Install dev dependencies
pip install -r requirements.txt -r requirements-dev.txt
```

On the Pi:
```bash
sudo journalctl -u epaper-frame -f   # service logs
curl -X POST http://epaper-frame.local/next  # force next photo
```

## Architecture

### Execution Flow
`main.py` → `FrameController.run()` → loop: fetch info → `Shuffler.next()` → `Renderer.render()` → `Display.show()`

### Core Modules (`core/`)
- **`frame_controller.py`** — main daemon loop; orchestrates all other components; weather/transit refresh runs on background threads (not yet implemented)
- **`shuffler.py`** — selects next photo using SQLite history DB, enforces `no_repeat_days` window, weighted-random across sources (not yet implemented)
- **`renderer.py`** — takes a PIL Image + strip data dict → returns 1200×1600 PIL Image; quantizes to 6-color palette with Floyd-Steinberg dithering; bottom 150px is an info strip (not yet implemented)
- **`display.py`** — wraps the Waveshare driver; set `EPAPER_MOCK=1` to save PNG instead of driving SPI

### Photo Sources (`sources/`)
All implement the `PhotoSource` ABC (`base.py`): `list_photos()` → `[Path]`, `sync()` → new count.
- **`local.py`** — reads a local folder path
- **`nextcloud.py`** — WebDAV sync via `webdavclient3`, caches to `data/cache/nextcloud/`
- **`upload.py`** — accepts files from the Flask upload endpoint, saves to local folder

### Info Fetchers (`info/`)
Each has a `fetch()` method returning a structured dict with in-memory caching.
- **`weather.py`** — OpenWeatherMap API; returns `{temp, condition, city, updated}`
- **`transit.py`** — MVG API for S-Bahn departures; filters by line + direction; returns `[{time, delay}]`
- **`pi_stats.py`** — reads local socket/sysfs; returns `{ip, cpu_temp, hostname}`

### Web UI (`web/`)
Flask app on port 80 (configurable). Routes: `/` status, `/config` editor, `/upload`, `/next`, `/preview`.

### Drivers (`drivers/`)
Waveshare vendor code — do not modify. `epd13in3E.py` has the `EPD` class with `Init()`, `display(buf)`, `getbuffer(image)`, `sleep()`. The `getbuffer()` method handles palette quantization and packs two 4-bit pixels per byte. `DEV_Config_*.so` are pre-built ARM binaries (excluded from git tracking).

## Configuration

Copy `config.yaml.example` → `config.yaml` (never committed). Key fields:
- `display.interval_minutes` — how often to change photo
- `display.no_repeat_days` — repeat prevention window
- `sources.nextcloud` — WebDAV credentials
- `weather.api_key` — OpenWeatherMap key
- `transit.mvg_global_id` / `transit.direction_filter` — MVG stop + direction

## Display Constraints

- Resolution: 1200×1600px (portrait only)
- Color palette: exactly 6 colors — black `#000000`, white `#ffffff`, yellow `#ffff00`, red `#ff0000`, blue `#0000ff`, green `#00ff00`
- Palette slot 4 is unused (keep as black) due to driver palette ordering
- Bottom 150px reserved for info strip; photo area is 1200×1450
- Full refresh takes ~30 seconds — not suitable for animations

## Systemd Service (Pi)

```ini
# /etc/systemd/system/epaper-frame.service
WorkingDirectory=/home/pi/epaper-frame
ExecStart=/home/pi/epaper-frame/venv/bin/python main.py
```
