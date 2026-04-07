import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import web.app as webapp
from core.display import Display
from core.renderer import Renderer
from core.shuffler import Shuffler
from info.pi_stats import PiStats
from info.transit import TransitFetcher
from info.weather import WeatherFetcher
from sources.local import LocalFolderSource
from sources.nextcloud import NextcloudSource
from sources.upload import UploadSource

logger = logging.getLogger(__name__)

_INFO_REFRESH_INTERVAL = 30  # seconds between info polling loops


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

        # Wiring: use the event already in web.app so POST /next wakes us
        self._next_event = webapp.next_photo_event

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

        # Block here
        self._display_loop()

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
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

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
                webapp.update_state(weather=weather, transit=transit, pi=pi)
                logger.debug('Info refreshed')
            except Exception:
                logger.exception('Info refresh error')

            if (datetime.now() - self._last_display_at).total_seconds() >= 86400:
                logger.warning('24h watchdog: no display refresh in 24h, forcing update')
                self._next_event.set()

            time.sleep(_INFO_REFRESH_INTERVAL)

    def _display_loop(self):
        """Main display loop — runs forever in the calling thread."""
        logger.info('Display loop started (interval=%ds)', self._interval)
        while True:
            try:
                self._do_display_cycle()
            except Exception:
                logger.exception('Display cycle failed — will retry next interval')

            next_at = datetime.now() + timedelta(seconds=self._interval)
            webapp.update_state(
                status='idle',
                next_update_at=next_at,
            )

            logger.info('Sleeping %ds (next at %s)', self._interval, next_at.strftime('%H:%M:%S'))
            woken = self._next_event.wait(timeout=self._interval)
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
        for source in self._sources:
            if hasattr(source, 'sync') and source.name == 'nextcloud':
                try:
                    n = source.sync()
                    if n:
                        logger.info('Nextcloud: synced %d new photos', n)
                except Exception:
                    logger.warning('Nextcloud sync failed', exc_info=True)

        # Collect latest info snapshot
        with webapp._state_lock:
            strip_data = {
                'weather': webapp._state.get('weather'),
                'transit': webapp._state.get('transit', []),
                'pi': webapp._state.get('pi', {}),
            }

        # Select + render
        photo_path = self._shuffler.next()
        logger.info('Selected photo: %s', photo_path)

        live_cfg = webapp._load_config()
        hex_color = live_cfg.get('display', {}).get('strip_text_color', '#ffffff')
        strip_fg = _hex_to_rgb(hex_color)
        rendered = self._renderer.render(photo_path, strip_data, strip_fg=strip_fg)

        # Push to display
        webapp.update_state(status='refreshing', last_photo=str(photo_path))
        logger.info('Pushing to display')
        self._display.show(rendered)

        self._last_display_at = datetime.now()
        logger.info('Display cycle complete')

    # ------------------------------------------------------------------ #
    # Source factory                                                       #
    # ------------------------------------------------------------------ #

    def _build_sources(self):
        sources_cfg = self.config.get('sources', {})
        sources = []

        local_cfg = sources_cfg.get('local_folder', {})
        if local_cfg.get('enabled', True):
            sources.append(LocalFolderSource(local_cfg))
            logger.info('Source enabled: local (%s)', local_cfg.get('path', ''))

        upload_cfg = sources_cfg.get('upload', {})
        if upload_cfg.get('enabled', True):
            # Upload saves into the same local_folder path
            upload_cfg = dict(upload_cfg)
            upload_cfg.setdefault('path', local_cfg.get('path', 'data/uploads'))
            sources.append(UploadSource(upload_cfg))
            logger.info('Source enabled: upload')

        nextcloud_cfg = sources_cfg.get('nextcloud', {})
        if nextcloud_cfg.get('enabled', False):
            sources.append(NextcloudSource(nextcloud_cfg))
            logger.info('Source enabled: nextcloud')

        if not sources:
            logger.warning('No photo sources enabled')

        return sources
