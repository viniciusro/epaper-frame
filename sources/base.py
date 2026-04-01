from abc import ABC, abstractmethod


class PhotoSource(ABC):
    @abstractmethod
    def list_photos(self): pass

    @abstractmethod
    def sync(self): pass

    @property
    @abstractmethod
    def name(self): pass
