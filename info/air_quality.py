import logging
import time

import requests

logger = logging.getLogger(__name__)

_API_URL = 'https://api.openweathermap.org/data/2.5/air_pollution'
_AQI_LABELS = {1: 'Good', 2: 'Fair', 3: 'Moderate', 4: 'Poor', 5: 'Very Poor'}


class AirQualityFetcher:
    def __init__(self, config):
        self.config = config  # shares the weather config section (api_key, refresh_interval_minutes)
        self._cache = None
        self._cache_time = 0.0

    def _ttl_seconds(self):
        return self.config.get('refresh_interval_minutes', 30) * 60

    def fetch(self, lat: float, lon: float) -> dict | None:
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self._ttl_seconds():
            return self._cache

        api_key = self.config.get('api_key', '')
        if not api_key:
            return self._cache

        try:
            resp = requests.get(
                _API_URL,
                params={'lat': lat, 'lon': lon, 'appid': api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            aqi = data['list'][0]['main']['aqi']
            result = {
                'aqi': aqi,
                'label': _AQI_LABELS.get(aqi, str(aqi)),
            }
            self._cache = result
            self._cache_time = now
            return result
        except Exception as exc:
            logger.warning('Air quality fetch failed: %s', exc)
            return self._cache
