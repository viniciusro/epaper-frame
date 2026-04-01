import json
import time
import pytest
from unittest.mock import patch, MagicMock

from info.weather import WeatherFetcher
from info.transit import TransitFetcher
from info.pi_stats import PiStats

# ------------------------------------------------------------------ #
# WeatherFetcher                                                       #
# ------------------------------------------------------------------ #

_WEATHER_RESPONSE = {
    'main': {'temp': 9.3},
    'weather': [{'description': 'light rain'}],
    'name': 'München',
}


def _weather_cfg(api_key='testkey'):
    return {
        'api_key': api_key,
        'city': 'Munich',
        'country_code': 'DE',
        'units': 'metric',
        'refresh_interval_minutes': 30,
    }


def test_weather_fetch_returns_expected_shape():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch('info.weather.requests.get', return_value=mock_resp) as mock_get:
        fetcher = WeatherFetcher(_weather_cfg())
        result = fetcher.fetch()

    assert result is not None
    assert result['temp'] == 9
    assert result['condition'] == 'light rain'
    assert result['city'] == 'München'
    assert 'updated' in result
    mock_get.assert_called_once()


def test_weather_cache(monkeypatch):
    """Second fetch within TTL must not make a new HTTP request."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch('info.weather.requests.get', return_value=mock_resp) as mock_get:
        fetcher = WeatherFetcher(_weather_cfg())
        fetcher.fetch()  # first — hits network
        fetcher.fetch()  # second — should use cache

    assert mock_get.call_count == 1


def test_weather_returns_cache_on_error():
    """On network error after a successful fetch, return last cached value."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    fetcher = WeatherFetcher(_weather_cfg())
    with patch('info.weather.requests.get', return_value=mock_resp):
        first = fetcher.fetch()

    # Force cache expiry
    fetcher._cache_time = 0.0

    with patch('info.weather.requests.get', side_effect=Exception('network down')):
        second = fetcher.fetch()

    assert second == first


def test_weather_no_api_key_returns_none():
    fetcher = WeatherFetcher(_weather_cfg(api_key=''))
    result = fetcher.fetch()
    assert result is None


def test_weather_fetch_live():
    """Live test — skipped if config.yaml absent or key empty."""
    pytest.importorskip('yaml')
    import yaml
    from pathlib import Path
    cfg_path = Path('config.yaml')
    if not cfg_path.exists():
        pytest.skip('config.yaml not found')
    cfg = yaml.safe_load(cfg_path.read_text())
    api_key = cfg.get('weather', {}).get('api_key', '')
    if not api_key:
        pytest.skip('weather.api_key not set in config.yaml')

    fetcher = WeatherFetcher(cfg['weather'])
    result = fetcher.fetch()
    assert result is not None
    assert 'temp' in result


# ------------------------------------------------------------------ #
# TransitFetcher                                                       #
# ------------------------------------------------------------------ #

_NOW_MS = int(time.time() * 1000)

_TRANSIT_RESPONSE = [
    # Correct line, correct direction
    {
        'label': 'S8',
        'destination': 'München Marienplatz',
        'plannedDepartureTime': _NOW_MS + 4 * 60000,
        'realtimeDepartureTime': _NOW_MS + 4 * 60000,  # on time
    },
    # Correct line, wrong direction — must be filtered out
    {
        'label': 'S8',
        'destination': 'Flughafen München',
        'plannedDepartureTime': _NOW_MS + 6 * 60000,
        'realtimeDepartureTime': _NOW_MS + 6 * 60000,
    },
    # Correct line, correct direction, delayed
    {
        'label': 'S8',
        'destination': 'S+U Marienplatz',
        'plannedDepartureTime': _NOW_MS + 10 * 60000,
        'realtimeDepartureTime': _NOW_MS + 13 * 60000,  # +3 min
    },
    # Wrong line
    {
        'label': 'S1',
        'destination': 'Marienplatz',
        'plannedDepartureTime': _NOW_MS + 2 * 60000,
        'realtimeDepartureTime': _NOW_MS + 2 * 60000,
    },
]


def _transit_cfg():
    return {
        'mvg_global_id': 'de:09162:1740',
        'line': 'S8',
        'direction_filter': 'Marienplatz',
        'limit': 2,
        'refresh_interval_minutes': 2,
    }


def test_transit_direction_filter():
    """Only S8 toward Marienplatz returned; Flughafen and S1 filtered out."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _TRANSIT_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch('info.transit.requests.get', return_value=mock_resp):
        fetcher = TransitFetcher(_transit_cfg())
        results = fetcher.fetch()

    assert len(results) == 2
    for r in results:
        assert 'marienplatz' in r['destination'].lower()
    assert results[0]['delay'] == 0
    assert results[1]['delay'] == 3


def test_transit_result_structure():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _TRANSIT_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch('info.transit.requests.get', return_value=mock_resp):
        fetcher = TransitFetcher(_transit_cfg())
        results = fetcher.fetch()

    assert isinstance(results, list)
    for r in results:
        assert 'time' in r
        assert 'delay' in r
        assert 'destination' in r


def test_transit_cache():
    """Second call within TTL must not re-hit the API."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _TRANSIT_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch('info.transit.requests.get', return_value=mock_resp) as mock_get:
        fetcher = TransitFetcher(_transit_cfg())
        fetcher.fetch()
        fetcher.fetch()

    assert mock_get.call_count == 1


def test_transit_returns_empty_on_error():
    with patch('info.transit.requests.get', side_effect=Exception('timeout')):
        fetcher = TransitFetcher(_transit_cfg())
        result = fetcher.fetch()
    assert result == []


def test_transit_fetch_live():
    """Live test — skipped if no network or config absent."""
    pytest.importorskip('yaml')
    import yaml
    from pathlib import Path
    cfg_path = Path('config.yaml')
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    transit_cfg = cfg.get('transit', _transit_cfg())

    try:
        fetcher = TransitFetcher(transit_cfg)
        results = fetcher.fetch()
    except Exception:
        pytest.skip('Live transit API unreachable')

    assert isinstance(results, list)
    for r in results:
        assert 'time' in r and 'delay' in r


# ------------------------------------------------------------------ #
# PiStats                                                              #
# ------------------------------------------------------------------ #

def test_pi_stats_structure():
    stats = PiStats()
    result = stats.fetch()
    assert 'ip' in result
    assert 'cpu_temp' in result
    assert 'hostname' in result
    assert 'updated' in result


def test_pi_stats_ip_is_string():
    result = PiStats().fetch()
    assert isinstance(result['ip'], str)
    assert len(result['ip']) > 0


def test_pi_stats_updated_format():
    result = PiStats().fetch()
    # Should be HH:MM format
    parts = result['updated'].split(':')
    assert len(parts) == 2
    assert parts[0].isdigit() and parts[1].isdigit()


def test_pi_stats_cpu_temp_none_on_windows():
    """On Windows (no thermal sysfs), cpu_temp should be None — not an error."""
    import platform
    result = PiStats().fetch()
    if platform.system() == 'Windows':
        assert result['cpu_temp'] is None


# ------------------------------------------------------------------ #
# Web UI                                                               #
# ------------------------------------------------------------------ #

def _make_client():
    import sys
    sys.path.insert(0, '.')
    from web.app import create_app
    app = create_app(config={
        'web': {'secret_key': 'test', 'port': 5000},
        'sources': {'local_folder': {'path': 'data/uploads'}},
        'display': {'interval_minutes': 60, 'no_repeat_days': 7},
        'weather': {'api_key': '', 'city': 'Munich', 'country_code': 'DE',
                    'units': 'metric', 'refresh_interval_minutes': 30},
        'transit': {'mvg_global_id': 'de:09162:1740', 'line': 'S8',
                    'direction_filter': 'Marienplatz', 'limit': 2,
                    'refresh_interval_minutes': 2},
    })
    app.config['TESTING'] = True
    return app.test_client()


def test_web_status_endpoint():
    client = _make_client()
    resp = client.get('/api/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'last_photo' in data
    assert 'next_update_in_seconds' in data
    assert 'weather' in data
    assert 'transit' in data
    assert 'pi' in data


def test_web_upload_invalid():
    import io
    client = _make_client()
    resp = client.post(
        '/upload',
        data={'photo': (io.BytesIO(b'not an image'), 'bad.jpg')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 400


def test_web_config_get():
    client = _make_client()
    resp = client.get('/config')
    assert resp.status_code == 200
    assert b'direction_filter' in resp.data or b'S8' in resp.data
