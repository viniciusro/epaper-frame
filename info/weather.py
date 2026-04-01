import logging
import time
import requests

logger = logging.getLogger(__name__)

_API_URL = 'https://api.openweathermap.org/data/2.5/weather'


class WeatherFetcher:
    def __init__(self, config):
        self.config = config
        self._cache = None
        self._cache_time = 0.0

    def _ttl_seconds(self):
        return self.config.get('refresh_interval_minutes', 30) * 60

    def fetch(self):
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self._ttl_seconds():
            return self._cache

        api_key = self.config.get('api_key', '')
        city = self.config.get('city', 'Munich')
        country = self.config.get('country_code', 'DE')
        units = self.config.get('units', 'metric')

        if not api_key:
            logger.warning('Weather API key not configured')
            return self._cache

        try:
            resp = requests.get(
                _API_URL,
                params={'q': f'{city},{country}', 'appid': api_key, 'units': units},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            result = {
                'temp': round(data['main']['temp']),
                'condition': data['weather'][0]['description'],
                'city': data['name'],
                'updated': _now_hhmm(),
            }
            self._cache = result
            self._cache_time = now
            return result
        except Exception as exc:
            logger.warning('Weather fetch failed: %s', exc)
            return self._cache


def _now_hhmm():
    from datetime import datetime
    return datetime.now().strftime('%H:%M')
