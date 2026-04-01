from sources.base import PhotoSource


class NextcloudSource(PhotoSource):
    def __init__(self, config): self.config = config

    @property
    def name(self): return 'nextcloud'

    def list_photos(self): raise NotImplementedError

    def sync(self): raise NotImplementedError
