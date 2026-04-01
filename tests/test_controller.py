import os
import threading
import time
import pytest
from pathlib import Path
from PIL import Image
from unittest.mock import MagicMock, patch

# Force mock display for all controller tests
os.environ['EPAPER_MOCK'] = '1'

import web.app as webapp
from core.frame_controller import FrameController

FIXTURES = Path(__file__).parent / 'fixtures'


def _minimal_config(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    # Drop one real image so shuffler has something to pick
    img = Image.new('RGB', (100, 100), color=(80, 120, 200))
    img.save(str(photos_dir / 'test.jpg'))

    return {
        'display': {'interval_minutes': 60, 'no_repeat_days': 7},
        'sources': {
            'local_folder': {'enabled': True, 'path': str(photos_dir)},
            'upload': {'enabled': False},
            'nextcloud': {'enabled': False},
        },
        'weather': {'api_key': '', 'city': 'Munich', 'country_code': 'DE',
                    'units': 'metric', 'refresh_interval_minutes': 30},
        'transit': {'mvg_global_id': 'de:09162:1740', 'line': 'S8',
                    'direction_filter': 'Marienplatz', 'limit': 2,
                    'refresh_interval_minutes': 2},
        'web': {'port': 15099, 'secret_key': 'test'},
    }


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #

def test_controller_init(tmp_path):
    cfg = _minimal_config(tmp_path)
    ctrl = FrameController(cfg)
    assert ctrl._shuffler is not None
    assert ctrl._renderer is not None
    assert ctrl._display is not None
    assert len(ctrl._sources) >= 1


def test_display_cycle_mock(tmp_path):
    """One full _do_display_cycle() should transition state and save a PNG."""
    cfg = _minimal_config(tmp_path)

    # Reset web state
    webapp.update_state(status='idle', weather=None, transit=[], pi={})

    ctrl = FrameController(cfg)

    # Pre-populate info state so strip render has data
    webapp.update_state(
        weather={'temp': 9, 'condition': 'test', 'city': 'München', 'updated': '00:00'},
        transit=[{'time': '00:04', 'delay': 0, 'destination': 'Marienplatz'}],
        pi={'ip': '127.0.0.1', 'cpu_temp': None, 'hostname': 'test', 'updated': '00:00'},
    )

    states_seen = []
    original_update = webapp.update_state

    def tracking_update(**kwargs):
        if 'status' in kwargs:
            states_seen.append(kwargs['status'])
        original_update(**kwargs)

    with patch.object(webapp, 'update_state', side_effect=tracking_update):
        ctrl._do_display_cycle()

    assert 'rendering' in states_seen
    assert 'refreshing' in states_seen

    with webapp._state_lock:
        assert webapp._state['last_photo'] is not None


def test_trigger_next(tmp_path):
    """trigger_next() should set the event so display_loop wakes early."""
    cfg = _minimal_config(tmp_path)
    ctrl = FrameController(cfg)

    webapp.next_photo_event.clear()
    assert not webapp.next_photo_event.is_set()

    ctrl.trigger_next()
    assert webapp.next_photo_event.is_set()


def test_info_refresh_updates_state(tmp_path):
    """One iteration of _info_refresh_loop should update web state."""
    cfg = _minimal_config(tmp_path)
    ctrl = FrameController(cfg)

    webapp.update_state(weather=None, transit=[], pi={})

    mock_weather = {'temp': 5, 'condition': 'clear', 'city': 'München', 'updated': '12:00'}
    mock_transit = [{'time': '12:01', 'delay': 0, 'destination': 'Marienplatz'}]
    mock_pi = {'ip': '10.0.0.1', 'cpu_temp': None, 'hostname': 'pi', 'updated': '12:00'}

    with patch.object(ctrl._weather, 'fetch', return_value=mock_weather), \
         patch.object(ctrl._transit, 'fetch', return_value=mock_transit), \
         patch.object(ctrl._pi_stats, 'fetch', return_value=mock_pi):

        # Run one iteration manually (don't let the sleep loop forever)
        ctrl._weather.fetch()
        ctrl._transit.fetch()
        pi = ctrl._pi_stats.fetch()
        webapp.update_state(
            weather=ctrl._weather.fetch(),
            transit=ctrl._transit.fetch(),
            pi=pi,
        )

    with webapp._state_lock:
        assert webapp._state['weather'] == mock_weather
        assert webapp._state['transit'] == mock_transit


def test_build_sources_local_only(tmp_path):
    cfg = _minimal_config(tmp_path)
    ctrl = FrameController(cfg)
    names = [s.name for s in ctrl._sources]
    assert 'local' in names
    assert 'nextcloud' not in names


def test_build_sources_nextcloud_disabled(tmp_path):
    cfg = _minimal_config(tmp_path)
    cfg['sources']['nextcloud']['enabled'] = False
    ctrl = FrameController(cfg)
    names = [s.name for s in ctrl._sources]
    assert 'nextcloud' not in names
