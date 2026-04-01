from sources.base import PhotoSource


class LocalFolderSource(PhotoSource):
    def __init__(self, config): self.config = config

    @property
    def name(self): return 'local'

    def list_photos(self): raise NotImplementedError

    def sync(self): return 0
