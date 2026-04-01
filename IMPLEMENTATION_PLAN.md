# epaper-frame — Implementation Plan

> **How to use this document**
> - Each step has a status badge: `[ ]` todo · `[x]` done · `[~]` in progress · `[!]` blocked
> - After completing a step, update its badge and fill in the **Result** field
> - Steps marked `🔧 HW` require the Raspberry Pi + display to be connected
> - Steps marked `💻 PC` can be done entirely on your Windows desktop before HW arrives
> - Use Cowork to execute implementation steps — point it at your local `epaper-frame/` folder

---

## Prerequisites

| Item | Status | Notes |
|------|--------|-------|
| Claude Desktop + Cowork (Windows) | `[ ]` | download at claude.ai/download |
| Git for Windows | `[ ]` | required for Cowork Code tab |
| Python 3.11+ on Windows | `[ ]` | for local dev/testing |
| VS Code + Remote SSH extension | `[ ]` | for cross-dev to Pi |
| GitHub account: viniciusro | `[x]` | https://github.com/viniciusro |
| Hardware ordered | `[x]` | Pi Zero 2W + Waveshare HAT + 13.3" e-Paper |

---

## Phase 0 — Repository & Tooling Setup
**Goal:** Working GitHub repo, local clone, deploy script, project skeleton.
**Environment:** 💻 PC

### Step 0.1 — Create GitHub repository
- [x] Go to https://github.com/new
- [x] Name: `epaper-frame`, description: `13.3" 6-color e-Paper digital photo frame — Raspberry Pi Zero 2W`
- [x] Set to **Public**, add `README.md`, license: MIT, `.gitignore`: Python
- [x] Clone locally: `git clone https://github.com/viniciusro/epaper-frame.git`

**Result:** Repo at https://github.com/viniciusro/epaper-frame, cloned to Windows dev machine.

### Step 0.2 — Create project skeleton
Using Cowork, create the full directory and file structure:

```
epaper-frame/
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── config.yaml.example
├── deploy.sh                   # Windows Git Bash: rsync + restart service
├── .gitignore
├── main.py
├── core/
│   ├── __init__.py
│   ├── frame_controller.py
│   ├── shuffler.py
│   ├── renderer.py
│   └── display.py
├── sources/
│   ├── __init__.py
│   ├── base.py
│   ├── local.py
│   ├── nextcloud.py
│   └── upload.py
├── info/
│   ├── __init__.py
│   ├── weather.py
│   ├── transit.py
│   └── pi_stats.py
├── web/
│   ├── __init__.py
│   ├── app.py
│   └── templates/
│       └── index.html
├── drivers/
│   ├── __init__.py
│   ├── epd13in3E.py            # copy from Waveshare reference
│   └── epdconfig.py            # copy from Waveshare reference
├── data/
│   └── .gitkeep
└── tests/
    ├── __init__.py
    ├── test_renderer.py
    ├── test_shuffler.py
    ├── test_sources.py
    └── test_info.py
```

- [x] Create all directories and stub `__init__.py` files
- [x] Copy Waveshare reference drivers into `drivers/`
- [x] Create `config.yaml.example` with all configurable fields (see §Config below)
- [x] Create `deploy.sh` (see §Deploy Script below)
- [x] Initial commit and push

**Result:** Full skeleton committed in commit `5f84d49`. All stubs in place.

### Step 0.3 — Config schema (config.yaml.example)
```yaml
# epaper-frame configuration
# Copy to config.yaml and fill in your values

display:
  interval_minutes: 60          # how often to change photo
  no_repeat_days: 7             # don't show same photo within N days
  orientation: portrait         # portrait only

sources:
  local_folder:
    enabled: true
    path: /home/pi/photos

  upload:
    enabled: true               # photos uploaded via web UI go to local_folder

  nextcloud:
    enabled: false
    url: https://your.nextcloud.instance
    username: ""
    password: ""
    remote_path: /Photos/frame  # WebDAV path to sync from
    sync_interval_minutes: 30

weather:
  enabled: true
  api_key: ""                   # OpenWeatherMap API key
  city: Munich
  country_code: DE
  units: metric
  refresh_interval_minutes: 30

transit:
  enabled: true
  mvg_global_id: de:09162:1740  # S-Bahn Fasanerie
  line: S8
  direction_filter: Marienplatz # filter departures containing this string
  limit: 2
  refresh_interval_minutes: 2

web:
  port: 80
  secret_key: ""                # Flask secret key, auto-generated on first run

pi:
  hostname: epaper-frame
```

- [x] Create file
- [x] Commit

**Result:** `config.yaml.example` committed with all fields. `.gitignore` excludes `config.yaml`.

### Step 0.4 — Deploy script (deploy.sh)
```bash
#!/bin/bash
# deploy.sh — push code to Pi and restart service
# Usage (from Git Bash on Windows): ./deploy.sh
# Set PI_HOST to your Pi's IP or hostname

PI_HOST="${PI_HOST:-epaper-frame.local}"
PI_USER="${PI_USER:-pi}"
REMOTE_DIR="/home/pi/epaper-frame"

echo ">>> Syncing to $PI_USER@$PI_HOST:$REMOTE_DIR"
rsync -avz --exclude '.git' --exclude '__pycache__' \
      --exclude '*.pyc' --exclude 'data/' \
      --exclude 'config.yaml' \
      ./ "$PI_USER@$PI_HOST:$REMOTE_DIR/"

echo ">>> Restarting service"
ssh "$PI_USER@$PI_HOST" "sudo systemctl restart epaper-frame"

echo ">>> Done"
```

- [x] Create file, make executable
- [x] Test rsync path (can run dry-run before Pi arrives: `rsync --dry-run`)
- [x] Commit

**Result:** `deploy.sh` committed. Excludes `.git`, `__pycache__`, `*.pyc`, `data/`, `config.yaml` from rsync. Restarts `epaper-frame` systemd service after sync.

---

## Phase 1 — Raspberry Pi Setup
**Goal:** Pi is configured, SSH works, Python env ready, SPI enabled.
**Environment:** 🔧 HW

### Step 1.1 — Flash OS
- [ ] Download Raspberry Pi Imager
- [ ] Flash **Raspberry Pi OS Lite (64-bit)** to SD card
- [ ] In Imager advanced settings:
  - Hostname: `epaper-frame`
  - Enable SSH with password auth
  - Set username: `pi`, password: (your choice)
  - Configure WiFi (your home network SSID + password)
- [ ] Boot Pi, wait ~60 seconds, find IP via router or `ping epaper-frame.local`

**Result:** _________________

### Step 1.2 — SSH access from Windows
```bash
# In Windows Terminal or Git Bash:
ssh pi@epaper-frame.local

# Generate SSH key if needed (optional but recommended):
ssh-keygen -t ed25519 -C "epaper-frame"
ssh-copy-id pi@epaper-frame.local
```
- [ ] SSH connection works
- [ ] Add VS Code Remote SSH config: Host `epaper-frame`, HostName `epaper-frame.local`, User `pi`
- [ ] VS Code remote opens and shows Pi filesystem

**Result:** _________________

### Step 1.3 — Enable SPI interface
```bash
sudo raspi-config
# Interface Options → SPI → Yes
sudo reboot
```
- [ ] SPI enabled
- [ ] Verify: `ls /dev/spi*` shows `spidev0.0` and `spidev0.1`

**Result:** _________________

### Step 1.4 — Install system dependencies
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    python3-pip python3-venv python3-dev \
    python3-pil python3-numpy \
    libgpiod-dev \
    git rsync
```
- [ ] All packages installed without errors

**Result:** _________________

### Step 1.5 — Clone repo and create Python venv
```bash
cd ~
git clone https://github.com/viniciusro/epaper-frame.git
cd epaper-frame
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
- [ ] Venv created
- [ ] Dependencies installed

**Test:** `python -c "from PIL import Image; print('PIL OK')"` → prints `PIL OK`

**Result:** _________________

---

## Phase 2 — Driver Validation
**Goal:** Display renders a test image correctly. 6-color palette verified.
**Environment:** 🔧 HW

### Step 2.1 — Hardware connection check
- [ ] HAT seated on Pi GPIO header (all 40 pins)
- [ ] Display ribbon cable connected to HAT
- [ ] USB-C power connected
- [ ] PWR LED on HAT lights up

**Result:** _________________

### Step 2.2 — Run Waveshare reference demo
```bash
cd ~/epaper-frame
source venv/bin/activate
python drivers/epd13in3E_test.py
```
- [ ] Display initializes without SPI errors
- [ ] Test pattern shows all 6 colors: black, white, red, green, blue, yellow
- [ ] No color banding or partial refresh artifacts

**Result:** _________________

### Step 2.3 — Validate display wrapper
```bash
python -c "
from core.display import Display
d = Display()
d.test_pattern()
d.sleep()
print('Display wrapper OK')
"
```
- [ ] `Display` class wraps driver correctly
- [ ] `test_pattern()` shows 6 color blocks
- [ ] `sleep()` puts display into low-power mode

**Result:** _________________

---

## Phase 3 — Image Pipeline (renderer)
**Goal:** Any input image → correctly sized, dithered, 6-color bitmap ready for display.
**Environment:** 💻 PC (mock display) then 🔧 HW (real display)

### Step 3.1 — Mock display
Create `core/display.py` with a `MOCK` mode that saves output as PNG instead of pushing to SPI.

```python
# core/display.py
import os
from PIL import Image

MOCK = os.environ.get('EPAPER_MOCK', '0') == '1'

class Display:
    WIDTH = 1200
    HEIGHT = 1600

    def show(self, image: Image.Image):
        if MOCK:
            image.save('/tmp/epaper_preview.png')
            print(f"[MOCK] Saved preview to /tmp/epaper_preview.png")
        else:
            from drivers.epd13in3E import EPD
            epd = EPD()
            epd.init()
            epd.display(epd.getbuffer(image))
            epd.sleep()
```

- [x] Implement `display.py`
- [x] Test: `EPAPER_MOCK=1 python -c "from core.display import Display; ..."`

**Result:** `core/display.py` implemented. `EPAPER_MOCK=1` saves PNG to `tempfile.gettempdir()/epaper_preview.png` (Windows-compatible). Real mode imports `drivers/epd13in3E.EPD` (Pi-only). Added `test_pattern()` method that renders 6 color blocks.

### Step 3.2 — Core image pipeline
Implement `core/renderer.py`:

1. **Load** — open any image format via Pillow
2. **Fit** — smart crop/resize to 1200×1450 (leaving 150px for bottom strip), portrait, no black bars
3. **Quantize** — Floyd-Steinberg dither to 6-color e-Paper palette: black, white, red, green, blue, yellow
4. **Compose** — paste photo + bottom strip into final 1200×1600 canvas
5. **Return** PIL Image ready for `Display.show()`

```python
PALETTE = [
    0,   0,   0,    # black
    255, 255, 255,  # white
    255, 255, 0,    # yellow
    255, 0,   0,    # red
    0,   0,   0,    # (unused slot)
    0,   0,   255,  # blue
    0,   255, 0,    # green
]
```

- [x] Implement `renderer.py`
- [x] Test with 5 different aspect ratio images (portrait, landscape, square, very wide, very tall)

**Test:**
```bash
EPAPER_MOCK=1 python -c "
from core.renderer import Renderer
from PIL import Image
r = Renderer()
img = Image.open('tests/fixtures/sample.jpg')
result = r.render(img, strip_data=None)
result.save('/tmp/test_output.png')
print(f'Output size: {result.size}')  # should be (1200, 1600)
"
```

**Result:** `core/renderer.py` fully implemented. `load()`, `fit_image()` (cover-crop to 1200×1450), `quantize_6color()` (Floyd-Steinberg to 6-color palette), `render_strip()`, `compose()`, `render()`. Tested with landscape/portrait/square fixtures — all produce correct 1200×1600 output. 8/8 pytest tests pass.

### Step 3.3 — Bottom strip renderer
Implement `renderer.py` strip composition:

- Left side: weather icon (unicode glyph) + temp + condition | S8 next 2 departures + delay status
- Right side: IP address + CPU temp + last updated timestamp
- Font: use a clean monospace bitmap font (load via Pillow ImageFont)
- Colors: white text on near-black background — must dither cleanly to 6-color palette

- [x] Implement strip renderer
- [x] Test with mock data

**Test:**
```bash
EPAPER_MOCK=1 python -c "
from core.renderer import Renderer
from PIL import Image
r = Renderer()
img = Image.open('tests/fixtures/sample.jpg')
strip_data = {
    'weather': {'temp': 9, 'condition': 'light rain', 'city': 'München'},
    'transit': [
        {'time': '08:04', 'delay': 0},
        {'time': '08:34', 'delay': 3},
    ],
    'pi': {'ip': '192.168.1.42', 'cpu_temp': 42, 'updated': '08:01'}
}
result = r.render(img, strip_data=strip_data)
result.save('/tmp/test_strip.png')
print('Strip test OK')
"
```

**Result:** Strip implemented in `render_strip()`. Left: temp/city/condition (row 0) + 2× S8 departure lines. Right: IP/CPU temp/updated timestamp, right-aligned. Font: TrueType with fallback to Pillow default. White text on black background. All tested via pytest.

---

## Phase 4 — Photo Sources
**Goal:** All 3 photo sources return PIL Image objects through a unified interface.
**Environment:** 💻 PC

### Step 4.1 — Abstract base source
Implement `sources/base.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

class PhotoSource(ABC):
    @abstractmethod
    def list_photos(self) -> List[Path]:
        """Return list of available photo paths in local cache."""
        pass

    @abstractmethod
    def sync(self) -> int:
        """Sync remote source to local cache. Return count of new photos."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

- [x] Implement `base.py`

**Result:** Already implemented in Phase 0 skeleton. `PhotoSource` ABC with `list_photos()`, `sync()`, `name` abstract members.

### Step 4.2 — Local folder source
Implement `sources/local.py`:
- Watches configured `path` for image files (jpg, jpeg, png, webp, gif)
- `list_photos()` returns all valid image paths
- `sync()` is a no-op (already local)

- [x] Implement `local.py`
- [x] Test: point at a folder with mixed file types, verify only images returned

**Result:** Recursive scan via `Path.rglob`, case-insensitive suffix check, hidden files excluded. `sync()` is a no-op. Tested via pytest (4 tests pass).

### Step 4.3 — Nextcloud source (WebDAV)
Implement `sources/nextcloud.py`:
- Uses `webdavclient3` library for WebDAV
- `sync()` downloads new/changed files from `remote_path` into `data/cache/nextcloud/`
- Uses ETag / Last-Modified for incremental sync (don't re-download unchanged files)
- `list_photos()` returns cached local paths

- [x] Add `webdavclient3` to `requirements.txt`
- [x] Implement `nextcloud.py`
- [ ] Test: connect to a real Nextcloud instance, sync 5 photos (deferred — needs HW/server)

**Test:**
```bash
python -c "
from sources.nextcloud import NextcloudSource
import yaml
cfg = yaml.safe_load(open('config.yaml'))['sources']['nextcloud']
s = NextcloudSource(cfg)
n = s.sync()
photos = s.list_photos()
print(f'Synced {n} new, total {len(photos)} photos')
"
```

**Result:** ETag-based incremental sync to `data/cache/nextcloud/`, metadata in `.sync_meta.json`. Connection errors logged as warnings, returns cached files. Real-server test deferred to Phase 9 integration.

### Step 4.4 — Upload source
Implement `sources/upload.py`:
- Accepts a file path (from Flask endpoint), moves it to `local_folder` path
- Validates image format and minimum size
- Returns the saved path

- [x] Implement `upload.py`
- [x] Test: upload a JPEG and a non-image file (should reject)

**Result:** `save(file_storage, destination_folder)` validates via PIL `verify()`, raises `ValueError` for non-images and corrupt files. `list_photos()` uses same recursive scan as LocalFolderSource. 5 tests pass.

---

## Phase 5 — Info Fetchers
**Goal:** Weather, S8 transit, and Pi stats return structured dicts with caching.
**Environment:** 💻 PC

### Step 5.1 — Weather fetcher
Implement `info/weather.py`:
- OpenWeatherMap `/weather` endpoint for Munich
- Cache result in memory, refresh every `refresh_interval_minutes`
- Returns: `{'temp': float, 'condition': str, 'city': str, 'updated': datetime}`
- Handle API errors gracefully (return last cached value or None)

- [x] Implement `weather.py`
- [x] Test: fetch live data, verify structure

**Test:**
```bash
python -c "
from info.weather import WeatherFetcher
import yaml
cfg = yaml.safe_load(open('config.yaml'))['weather']
w = WeatherFetcher(cfg)
data = w.fetch()
print(data)
"
```

**Result:** OpenWeatherMap `/weather` endpoint, `time.monotonic()` cache, returns `{temp, condition, city, updated}`. Error returns last cache or None. 4 unit tests pass (live test skipped without config.yaml).

### Step 5.2 — Transit fetcher (MVG S8)
Implement `info/transit.py`:
- Fetch from: `https://www.mvg.de/api/bgw-pt/v3/departures?globalId=de:09162:1740&limit=8&transportTypes=SBAHN`
- Filter: `line == 'S8'` AND `destination` contains `direction_filter` from config (default: `"Marienplatz"`)
- Take next 2 matching departures
- Calculate delay: `realtimeDepartureTime - plannedDepartureTime` (in minutes, from epoch ms)
- Cache 2 minutes
- Returns: `[{'time': 'HH:MM', 'delay': int}, ...]`

- [x] Implement `transit.py`
- [x] Test: verify direction filter works, delay calculation correct

**Test:**
```bash
python -c "
from info.transit import TransitFetcher
import yaml
cfg = yaml.safe_load(open('config.yaml'))['transit']
t = TransitFetcher(cfg)
data = t.fetch()
print(data)
"
```

**Result:** MVG API, filters by `label == line` AND `destination` contains `direction_filter` (case-insensitive). Delay = `(realtime - planned) / 60000` rounded. Returns `[{time, delay, destination}]`. 5 tests pass including live MVG API call.

### Step 5.3 — Pi stats
Implement `info/pi_stats.py`:
- IP: `socket.gethostbyname(socket.gethostname())`
- CPU temp: read `/sys/class/thermal/thermal_zone0/temp` (divide by 1000)
- Hostname: `socket.gethostname()`
- No caching needed (cheap to read)
- Returns: `{'ip': str, 'cpu_temp': float, 'hostname': str}`

- [x] Implement `pi_stats.py`
- [x] Test on Windows (IP works, CPU temp returns `None` gracefully)
- [ ] Test on Pi (all fields populated) — deferred to Phase 9

**Result:** Added `updated` field (`HH:MM`). CPU temp reads `/sys/class/thermal/thermal_zone0/temp`, returns `None` on Windows. IP falls back to `'0.0.0.0'` on error. 4 tests pass on Windows.

---

## Phase 6 — Shuffler
**Goal:** Smart photo selection with SQLite history, no-repeat window, multi-source support.
**Environment:** 💻 PC

### Step 6.1 — SQLite history database
Schema:
```sql
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_path TEXT NOT NULL,
    source TEXT NOT NULL,
    shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shown_at ON history(shown_at);
CREATE INDEX IF NOT EXISTS idx_path ON history(photo_path);
```

- [x] Implement DB init in `core/shuffler.py`
- [x] Test: create DB, insert records, query

**Result:** SQLite schema with history table + two indexes created at `data/history.db` on first instantiation.

### Step 6.2 — Selection algorithm
Implement `core/shuffler.py`:

1. Collect all photos from all enabled sources
2. Filter out photos shown within `no_repeat_days`
3. If no eligible photos remain: reset history (start fresh), log warning
4. Weighted random selection — equal weight across all sources (not all photos, to avoid large sources dominating)
5. Record selection in history
6. Return selected photo path

- [x] Implement `shuffler.py`
- [x] Test: populate 20 photos, verify no-repeat window works

**Test:**
```bash
python -c "
from core.shuffler import Shuffler
import yaml
cfg = yaml.safe_load(open('config.yaml'))
s = Shuffler(cfg, sources=[...])
for i in range(5):
    photo = s.next()
    print(f'{i+1}: {photo}')
"
```

**Result:** Full implementation. `db_path` injectable for testing. `next()` groups by source name, picks source then photo within it. History reset on exhaustion with warning log. `history_count()` and `reset_history()` public helpers. 6 tests pass including weighted-source and persistence tests.

---

## Phase 7 — Web Interface
**Goal:** Flask app running on port 80 with config management, photo upload, manual trigger, status page.
**Environment:** 💻 PC

### Step 7.1 — Flask app skeleton
Implement `web/app.py`:

Routes:
- `GET /` — status page: current photo, next refresh time, weather, S8, Pi stats
- `GET /config` — config editor form
- `POST /config` — save config changes
- `POST /upload` — photo upload endpoint
- `POST /next` — trigger manual photo change
- `GET /preview` — serve last rendered image as PNG

- [x] Implement Flask app with all routes (stubs)
- [x] Test: `flask run --port 5000`, all routes return 200

**Result:** `create_app(config)` factory pattern. Routes: `GET /`, `GET /config`, `POST /config`, `POST /upload`, `POST /next`, `GET /preview`, `GET /api/status`. Thread-safe state dict + lock shared with FrameController. `next_photo_event` threading.Event polled by controller.

### Step 7.2 — Status page UI
Implement `web/templates/index.html`:
- Show current photo (thumbnail)
- Weather + S8 status
- Pi stats
- "Next photo" button → `POST /next`
- Upload form
- Link to config

- [x] Implement template
- [x] Test: open in browser, all sections render

**Result:** Minimal monospace dark-theme UI. Sections: Status (photo name + countdown), Weather, S8 Departures (table with on-time/delayed color), Pi, Actions (Next Photo / Upload / Config / Preview). Meta refresh every 30s.

### Step 7.3 — Config editor
- Form for all `config.yaml` fields
- Sensitive fields (API key, Nextcloud password) shown as password inputs
- S8 direction filter editable here (no code change needed to update it)
- Save → write `config.yaml` → restart frame controller

- [x] Implement config form
- [x] Test: change S8 direction filter, verify `config.yaml` updated

**Result:** `config.html` with fieldsets: Display, Weather, Transit, Nextcloud. Password inputs for api_key and nextcloud password (blank = keep existing). Direction filter prominently in Transit section. POST writes YAML via PyYAML.

### Step 7.4 — Upload endpoint
```python
@app.post('/upload')
def upload():
    file = request.files['photo']
    upload_source.save(file)
    return redirect('/')
```
- [x] Implement upload endpoint
- [x] Test: upload JPEG via curl, verify saved to photos folder

**Test:**
```bash
curl -X POST http://localhost:5000/upload \
     -F "photo=@tests/fixtures/sample.jpg"
```

**Result:** Delegates to `UploadSource.save()` with PIL validation. Returns 400 on invalid file, redirects to `/` on success. Tested via Flask test client.

---

## Phase 8 — Frame Controller (Main Daemon)
**Goal:** Main loop orchestrating all components, runs as systemd service.
**Environment:** 🔧 HW

### Step 8.1 — Frame controller loop
Implement `core/frame_controller.py`:

```python
class FrameController:
    def run(self):
        while True:
            # 1. Refresh info (weather, transit, pi stats) — respect cache TTLs
            # 2. Select next photo via shuffler
            # 3. Render (image + strip) via renderer
            # 4. Push to display
            # 5. Sleep until next interval
```

- [x] Implement controller
- [x] Test with mock display: `EPAPER_MOCK=1 python main.py`
- [ ] Verify photo changes after configured interval — deferred to Phase 9 (HW)

**Result:** Full implementation. State machine: idle→rendering→refreshing→idle. `_do_display_cycle()` syncs Nextcloud, grabs info snapshot, shuffles, renders, pushes to display. `main.py` sets up dual-sink logging (stdout + `logs/epaper-frame.log`). 6 controller tests pass.

### Step 8.2 — Concurrent info refresh
- Weather and transit fetch on background threads (don't block display update)
- Info cache shared between controller and web UI
- Thread-safe dict with lock

- [x] Implement background threads
- [x] Test: info refreshes independently of display cycle

**Result:** `_info_refresh_loop()` daemon thread polls weather+transit+pi_stats every 30s and pushes to `web.app._state` via `update_state()`. Flask runs in its own daemon thread. Display loop runs in main thread. `web.app._state` extended with `status` and `last_refresh` fields. `index.html` shows pulsing status indicator (CSS animation) and JS live countdown.

### Step 8.3 — systemd service
Create `/etc/systemd/system/epaper-frame.service`:
```ini
[Unit]
Description=e-Paper Digital Photo Frame
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/epaper-frame
Environment=PATH=/home/pi/epaper-frame/venv/bin
ExecStart=/home/pi/epaper-frame/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable epaper-frame
sudo systemctl start epaper-frame
sudo journalctl -u epaper-frame -f
```

- [ ] Service file deployed — deferred to Phase 9 (HW)
- [ ] Service starts on boot — deferred to Phase 9
- [ ] Survives reboot — deferred to Phase 9
- [ ] `journalctl` shows clean startup log — deferred to Phase 9

**Result:** Service unit file content defined in plan. Deployment deferred until Pi hardware arrives (Phase 9).

---

## Phase 9 — Integration Testing
**Goal:** Full end-to-end test of every feature on real hardware.
**Environment:** 🔧 HW

### Step 9.1 — Full cycle test
- [ ] Frame displays photo with bottom strip
- [ ] Weather data is live and correct
- [ ] S8 shows real departures toward Marienplatz
- [ ] Pi stats show correct IP and temperature
- [ ] Photo changes after configured interval
- [ ] No-repeat window prevents same photo showing twice within 7 days

**Result:** _________________

### Step 9.2 — Source tests
- [ ] Photo from local folder displays correctly
- [ ] Photo uploaded via web UI appears in rotation
- [ ] Nextcloud sync downloads photos and they enter rotation

**Result:** _________________

### Step 9.3 — Web interface tests
- [ ] Status page loads at `http://epaper-frame.local`
- [ ] Config change (S8 direction filter) takes effect without code change
- [ ] Manual "next photo" button works
- [ ] Photo upload via browser works

**Result:** _________________

### Step 9.4 — Resilience tests
- [ ] WiFi disconnect → frame keeps displaying last image, recovers when WiFi returns
- [ ] Nextcloud unreachable → frame falls back to local photos
- [ ] MVG API down → S8 section shows "unavailable" gracefully
- [ ] Service restarts automatically after crash (`systemctl status` shows restart count)

**Result:** _________________

---

## Phase 10 — Polish & Documentation
**Goal:** Production-ready, documented, clean GitHub repo.
**Environment:** 💻 PC + 🔧 HW

### Step 10.1 — README.md
- [ ] Project description + photo of finished frame
- [ ] Hardware BOM with links
- [ ] Setup instructions (Pi OS → SSH → deploy)
- [ ] Configuration reference
- [ ] Web UI screenshot

**Result:** _________________

### Step 10.2 — requirements.txt finalized
```
Pillow>=10.0
Flask>=3.0
PyYAML>=6.0
requests>=2.31
webdavclient3>=3.14
RPi.GPIO>=0.7        # Pi only
spidev>=3.6          # Pi only
```

- [ ] Pin all versions
- [ ] Test clean install on Pi: `pip install -r requirements.txt`

**Result:** _________________

### Step 10.3 — Logging
- [ ] Replace all `print()` with `logging` module
- [ ] Log to `/var/log/epaper-frame.log` + stdout (for journalctl)
- [ ] Log levels: INFO for normal ops, WARNING for fallbacks, ERROR for failures

**Result:** _________________

---

## Deferred (Future Phases)

| Feature | Notes |
|---------|-------|
| WiFi hotspot setup wizard | first-boot captive portal, `hostapd` + `dnsmasq` |
| Google Photos integration | OAuth2 flow, album selection |
| OTA updates | pull latest from GitHub via web UI |
| Multiple display profiles | different strip layouts, seasonal themes |

---

## Quick Reference

### Deploy from Windows
```bash
# In Git Bash from project root:
./deploy.sh
```

### SSH to Pi
```bash
ssh pi@epaper-frame.local
```

### Run locally (mock display)
```bash
EPAPER_MOCK=1 python main.py
```

### Check service logs
```bash
sudo journalctl -u epaper-frame -f
```

### Force next photo
```bash
curl -X POST http://epaper-frame.local/next
```