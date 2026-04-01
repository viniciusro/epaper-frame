import io
import pytest
from pathlib import Path
from PIL import Image

from sources.local import LocalFolderSource
from sources.upload import UploadSource


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _make_image_bytes(fmt='JPEG'):
    buf = io.BytesIO()
    img = Image.new('RGB', (10, 10), color=(100, 150, 200))
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


class _FakeFileStorage:
    """Minimal stand-in for Flask FileStorage."""
    def __init__(self, filename, data: bytes):
        self.filename = filename
        self._buf = io.BytesIO(data)

    def read(self, n=-1):
        return self._buf.read(n)

    def seek(self, pos):
        self._buf.seek(pos)


# ------------------------------------------------------------------ #
# LocalFolderSource                                                    #
# ------------------------------------------------------------------ #

def test_local_source_lists_images(tmp_path):
    (tmp_path / 'a.jpg').write_bytes(_make_image_bytes().read())
    (tmp_path / 'b.jpeg').write_bytes(_make_image_bytes().read())
    (tmp_path / 'c.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)
    (tmp_path / 'readme.txt').write_text('not an image')

    src = LocalFolderSource({'path': str(tmp_path)})
    photos = src.list_photos()
    names = {p.name for p in photos}
    assert names == {'a.jpg', 'b.jpeg', 'c.png'}


def test_local_source_excludes_hidden(tmp_path):
    (tmp_path / 'visible.jpg').write_bytes(_make_image_bytes().read())
    (tmp_path / '.hidden.jpg').write_bytes(_make_image_bytes().read())

    src = LocalFolderSource({'path': str(tmp_path)})
    photos = src.list_photos()
    names = {p.name for p in photos}
    assert '.hidden.jpg' not in names
    assert 'visible.jpg' in names


def test_local_source_nonexistent_path():
    src = LocalFolderSource({'path': '/does/not/exist'})
    assert src.list_photos() == []


def test_local_source_sync_returns_zero(tmp_path):
    src = LocalFolderSource({'path': str(tmp_path)})
    assert src.sync() == 0


# ------------------------------------------------------------------ #
# UploadSource                                                         #
# ------------------------------------------------------------------ #

def test_upload_save_valid_image(tmp_path):
    src = UploadSource({'path': str(tmp_path)})
    img_bytes = _make_image_bytes().read()
    fs = _FakeFileStorage('photo.jpg', img_bytes)

    saved = src.save(fs, destination_folder=tmp_path)
    assert saved.exists()
    assert saved.name == 'photo.jpg'


def test_upload_save_invalid_file(tmp_path):
    src = UploadSource({'path': str(tmp_path)})
    fs = _FakeFileStorage('notes.txt', b'this is not an image')
    with pytest.raises(ValueError):
        src.save(fs, destination_folder=tmp_path)


def test_upload_save_invalid_image_data(tmp_path):
    """A .jpg extension but corrupt bytes should raise ValueError."""
    src = UploadSource({'path': str(tmp_path)})
    fs = _FakeFileStorage('bad.jpg', b'not jpeg data at all')
    with pytest.raises(ValueError):
        src.save(fs, destination_folder=tmp_path)


def test_upload_list_photos(tmp_path):
    src = UploadSource({'path': str(tmp_path)})
    img_bytes = _make_image_bytes().read()
    fs = _FakeFileStorage('upload1.jpg', img_bytes)
    src.save(fs, destination_folder=tmp_path)

    photos = src.list_photos()
    assert any(p.name == 'upload1.jpg' for p in photos)


def test_upload_sync_returns_zero(tmp_path):
    src = UploadSource({'path': str(tmp_path)})
    assert src.sync() == 0
