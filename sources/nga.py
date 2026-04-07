import csv
import io
import json
import logging
import random
from pathlib import Path

import requests

from sources.base import PhotoSource

logger = logging.getLogger(__name__)

_IMAGES_CSV_URL = 'https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data/published_images.csv'
_OBJECTS_CSV_URL = 'https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data/objects.csv'
_IIIF_SIZE = '1200,'        # fit to 1200px wide, height proportional
_META_FILE = '.nga_meta.json'
_CACHE_SIZE = 50            # max images to keep on disk at once
_MIN_WIDTH = 800            # skip images smaller than this (poor quality when scaled)


class NGASource(PhotoSource):
    """Downloads open-access artwork images from the National Gallery of Art.

    On each sync() it picks a random selection of open-access images from the
    NGA dataset, downloads them to data/cache/nga/, and returns them via
    list_photos(). The local cache is capped at _CACHE_SIZE images — old ones
    are evicted when new ones arrive so the Pi disk stays bounded.
    """

    def __init__(self, config):
        self.config = config
        self._cache_dir = Path('data/cache/nga')
        self._meta_path = self._cache_dir / _META_FILE
        self._cache_size = int(config.get('cache_size', _CACHE_SIZE))

    @property
    def name(self):
        return 'nga'

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

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

    def _fetch_candidates(self):
        """Download the published_images CSV and return a list of eligible rows."""
        try:
            resp = requests.get(_IMAGES_CSV_URL, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning('NGA: failed to fetch image list: %s', exc)
            return []

        candidates = []
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            if row.get('openaccess', '0') != '1':
                continue
            uuid = row.get('uuid', '').strip()
            if not uuid:
                continue
            try:
                w = int(row.get('width') or 0)
                h = int(row.get('height') or 0)
            except ValueError:
                continue
            if w < _MIN_WIDTH or h < _MIN_WIDTH:
                continue
            candidates.append({
                'uuid': uuid,
                'width': w,
                'height': h,
            })

        logger.info('NGA: %d open-access candidates found', len(candidates))
        return candidates

    def _image_url(self, uuid):
        return f'https://api.nga.gov/iiif/{uuid}/full/{_IIIF_SIZE}/0/default.jpg'

    def _evict_old(self, meta, keep_uuids):
        """Remove cached files not in keep_uuids, update meta."""
        for uuid, info in list(meta.items()):
            if uuid not in keep_uuids:
                path = self._cache_dir / info['filename']
                if path.exists():
                    path.unlink()
                    logger.debug('NGA: evicted %s', info['filename'])
                del meta[uuid]

    # ------------------------------------------------------------------ #
    # PhotoSource interface                                                #
    # ------------------------------------------------------------------ #

    def sync(self):
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        meta = self._load_meta()

        candidates = self._fetch_candidates()
        if not candidates:
            return 0

        # Pick a random selection, excluding already-cached UUIDs
        already_cached = set(meta.keys())
        fresh = [c for c in candidates if c['uuid'] not in already_cached]
        random.shuffle(fresh)

        want = max(0, self._cache_size - len(already_cached))
        to_download = fresh[:want]

        new_count = 0
        for item in to_download:
            uuid = item['uuid']
            filename = f'{uuid}.jpg'
            local_path = self._cache_dir / filename
            url = self._image_url(uuid)

            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
                meta[uuid] = {'filename': filename, 'url': url}
                new_count += 1
                logger.info('NGA: downloaded %s', filename)
            except Exception as exc:
                logger.warning('NGA: failed to download %s: %s', uuid, exc)

        # Evict oldest if over cache limit
        if len(meta) > self._cache_size:
            keep = set(list(meta.keys())[-self._cache_size:])
            self._evict_old(meta, keep)

        self._save_meta(meta)
        return new_count

    def list_photos(self):
        if not self._cache_dir.exists():
            return []
        return sorted(
            p for p in self._cache_dir.iterdir()
            if p.is_file()
            and not p.name.startswith('.')
            and p.suffix.lower() == '.jpg'
        )
