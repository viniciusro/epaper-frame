from sources.base import PhotoSource


class UploadSource(PhotoSource):
    def __init__(self, config): self.config = config

    @property
    def name(self): return 'upload'

    def list_photos(self): raise NotImplementedError

    def sync(self): return 0
