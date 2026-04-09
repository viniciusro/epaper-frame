import json
import logging
from pathlib import Path

from sources.base import PhotoSource

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
_META_FILE = '.sync_meta.json'


class NextcloudSource(PhotoSource):
    def __init__(self, config):
        self.config = config
        self._cache_dir = Path('data/cache/nextcloud')
        self._meta_path = self._cache_dir / _META_FILE

    @property
    def name(self):
        return 'nextcloud'

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_client(self):
        from webdav3.client import Client
        options = {
            'webdav_hostname': self.config['url'],
            'webdav_login': self.config['username'],
            'webdav_password': self.config['password'],
        }
        return Client(options)

    def _load_meta(self):
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text())
            except Exception:
                pass
        return {}

    def _save_meta(self, meta):
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path.write_text(json.dumps(meta, indent=2))

    # ------------------------------------------------------------------ #
    # PhotoSource interface                                                #
    # ------------------------------------------------------------------ #

    def sync(self):
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        meta = self._load_meta()
        new_count = 0

        try:
            client = self._get_client()
            remote_path = self.config.get('remote_path', '/')
            remote_files = client.list(remote_path, get_info=True)
        except Exception as exc:
            logger.warning('Nextcloud sync failed: %s', exc)
            return 0

        for info in remote_files:
            name = info.get('path', '').rstrip('/').split('/')[-1]
            if not name or Path(name).suffix.lower() not in _IMAGE_SUFFIXES:
                continue

            etag = info.get('etag', '').strip('"')
            last_mod = info.get('modified', '')
            cache_key = name
            cached_etag = meta.get(cache_key, {}).get('etag')
            local_path = self._cache_dir / name

            # Skip if already cached with same ETag
            if local_path.exists() and etag and etag == cached_etag:
                continue

            remote_file_path = f"{remote_path.rstrip('/')}/{name}"
            try:
                client.download_file(remote_file_path, str(local_path))
                meta[cache_key] = {'etag': etag, 'modified': last_mod}
                new_count += 1
                logger.info('Downloaded %s', name)
            except Exception as exc:
                logger.warning('Failed to download %s: %s', name, exc)

        self._save_meta(meta)
        self._evict(meta)
        return new_count

    def _evict(self, meta: dict):
        """Remove oldest cached files if count exceeds cache_size."""
        cache_size = self.config.get('cache_size', 50)
        cached = sorted(
            (p for p in self._cache_dir.iterdir()
             if p.is_file() and not p.name.startswith('.')
             and p.suffix.lower() in _IMAGE_SUFFIXES),
            key=lambda p: p.stat().st_mtime,
        )
        for path in cached[:-cache_size] if cache_size < len(cached) else []:
            try:
                path.unlink()
                meta.pop(path.name, None)
                logger.info('Evicted cached file %s', path.name)
            except Exception as exc:
                logger.warning('Failed to evict %s: %s', path.name, exc)
        if len(cached) > cache_size:
            self._save_meta(meta)

    def list_photos(self):
        if not self._cache_dir.exists():
            return []
        return sorted(
            p for p in self._cache_dir.iterdir()
            if p.is_file()
            and not p.name.startswith('.')
            and p.suffix.lower() in _IMAGE_SUFFIXES
        )
