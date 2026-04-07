import io
import json
import pytest
from pathlib import Path
from PIL import Image
from unittest.mock import patch, MagicMock

from sources.local import LocalFolderSource
from sources.upload import UploadSource
from sources.nga import NGASource


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


# ------------------------------------------------------------------ #
# NGASource                                                            #
# ------------------------------------------------------------------ #

_FAKE_CSV = (
    'uuid,iiifurl,iiifthumburl,viewtype,sequence,width,height,maxpixels,openaccess,'
    'created,modified,depictstmsobjectid,assistivetext\n'
    'abc-001,https://api.nga.gov/iiif/abc-001,,primary,1,3000,4000,12000000,1,'
    '2020-01-01,2020-01-01,1234,\n'
    'abc-002,https://api.nga.gov/iiif/abc-002,,primary,1,2000,3000,6000000,0,'
    '2020-01-01,2020-01-01,5678,\n'  # openaccess=0, should be skipped
    'abc-003,https://api.nga.gov/iiif/abc-003,,primary,1,100,100,10000,1,'
    '2020-01-01,2020-01-01,9999,\n'  # too small, should be skipped
)


def test_nga_list_photos_empty(tmp_path):
    src = NGASource({'cache_size': 10})
    src._cache_dir = tmp_path
    assert src.list_photos() == []


def test_nga_sync_downloads_open_access(tmp_path):
    src = NGASource({'cache_size': 10})
    src._cache_dir = tmp_path
    src._meta_path = tmp_path / '.nga_meta.json'

    fake_image = _make_image_bytes().read()

    with patch('sources.nga.requests.get') as mock_get:
        # First call: CSV fetch; subsequent calls: image downloads
        csv_resp = MagicMock()
        csv_resp.text = _FAKE_CSV
        csv_resp.raise_for_status = MagicMock()

        img_resp = MagicMock()
        img_resp.content = fake_image
        img_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [csv_resp, img_resp]

        count = src.sync()

    assert count == 1  # only abc-001 passes filters
    assert (tmp_path / 'abc-001.jpg').exists()
    meta = json.loads((tmp_path / '.nga_meta.json').read_text())
    assert 'abc-001' in meta


def test_nga_sync_skips_already_cached(tmp_path):
    src = NGASource({'cache_size': 10})
    src._cache_dir = tmp_path
    src._meta_path = tmp_path / '.nga_meta.json'

    # Pre-populate meta as if abc-001 is already cached
    (tmp_path / 'abc-001.jpg').write_bytes(b'fake')
    src._save_meta({'abc-001': {'filename': 'abc-001.jpg', 'url': 'http://x'}})

    with patch('sources.nga.requests.get') as mock_get:
        csv_resp = MagicMock()
        csv_resp.text = _FAKE_CSV
        csv_resp.raise_for_status = MagicMock()
        mock_get.return_value = csv_resp

        count = src.sync()

    assert count == 0  # nothing new to download


def test_nga_sync_network_error_returns_zero(tmp_path):
    src = NGASource({'cache_size': 10})
    src._cache_dir = tmp_path
    src._meta_path = tmp_path / '.nga_meta.json'

    with patch('sources.nga.requests.get', side_effect=Exception('network error')):
        count = src.sync()

    assert count == 0
