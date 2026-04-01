from pathlib import Path
from sources.base import PhotoSource

_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


class LocalFolderSource(PhotoSource):
    def __init__(self, config):
        self.config = config
        self._path = Path(config['path'])

    @property
    def name(self):
        return 'local'

    def list_photos(self):
        if not self._path.exists():
            return []
        photos = [
            p for p in self._path.rglob('*')
            if p.is_file()
            and not p.name.startswith('.')
            and p.suffix.lower() in _IMAGE_SUFFIXES
        ]
        return sorted(photos)

    def sync(self):
        return 0
