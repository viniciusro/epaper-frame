import pytest
from pathlib import Path
from PIL import Image
from core.shuffler import Shuffler


# ------------------------------------------------------------------ #
# Fake source helpers                                                  #
# ------------------------------------------------------------------ #

class _FakeSource:
    def __init__(self, name, paths):
        self._name = name
        self._paths = [Path(p) for p in paths]

    @property
    def name(self):
        return self._name

    def list_photos(self):
        return list(self._paths)

    def sync(self):
        return 0


def _make_shuffler(tmp_path, sources, no_repeat_days=7):
    config = {'display': {'no_repeat_days': no_repeat_days}}
    db = tmp_path / 'history.db'
    return Shuffler(config, sources, db_path=db)


def _photos(tmp_path, prefix, count):
    """Create real tiny image files so Path.exists() is satisfied."""
    paths = []
    for i in range(count):
        p = tmp_path / f'{prefix}_{i}.jpg'
        img = Image.new('RGB', (4, 4), color=(i * 20, 100, 200))
        img.save(str(p))
        paths.append(str(p))
    return paths


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #

def test_next_returns_path(tmp_path):
    photos = _photos(tmp_path, 'a', 3)
    src = _FakeSource('local', photos)
    shuffler = _make_shuffler(tmp_path, [src])
    result = shuffler.next()
    assert isinstance(result, Path)
    assert str(result) in photos


def test_no_repeat_window(tmp_path):
    photos = _photos(tmp_path, 'b', 3)
    src = _FakeSource('local', photos)
    shuffler = _make_shuffler(tmp_path, [src], no_repeat_days=7)

    seen = set()
    for _ in range(3):
        p = shuffler.next()
        assert str(p) not in seen, f'Repeated photo: {p}'
        seen.add(str(p))


def test_history_reset_when_exhausted(tmp_path):
    photos = _photos(tmp_path, 'c', 2)
    src = _FakeSource('local', photos)
    shuffler = _make_shuffler(tmp_path, [src], no_repeat_days=7)

    # Exhaust all photos
    shuffler.next()
    shuffler.next()
    assert shuffler.history_count() == 2

    # Third call should trigger reset and succeed
    result = shuffler.next()
    assert isinstance(result, Path)
    assert shuffler.history_count() == 1  # fresh history with just this pick


def test_weighted_by_source(tmp_path):
    """Source B (1 photo) should appear across 50 draws despite source A having 10."""
    photos_a = _photos(tmp_path, 'big', 10)
    photos_b = _photos(tmp_path, 'small', 1)
    src_a = _FakeSource('sourceA', photos_a)
    src_b = _FakeSource('sourceB', photos_b)

    # Use no_repeat_days=0 so history doesn't block reuse
    config = {'display': {'no_repeat_days': 0}}
    db = tmp_path / 'history.db'
    shuffler = Shuffler(config, [src_a, src_b], db_path=db)

    sources_seen = set()
    for _ in range(50):
        p = shuffler.next()
        # identify source by filename prefix
        sources_seen.add('sourceB' if 'small' in p.name else 'sourceA')

    assert 'sourceA' in sources_seen
    assert 'sourceB' in sources_seen, 'sourceB never selected despite equal source weight'


def test_history_persists(tmp_path):
    photos = _photos(tmp_path, 'd', 5)
    src = _FakeSource('local', photos)
    db = tmp_path / 'history.db'
    config = {'display': {'no_repeat_days': 7}}

    shuffler1 = Shuffler(config, [src], db_path=db)
    chosen = shuffler1.next()
    assert shuffler1.history_count() == 1

    # New instance, same DB
    shuffler2 = Shuffler(config, [src], db_path=db)
    assert shuffler2.history_count() == 1

    # chosen photo should not be returned again
    for _ in range(4):
        p = shuffler2.next()
        assert str(p) != str(chosen), f'Repeated photo from new instance: {p}'


def test_reset_history(tmp_path):
    photos = _photos(tmp_path, 'e', 3)
    src = _FakeSource('local', photos)
    shuffler = _make_shuffler(tmp_path, [src])

    shuffler.next()
    shuffler.next()
    assert shuffler.history_count() == 2

    shuffler.reset_history()
    assert shuffler.history_count() == 0
