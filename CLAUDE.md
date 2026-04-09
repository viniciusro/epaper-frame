# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

13.3" 6-color e-Paper digital photo frame running on Raspberry Pi Zero 2W. The display is a Waveshare Spectra 6 (1200×1600px, 6-color: black, white, red, green, blue, yellow). The project is fully implemented and running in production — see `IMPLEMENTATION_PLAN.md` for complete history.

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
sudo journalctl -u epaper-frame -f        # follow logs (also available in web UI)
ssh pi@epaper-frame.local "cd epaper-frame && git pull && sudo systemctl restart epaper-frame"
```

## Architecture

### Execution Flow
`main.py` → `FrameController.run()` → three threads:
- **info-refresh** (daemon): polls weather/transit/pi_stats every 30s, pushes to `web.app._state`
- **flask** (daemon): serves web UI on port 80 (HTTPS if cert present)
- **telegram-bot** (daemon): asyncio event loop, polls Telegram API
- **main thread**: `_display_loop()` → sleep check → `_do_display_cycle()` → wait for interval or `next_photo_event`

### Core Modules (`core/`)
- **`frame_controller.py`** — orchestrates all components; `_build_sources()` enforces exclusive source modes (NGA → Nextcloud → Local+Upload); `_increment_refresh_count()` tracks lifetime refreshes; crash handler sends Telegram alert
- **`shuffler.py`** — SQLite history DB at `data/history.db`; enforces `no_repeat_days`; upload always first, then NGA, then Nextcloud, then local
- **`renderer.py`** — load → EXIF rotate → GPS extract → fit (cover-crop 1200×1600) → enhance (contrast×1.5, saturation×2, sharpness×1.5) → auto text color detection → compose strip → return RGB; `_auto_text_color()` measures bottom 150px luminance
- **`display.py`** — wraps Waveshare driver; `EPAPER_MOCK=1` saves PNG to temp dir; `clear()` blanks to white

### Photo Sources (`sources/`)
All implement `PhotoSource` ABC: `list_photos()` → `[Path]`, `sync()` → new count.
- **`local.py`** — recursive scan of configured folder
- **`nextcloud.py`** — WebDAV sync via `webdavclient3`; ETag-based incremental; cache eviction to `cache_size` limit
- **`upload.py`** — PIL-validated uploads saved to local folder path
- **`nga.py`** — NGA IIIF API; random public-domain artworks; caches to `data/cache/nga/`

### Info Fetchers (`info/`)
Each has `fetch()` with in-memory TTL cache.
- **`weather.py`** — OpenWeatherMap `/weather`; returns `{temp, condition, city, lat, lon, updated}`
- **`transit.py`** — MVG API; filters by `label == line` AND destination contains `direction_filter`; returns `[{time, delay, destination}]`
- **`pi_stats.py`** — `{ip, cpu_temp, cpu_load, disk_used_pct, hostname, updated}`
- **`air_quality.py`** — OpenWeatherMap Air Pollution API using lat/lon from weather; returns `{aqi, label}`
- **`telegram_bot.py`** — python-telegram-bot v21; async lifecycle in daemon thread via `asyncio.run()` + manual `async with app`; `send_alert()` uses plain HTTP POST; `_last_chat_id` persisted to `data/telegram_chat_id.txt`

### Web UI (`web/`)
Flask app. Routes: `/` status, `/config`, `/upload`, `/next`, `/preview`, `/gallery`, `/thumb/<path:filename>`, `/delete/<path:filename>`, `/logs`, `/api/logs`, `/api/status`, `/api/transit/directions`, `/reboot`, `/restart`.

Strip data dict passed to renderer: `{weather, transit, pi, air, strip_cfg, location}`.

### Drivers (`drivers/`)
Waveshare vendor code — do not modify. `epd13in3E.py` → `EPD` class: `Init()`, `display(buf)`, `getbuffer(image)`, `sleep()`. `DEV_Config_*.so` are pre-built ARM binaries excluded from git.

## Key Behaviours

**Source mode priority** (enforced in both `_build_sources` and `shuffler.next()`):
1. Upload — always jumps queue in every mode
2. NGA enabled → only NGA
3. Nextcloud enabled → only Nextcloud
4. Neither → local folder + upload

**Sleep schedule**: `_in_sleep_window()` handles midnight-crossing; `display.clear()` on entry; inner poll loop breaks immediately if `next_photo_event` is set (Wake Up button).

**Full paths required**: systemd service runs with restricted PATH — always use `/usr/bin/sudo`, `/usr/bin/journalctl`, `/sbin/reboot`, `/usr/bin/systemctl` in subprocess calls.

**Strip text color**: `strip_text_color: auto` in config → `_auto_text_color()` in renderer picks black or white per photo. Other valid values: `#ffffff`, `#000000`, any hex.

## Configuration

`config.yaml` (never committed — copy from `config.yaml.example`). All settings live-reloadable from web UI. Key fields:
- `display.interval_minutes`, `no_repeat_days`, `sleep_start`, `sleep_end`, `strip_text_color`
- `display.strip.*` — per-element boolean toggles
- `sources.nextcloud.cache_size` — max cached files (evicts oldest)
- `weather.api_key` — used for both weather and AQI
- `transit.mvg_global_id`, `line`, `direction_filter`
- `telegram.bot_token`

## Display Constraints

- Resolution: 1200×1600px portrait only
- 6-color palette: black `#000000`, white `#ffffff`, yellow `#ffff00`, red `#ff0000`, blue `#0000ff`, green `#00ff00`
- Palette slot 4 unused (keep as black) — driver ordering requirement
- Bottom 150px = info strip; photo area 1200×1450
- Full refresh ~30 seconds; rated 1,000,000 refreshes

## Systemd Service (Pi)

```ini
# /etc/systemd/system/epaper-frame.service
WorkingDirectory=/home/pi/epaper-frame
ExecStart=/home/pi/epaper-frame/venv/bin/python main.py
Restart=always
RestartSec=10
```

Sudoers (`/etc/sudoers.d/epaper-reboot`):
```
pi ALL=(ALL) NOPASSWD: /sbin/reboot
pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart epaper-frame
```
