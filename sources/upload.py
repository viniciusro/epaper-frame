import logging
from pathlib import Path
from PIL import Image

from sources.base import PhotoSource

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


class UploadSource(PhotoSource):
    def __init__(self, config):
        self.config = config
        # Upload saves into the local_folder path configured alongside it
        self._folder = Path(config.get('path', 'data/uploads'))

    @property
    def name(self):
        return 'upload'

    def save(self, file_storage, destination_folder=None):
        """
        Validate and save an uploaded file.

        file_storage: a file-like object with a .filename attribute (Flask
                      FileStorage) or a plain Path/str to an existing file.
        destination_folder: override save location (defaults to self._folder).

        Returns the saved Path.
        Raises ValueError for non-image files.
        """
        dest = Path(destination_folder) if destination_folder else self._folder
        dest.mkdir(parents=True, exist_ok=True)

        # Determine filename and readable stream
        if hasattr(file_storage, 'filename'):
            filename = Path(file_storage.filename).name
            stream = file_storage
        else:
            # Plain path passed (e.g. in tests)
            filename = Path(file_storage).name
            stream = open(file_storage, 'rb')

        suffix = Path(filename).suffix.lower()
        if suffix not in _IMAGE_SUFFIXES:
            raise ValueError(f'Unsupported file type: {suffix!r}')

        # Validate it's actually a readable image
        try:
            img = Image.open(stream)
            img.verify()
        except Exception as exc:
            raise ValueError(f'File is not a valid image: {exc}') from exc

        # Re-open after verify() (verify() consumes the stream)
        if hasattr(file_storage, 'seek'):
            file_storage.seek(0)
            stream = file_storage
        else:
            stream = open(file_storage, 'rb')

        save_path = dest / filename
        with open(save_path, 'wb') as f:
            f.write(stream.read())

        logger.info('Saved upload: %s', save_path)
        return save_path

    def list_photos(self):
        if not self._folder.exists():
            return []
        return sorted(
            p for p in self._folder.rglob('*')
            if p.is_file()
            and not p.name.startswith('.')
            and p.suffix.lower() in _IMAGE_SUFFIXES
        )

    def sync(self):
        return 0
