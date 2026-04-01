import logging
import time
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

_API_URL = 'https://www.mvg.de/api/bgw-pt/v3/departures'


class TransitFetcher:
    def __init__(self, config):
        self.config = config
        self._cache = None
        self._cache_time = 0.0

    def _ttl_seconds(self):
        return self.config.get('refresh_interval_minutes', 2) * 60

    def fetch(self):
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self._ttl_seconds():
            return self._cache

        global_id = self.config.get('mvg_global_id', 'de:09162:1740')
        line_filter = self.config.get('line', 'S8')
        direction_filter = self.config.get('direction_filter', 'Marienplatz').lower()
        limit = self.config.get('limit', 2)

        try:
            resp = requests.get(
                _API_URL,
                params={
                    'globalId': global_id,
                    'limit': 8,
                    'transportTypes': 'SBAHN',
                },
                timeout=10,
                headers={'Accept': 'application/json'},
            )
            resp.raise_for_status()
            departures = resp.json()
        except Exception as exc:
            logger.warning('Transit fetch failed: %s', exc)
            return self._cache if self._cache is not None else []

        results = []
        for dep in departures:
            label = dep.get('label', '')
            destination = dep.get('destination', '')
            if label != line_filter:
                continue
            if direction_filter not in destination.lower():
                continue

            planned = dep.get('plannedDepartureTime')
            realtime = dep.get('realtimeDepartureTime')

            if planned is None:
                continue

            if realtime and realtime != planned:
                delay = round((realtime - planned) / 60000)
            else:
                delay = 0

            dep_time = datetime.fromtimestamp(planned / 1000).strftime('%H:%M')

            results.append({
                'time': dep_time,
                'delay': max(delay, 0),
                'destination': destination,
            })

            if len(results) >= limit:
                break

        self._cache = results
        self._cache_time = now
        return results
