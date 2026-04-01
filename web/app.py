import logging
import os
import tempfile
import threading
from pathlib import Path

import yaml
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path('config.yaml')

# Shared state — written by controller, read by web UI
_state = {
    'last_photo': None,       # Path or None
    'next_update_at': None,   # datetime or None
    'weather': None,
    'transit': [],
    'pi': {},
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


def create_app(config=None):
    app = Flask(__name__, template_folder='templates')

    if config is None:
        config = _load_config()

    app.secret_key = config.get('web', {}).get('secret_key') or os.urandom(24)

    upload_folder = Path(
        config.get('sources', {}).get('local_folder', {}).get('path', 'data/uploads')
    )

    # ------------------------------------------------------------------ #
    # Routes                                                               #
    # ------------------------------------------------------------------ #

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
            weather=state.get('weather'),
            transit=state.get('transit', []),
            pi=state.get('pi', {}),
            config=cfg,
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
        cfg['sources']['nextcloud']['url'] = f.get('nextcloud_url', '')
        cfg['sources']['nextcloud']['username'] = f.get('nextcloud_username', '')
        if f.get('nextcloud_password'):
            cfg['sources']['nextcloud']['password'] = f.get('nextcloud_password')
        cfg['sources']['nextcloud']['remote_path'] = f.get('nextcloud_remote_path', '/Photos/frame')
        cfg['sources']['nextcloud']['sync_interval_minutes'] = int(f.get('nextcloud_sync_interval', 30))

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

    @app.get('/preview')
    def preview():
        preview_path = Path(tempfile.gettempdir()) / 'epaper_preview.png'
        if not preview_path.exists():
            return 'No preview available', 404
        return send_file(str(preview_path), mimetype='image/png')

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
            'weather': state.get('weather'),
            'transit': state.get('transit', []),
            'pi': state.get('pi', {}),
        })

    return app


# Stand-alone dev server
if __name__ == '__main__':
    cfg = _load_config()
    port = cfg.get('web', {}).get('port', 5000)
    create_app(cfg).run(host='0.0.0.0', port=port, debug=True)
