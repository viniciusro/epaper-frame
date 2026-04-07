import pytest
from pathlib import Path
from PIL import Image
from core.renderer import Renderer, WIDTH, HEIGHT, STRIP_HEIGHT, _PALETTE_COLORS

PHOTO_HEIGHT = HEIGHT  # photo now fills full canvas (strip overlays)

FIXTURES = Path(__file__).parent / 'fixtures'

MOCK_STRIP = {
    'weather': {'temp': 9, 'condition': 'light rain', 'city': 'München'},
    'transit': [
        {'time': '08:04', 'delay': 0},
        {'time': '08:34', 'delay': 3},
    ],
    'pi': {'ip': '192.168.1.42', 'cpu_temp': 42.0, 'updated': '08:01'},
}

# Allowed RGB colors after 6-color quantization
ALLOWED_COLORS = {tuple(c) for c in _PALETTE_COLORS}


@pytest.fixture(scope='module')
def renderer():
    return Renderer()


@pytest.fixture(scope='module')
def landscape_img():
    return Image.open(FIXTURES / 'landscape.jpg').convert('RGB')


@pytest.fixture(scope='module')
def portrait_img():
    return Image.open(FIXTURES / 'portrait.jpg').convert('RGB')


@pytest.fixture(scope='module')
def square_img():
    return Image.open(FIXTURES / 'square.jpg').convert('RGB')


# ------------------------------------------------------------------ #
# fit_image                                                            #
# ------------------------------------------------------------------ #

def test_fit_image_landscape(renderer, landscape_img):
    result = renderer.fit_image(landscape_img)
    assert result.size == (WIDTH, PHOTO_HEIGHT), f'Expected {(WIDTH, PHOTO_HEIGHT)}, got {result.size}'


def test_fit_image_portrait(renderer, portrait_img):
    result = renderer.fit_image(portrait_img)
    assert result.size == (WIDTH, PHOTO_HEIGHT)


def test_fit_image_square(renderer, square_img):
    result = renderer.fit_image(square_img)
    assert result.size == (WIDTH, PHOTO_HEIGHT)


# ------------------------------------------------------------------ #
# quantize_6color                                                      #
# ------------------------------------------------------------------ #

def test_quantize_6color(renderer, square_img):
    small = square_img.resize((120, 145))  # keep test fast
    result = renderer.quantize_6color(small)
    assert result.mode == 'RGB'

    unique = set(map(tuple, result.getdata()))
    unexpected = unique - ALLOWED_COLORS
    assert not unexpected, f'Unexpected colors found: {unexpected}'


# ------------------------------------------------------------------ #
# compose                                                              #
# ------------------------------------------------------------------ #

def test_compose_size(renderer, landscape_img):
    result = renderer.compose(landscape_img, MOCK_STRIP)
    assert result.size == (WIDTH, HEIGHT)


def test_compose_strip_region(renderer, square_img):
    result = renderer.compose(square_img, MOCK_STRIP)
    # Crop the bottom strip area where text is overlaid
    strip_region = result.crop((0, HEIGHT - STRIP_HEIGHT, WIDTH, HEIGHT))
    # Strip text (white) should produce non-uniform pixels over the photo
    colors = set(map(tuple, strip_region.getdata()))
    assert len(colors) > 1, 'Strip region is uniform — strip not rendered'


# ------------------------------------------------------------------ #
# render (full pipeline)                                               #
# ------------------------------------------------------------------ #

def test_render_full_pipeline(renderer):
    result = renderer.render(FIXTURES / 'landscape.jpg', strip_data=MOCK_STRIP)
    assert result is not None
    assert result.size == (WIDTH, HEIGHT)
    assert result.mode == 'RGB'


def test_render_no_strip_data(renderer):
    """render() should succeed even with strip_data=None."""
    result = renderer.render(FIXTURES / 'portrait.jpg', strip_data=None)
    assert result.size == (WIDTH, HEIGHT)
