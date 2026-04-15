import logging
import os
import tempfile
import threading
from pathlib import Path

import yaml
from flask import Flask, jsonify, make_response, redirect, render_template, request, send_file, send_from_directory, url_for

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path('config.yaml')

_REFRESH_COUNT_PATH = Path('data/refresh_count.txt')
_REFRESH_MAX = 1_000_000


def _load_refresh_count():
    try:
        return int(_REFRESH_COUNT_PATH.read_text().strip()) if _REFRESH_COUNT_PATH.exists() else 0
    except Exception:
        return 0


# Shared state — written by controller, read by web UI
_state = {
    'last_photo': None,           # Path or None
    'next_update_at': None,       # datetime or None
    'last_refresh': None,         # datetime or None
    'status': 'idle',             # idle | rendering | refreshing | sleeping
    'weather': None,
    'transit': [],
    'pi': {},
    'air': None,
    'sleeping_until': None,       # HH:MM string or None
    'refresh_count': _load_refresh_count(),
    'refresh_health_pct': round(_load_refresh_count() / _REFRESH_MAX * 100, 2),
}
_state_lock = threading.Lock()

# Event polled by FrameController to advance the photo immediately
next_photo_event = threading.Event()


def _load_config():
    if _CONFIG_PATH.exists():
        return yaml.safe_load(_CONFIG_PATH.read_text())
    return {}


def update_state(**kwargs):
    """Called by FrameController to push current info into web state."""
    with _state_lock:
        _state.update(kwargs)


_CERT_FILE = Path('data/ssl/cert.pem')
_KEY_FILE  = Path('data/ssl/key.pem')


def ssl_context():
    """Return (cert, key) tuple if cert files exist, else None (plain HTTP)."""
    if _CERT_FILE.exists() and _KEY_FILE.exists():
        return (str(_CERT_FILE), str(_KEY_FILE))
    return None


def create_app(config=None):
    app = Flask(__name__, template_folder='templates')

    if config is None:
        config = _load_config()

    app.secret_key = config.get('web', {}).get('secret_key') or os.urandom(24)

    upload_folder = Path('data/uploads')

    # ------------------------------------------------------------------ #
    # Routes                                                               #
    # ------------------------------------------------------------------ #

    @app.get('/service-worker.js')
    def service_worker():
        response = make_response(
            send_from_directory(app.static_folder, 'service-worker.js')
        )
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache'
        return response

    @app.get('/')
    def index():
        with _state_lock:
            state = dict(_state)
        cfg = _load_config()

        next_in = None
        if state.get('next_update_at'):
            from datetime import datetime
            delta = state['next_update_at'] - datetime.now()
            next_in = max(0, int(delta.total_seconds()))

        return render_template(
            'index.html',
            last_photo=Path(state['last_photo']).name if state['last_photo'] else None,
            next_in=next_in,
            status=state.get('status', 'idle'),
            sleeping_until=state.get('sleeping_until'),
            weather=state.get('weather'),
            air=state.get('air'),
            transit=state.get('transit', []),
            pi=state.get('pi', {}),
            config=cfg,
            refresh_count=state.get('refresh_count', 0),
            refresh_health_pct=state.get('refresh_health_pct', 0.0),
        )

    @app.get('/config')
    def config_get():
        cfg = _load_config()
        return render_template('config.html', config=cfg)

    @app.post('/config')
    def config_post():
        cfg = _load_config()
        f = request.form

        cfg.setdefault('display', {})
        cfg['display']['interval_minutes'] = int(f.get('interval_minutes', 60))
        cfg['display']['no_repeat_days'] = int(f.get('no_repeat_days', 7))
        color_mode = f.get('strip_text_color_mode', 'auto')
        cfg['display']['strip_text_color'] = (
            f.get('strip_text_color', '#ffffff') if color_mode == 'custom' else color_mode
        )
        cfg['display']['sleep_start'] = f.get('sleep_start', '').strip()
        cfg['display']['sleep_end'] = f.get('sleep_end', '').strip()
        cfg['display'].setdefault('strip', {})
        cfg['display']['strip']['enabled'] = 'strip_enabled' in f
        cfg['display']['strip']['weather'] = 'strip_weather' in f
        cfg['display']['strip']['transit'] = 'strip_transit' in f
        cfg['display']['strip']['ip'] = 'strip_ip' in f
        cfg['display']['strip']['cpu_temp'] = 'strip_cpu_temp' in f
        cfg['display']['strip']['aqi'] = 'strip_aqi' in f
        cfg['display']['strip']['location'] = 'strip_location' in f

        cfg.setdefault('weather', {})
        cfg['weather']['api_key'] = f.get('weather_api_key', '')
        cfg['weather']['city'] = f.get('weather_city', 'Munich')
        cfg['weather']['country_code'] = f.get('weather_country_code', 'DE')
        cfg['weather']['units'] = f.get('weather_units', 'metric')
        cfg['weather']['refresh_interval_minutes'] = int(f.get('weather_refresh', 30))

        cfg.setdefault('transit', {})
        cfg['transit']['mvg_global_id'] = f.get('transit_global_id', 'de:09162:1740')
        cfg['transit']['line'] = f.get('transit_line', 'S8')
        cfg['transit']['direction_filter'] = f.get('transit_direction_filter', 'Marienplatz')
        cfg['transit']['limit'] = int(f.get('transit_limit', 2))
        cfg['transit']['refresh_interval_minutes'] = int(f.get('transit_refresh', 2))

        cfg.setdefault('sources', {}).setdefault('nextcloud', {})
        cfg['sources']['nextcloud']['enabled'] = f.get('nextcloud_enabled', 'false') == 'true'
        cfg['sources']['nextcloud']['url'] = f.get('nextcloud_url', '')
        cfg['sources']['nextcloud']['username'] = f.get('nextcloud_username', '')
        if f.get('nextcloud_password'):
            cfg['sources']['nextcloud']['password'] = f.get('nextcloud_password')
        cfg['sources']['nextcloud']['remote_path'] = f.get('nextcloud_remote_path', '/Photos/frame')
        cfg['sources']['nextcloud']['sync_interval_minutes'] = int(f.get('nextcloud_sync_interval', 30))
        cfg['sources']['nextcloud']['cache_size'] = int(f.get('nextcloud_cache_size', 50))

        cfg['sources'].setdefault('nga', {})
        cfg['sources']['nga']['enabled'] = f.get('nga_enabled', 'false') == 'true'
        cfg['sources']['nga']['cache_size'] = int(f.get('nga_cache_size', 50))

        cfg.setdefault('telegram', {})
        cfg['telegram']['bot_token'] = f.get('telegram_bot_token', '')

        _CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
        return redirect(url_for('config_get'))

    @app.post('/upload')
    def upload():
        if 'photo' not in request.files:
            return 'No file', 400
        file = request.files['photo']
        if not file.filename:
            return 'No filename', 400
        from sources.upload import UploadSource
        src = UploadSource({'path': str(upload_folder)})
        try:
            src.save(file, destination_folder=upload_folder)
        except ValueError as exc:
            return str(exc), 400
        return redirect(url_for('index'))

    @app.post('/next')
    def next_photo():
        next_photo_event.set()
        return redirect(url_for('index'))

    @app.post('/restart')
    def restart_service():
        import subprocess
        subprocess.Popen(['/usr/bin/sudo', '/usr/bin/systemctl', 'restart', 'epaper-frame'])
        return '<p style="font-family:monospace;background:#111;color:#eee;padding:2rem">Restarting service… reconnect in ~10 seconds. <a href="/" style="color:#888">← Home</a></p>'

    @app.post('/reboot')
    def reboot():
        import subprocess
        subprocess.Popen(['/usr/bin/sudo', '/sbin/reboot'])
        return '<p style="font-family:monospace;background:#111;color:#eee;padding:2rem">Rebooting… reconnect in ~30 seconds. <a href="/" style="color:#888">← Home</a></p>'

    @app.get('/logs')
    def logs():
        return render_template('logs.html')

    @app.get('/api/logs')
    def api_logs():
        import subprocess as _sp
        try:
            result = _sp.run(
                ['/usr/bin/journalctl', '-u', 'epaper-frame', '-n', '200', '--no-pager', '--output=short-iso'],
                capture_output=True, text=True, timeout=10,
            )
            return jsonify({'lines': result.stdout.splitlines()})
        except Exception as exc:
            return jsonify({'lines': [], 'error': str(exc)})

    @app.get('/preview')
    def preview():
        preview_path = Path(tempfile.gettempdir()) / 'epaper_preview.png'
        if not preview_path.exists():
            return 'No preview available', 404
        return send_file(str(preview_path), mimetype='image/png')

    # ------------------------------------------------------------------ #
    # Photo gallery                                                        #
    # ------------------------------------------------------------------ #

    def _local_photo_paths():
        """Return deduplicated list of photos from local folder + uploads folder."""
        from sources.local import LocalFolderSource
        from sources.upload import UploadSource
        cfg = _load_config()
        sources_cfg = cfg.get('sources', {})
        local_path = sources_cfg.get('local_folder', {}).get('path', '/home/pi/photos')
        seen = set()
        photos = []
        for source in [LocalFolderSource({'path': local_path}), UploadSource({'path': 'data/uploads'})]:
            for p in source.list_photos():
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    photos.append(p)
        return sorted(photos, key=lambda p: p.name.lower())

    @app.get('/gallery')
    def gallery():
        photos = [{'filename': p.name, 'filepath': str(p)} for p in _local_photo_paths()]
        return render_template('gallery.html', photos=photos)

    @app.get('/thumb/<path:filename>')
    def thumb(filename):
        from werkzeug.utils import secure_filename as _secure
        from PIL import Image as _Image, ImageOps as _ImageOps
        safe = _secure(filename)
        if not safe:
            return 'Invalid filename', 400
        thumb_dir = (_CONFIG_PATH.parent / 'data/cache/thumbs').resolve()
        thumb_dir.mkdir(parents=True, exist_ok=True)
        cache_path = thumb_dir / safe
        if not cache_path.exists():
            original = next((p for p in _local_photo_paths() if p.name == safe), None)
            if original is None:
                return 'Not found', 404
            try:
                img = _Image.open(original)
                img = _ImageOps.exif_transpose(img)
                img.thumbnail((200, 150), _Image.LANCZOS)
                img = img.convert('RGB')
                img.save(str(cache_path), 'JPEG', quality=70)
            except Exception as exc:
                logger.warning('Thumbnail generation failed for %s: %s', safe, exc)
                return 'Error generating thumbnail', 500
        return send_file(str(cache_path), mimetype='image/jpeg')

    @app.post('/delete/<path:filename>')
    def delete_photo(filename):
        from werkzeug.utils import secure_filename as _secure
        safe = _secure(filename)
        if not safe:
            return 'Invalid filename', 400
        cfg = _load_config()
        local_root = Path(
            cfg.get('sources', {}).get('local_folder', {}).get('path', '/home/pi/photos')
        ).resolve()
        upload_root = Path('data/uploads').resolve()
        original = next((p for p in _local_photo_paths() if p.name == safe), None)
        if original is None:
            return redirect(url_for('gallery'))
        # Path traversal guard: only allow deletion within known source folders
        resolved = original.resolve()
        if not (resolved.is_relative_to(local_root) or resolved.is_relative_to(upload_root)):
            return 'Forbidden', 403
        try:
            original.unlink()
        except Exception as exc:
            logger.warning('Delete failed for %s: %s', safe, exc)
        # Remove cached thumbnail if present
        thumb = Path('data/cache/thumbs') / safe
        if thumb.exists():
            thumb.unlink(missing_ok=True)
        return redirect(url_for('gallery'))

    @app.get('/api/transit/directions')
    def api_transit_directions():
        """Return unique destinations for the configured stop+line from MVG live."""
        import requests as _requests
        cfg = _load_config()
        transit_cfg = cfg.get('transit', {})
        global_id = transit_cfg.get('mvg_global_id', 'de:09162:1740')
        line_filter = transit_cfg.get('line', 'S8')
        try:
            resp = _requests.get(
                'https://www.mvg.de/api/bgw-pt/v3/departures',
                params={'globalId': global_id, 'limit': 80, 'transportTypes': 'SBAHN'},
                headers={'Accept': 'application/json'},
                timeout=10,
            )
            resp.raise_for_status()
            departures = resp.json()
        except Exception as exc:
            return jsonify({'error': str(exc), 'directions': []}), 502
        directions = sorted({
            d.get('destination', '')
            for d in departures
            if d.get('label', '') == line_filter and d.get('destination')
        })
        return jsonify({'directions': directions})

    @app.get('/api/status')
    def api_status():
        with _state_lock:
            state = dict(_state)
        next_in = None
        if state.get('next_update_at'):
            from datetime import datetime
            delta = state['next_update_at'] - datetime.now()
            next_in = max(0, int(delta.total_seconds()))
        return jsonify({
            'last_photo': str(state['last_photo']) if state['last_photo'] else None,
            'next_update_in_seconds': next_in,
            'status': state.get('status', 'idle'),
            'weather': state.get('weather'),
            'transit': state.get('transit', []),
            'pi': state.get('pi', {}),
        })

    return app


# Stand-alone dev server
if __name__ == '__main__':
    cfg = _load_config()
    port = cfg.get('web', {}).get('port', 5000)
    create_app(cfg).run(host='0.0.0.0', port=port, debug=True, ssl_context=ssl_context())
