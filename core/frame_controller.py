import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import web.app as webapp
from core.display import Display
from core.renderer import Renderer
from core.shuffler import Shuffler
from info.air_quality import AirQualityFetcher
from info.pi_stats import PiStats
from info.telegram_bot import TelegramBot
from info.transit import TransitFetcher
from info.weather import WeatherFetcher
from sources.local import LocalFolderSource
from sources.nextcloud import NextcloudSource
from sources.nga import NGASource
from sources.upload import UploadSource

logger = logging.getLogger(__name__)

_INFO_REFRESH_INTERVAL = 30  # seconds between info polling loops


def _in_sleep_window(sleep_start: str, sleep_end: str) -> bool:
    """Return True if current local time is within the [sleep_start, sleep_end) window.
    Handles midnight-crossing ranges (e.g. 23:00 → 07:00)."""
    from datetime import time as dtime
    now = datetime.now().time()
    start = dtime(*map(int, sleep_start.split(':')))
    end   = dtime(*map(int, sleep_end.split(':')))
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class FrameController:
    def __init__(self, config):
        self.config = config
        self._display_cfg = config.get('display', {})
        self._interval = self._display_cfg.get('interval_minutes', 60) * 60  # seconds

        # Photo sources
        self._sources = self._build_sources()

        # Core components
        self._shuffler = Shuffler(config, self._sources)
        self._renderer = Renderer()
        self._display = Display()

        # Info fetchers
        self._weather = WeatherFetcher(config.get('weather', {}))
        self._transit = TransitFetcher(config.get('transit', {}))
        self._pi_stats = PiStats()
        self._air_quality = AirQualityFetcher(config.get('weather', {}))

        # Wiring: use the event already in web.app so POST /next wakes us
        self._next_event = webapp.next_photo_event

        # Telegram bot (no-op if token not configured)
        upload_folder = Path(
            webapp._load_config().get('sources', {}).get('local_folder', {}).get('path', 'data/uploads')
        )
        self._telegram = TelegramBot(config.get('telegram', {}), upload_folder, self._next_event)

        # Watchdog: track last successful display time for 24h forced refresh
        self._last_display_at = datetime.now()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        """Start all threads and block on the display loop."""
        logger.info('FrameController starting')

        # Daemon threads — die when main thread exits
        threading.Thread(target=self._info_refresh_loop, daemon=True, name='info-refresh').start()
        self._start_web_thread()
        self._telegram.start()

        # Block here — catch crash and alert via Telegram before re-raising
        try:
            self._display_loop()
        except Exception:
            logger.exception('Display loop crashed')
            self._telegram.send_alert('❌ epaper-frame: display loop crashed — service will restart.')
            raise

    def trigger_next(self):
        """Skip the current sleep and advance to the next photo immediately."""
        self._next_event.set()

    # ------------------------------------------------------------------ #
    # Threads                                                              #
    # ------------------------------------------------------------------ #

    def _start_web_thread(self):
        cfg = self.config
        port = cfg.get('web', {}).get('port', 5000)

        def _run():
            import logging as _logging
            _logging.getLogger('werkzeug').setLevel(_logging.WARNING)
            app = webapp.create_app(cfg)
            ssl_context = webapp.ssl_context()
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False,
                    ssl_context=ssl_context)

        t = threading.Thread(target=_run, daemon=True, name='flask')
        t.start()
        logger.info('Web UI started on port %d', port)

    def _info_refresh_loop(self):
        """Continuously refresh weather, transit, pi_stats and push to web state.
        Also fires the 24h watchdog if no display refresh has occurred in 24 hours."""
        while True:
            try:
                weather = self._weather.fetch()
                transit = self._transit.fetch()
                pi = self._pi_stats.fetch()
                air = None
                if weather and weather.get('lat') is not None:
                    air = self._air_quality.fetch(weather['lat'], weather['lon'])
                webapp.update_state(weather=weather, transit=transit, pi=pi, air=air)
                logger.debug('Info refreshed')
            except Exception:
                logger.exception('Info refresh error')

            if (datetime.now() - self._last_display_at).total_seconds() >= 86400:
                logger.warning('24h watchdog: no display refresh in 24h, forcing update')
                self._telegram.send_alert('⚠️ epaper-frame: no display refresh in 24h — forcing update now.')
                self._next_event.set()

            time.sleep(_INFO_REFRESH_INTERVAL)

    def _display_loop(self):
        """Main display loop — runs forever in the calling thread."""
        logger.info('Display loop started')

        # Give the info-refresh thread time to complete its first fetch
        # before the first display cycle so the strip has live data.
        logger.info('Waiting for first info fetch…')
        time.sleep(10)

        while True:
            live_cfg = webapp._load_config()
            sleep_start = live_cfg.get('display', {}).get('sleep_start', '')
            sleep_end   = live_cfg.get('display', {}).get('sleep_end', '')
            if sleep_start and sleep_end and _in_sleep_window(sleep_start, sleep_end):
                logger.info('Display sleeping until %s', sleep_end)
                webapp.update_state(status='sleeping', sleeping_until=sleep_end)
                self._display.clear()
                while _in_sleep_window(sleep_start, sleep_end):
                    self._next_event.wait(timeout=60)
                    self._next_event.clear()
                webapp.update_state(status='idle', sleeping_until=None)
                logger.info('Display waking up')
                continue  # skip to next iteration → run display cycle immediately

            try:
                self._do_display_cycle()
            except Exception:
                logger.exception('Display cycle failed — will retry next interval')

            interval = webapp._load_config().get('display', {}).get('interval_minutes', 60) * 60
            next_at = datetime.now() + timedelta(seconds=interval)
            webapp.update_state(
                status='idle',
                next_update_at=next_at,
            )

            logger.info('Sleeping %ds (next at %s)', interval, next_at.strftime('%H:%M:%S'))
            woken = self._next_event.wait(timeout=interval)
            if woken:
                logger.info('Woken early by /next trigger')
            self._next_event.clear()

    # ------------------------------------------------------------------ #
    # Display cycle                                                        #
    # ------------------------------------------------------------------ #

    def _do_display_cycle(self):
        webapp.update_state(status='rendering')
        logger.info('Display cycle starting')

        # Sync remote sources (non-blocking — errors logged, not raised)
        # Rebuild sources from live config so enabling a source in the UI
        # takes effect without restarting the service.
        self._sources = self._build_sources()
        self._shuffler.sources = self._sources

        for source in self._sources:
            if source.name in ('nextcloud', 'nga'):
                try:
                    n = source.sync()
                    if n:
                        logger.info('%s: synced %d new photos', source.name, n)
                except Exception:
                    logger.warning('%s sync failed', source.name, exc_info=True)

        # Collect latest info snapshot
        with webapp._state_lock:
            strip_data = {
                'weather': webapp._state.get('weather'),
                'transit': webapp._state.get('transit', []),
                'pi': webapp._state.get('pi', {}),
                'air': webapp._state.get('air'),
            }

        # Select + render
        photo_path = self._shuffler.next()
        logger.info('Selected photo: %s', photo_path)

        live_cfg = webapp._load_config()
        hex_color = live_cfg.get('display', {}).get('strip_text_color', 'auto')
        auto_color = (hex_color == 'auto')
        strip_fg = (255, 255, 255) if auto_color else _hex_to_rgb(hex_color)
        strip_data['strip_cfg'] = live_cfg.get('display', {}).get('strip', {})
        rendered = self._renderer.render(photo_path, strip_data, strip_fg=strip_fg, auto_color=auto_color)

        # Push to display
        webapp.update_state(status='refreshing', last_photo=str(photo_path))
        logger.info('Pushing to display')
        self._display.show(rendered)

        self._last_display_at = datetime.now()
        count = self._increment_refresh_count()
        logger.info('Display cycle complete (refresh #%d)', count)

    # ------------------------------------------------------------------ #
    # Refresh counter                                                      #
    # ------------------------------------------------------------------ #

    _REFRESH_COUNT_PATH = Path('data/refresh_count.txt')
    _REFRESH_MAX = 1_000_000

    def _increment_refresh_count(self) -> int:
        """Read, increment by 1, write back. Returns new count. Never raises."""
        try:
            path = self._REFRESH_COUNT_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            count = int(path.read_text().strip()) if path.exists() else 0
            count += 1
            path.write_text(str(count))
            pct = round(count / self._REFRESH_MAX * 100, 2)
            webapp.update_state(refresh_count=count, refresh_health_pct=pct)
            return count
        except Exception:
            logger.warning('Failed to update refresh count', exc_info=True)
            return 0

    # ------------------------------------------------------------------ #
    # Source factory                                                       #
    # ------------------------------------------------------------------ #

    def _build_sources(self):
        sources_cfg = webapp._load_config().get('sources', {})
        sources = []

        local_cfg = sources_cfg.get('local_folder', {})
        upload_cfg = sources_cfg.get('upload', {})
        nextcloud_cfg = sources_cfg.get('nextcloud', {})
        nga_cfg = sources_cfg.get('nga', {})

        nga_on       = nga_cfg.get('enabled', False)
        nextcloud_on = nextcloud_cfg.get('enabled', False)

        # Upload is always available (photos sent via Telegram or web UI
        # jump the queue in every mode).
        if upload_cfg.get('enabled', True):
            uc = dict(upload_cfg)
            uc.setdefault('path', local_cfg.get('path', 'data/uploads'))
            sources.append(UploadSource(uc))
            logger.info('Source enabled: upload')

        if nga_on:
            # NGA mode — only NGA (upload handled above)
            sources.append(NGASource(nga_cfg))
            logger.info('Source enabled: nga (National Gallery of Art) [exclusive]')

        elif nextcloud_on:
            # Nextcloud mode — only Nextcloud (upload handled above)
            sources.append(NextcloudSource(nextcloud_cfg))
            logger.info('Source enabled: nextcloud [exclusive]')

        else:
            # Local mode — local folder + upload (already added)
            if local_cfg.get('enabled', True):
                sources.append(LocalFolderSource(local_cfg))
                logger.info('Source enabled: local (%s)', local_cfg.get('path', ''))

        if not sources:
            logger.warning('No photo sources enabled')

        return sources
