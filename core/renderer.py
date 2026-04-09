import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import requests

logger = logging.getLogger(__name__)

# Display geometry
WIDTH = 1200
HEIGHT = 1600
STRIP_HEIGHT = 150

# The 6 physical ink colors of the Waveshare 13.3" Spectra 6 display.
# These are the ACTUAL colors the panel can render — used for palette
# quantization so dithering maps to real ink, not ideal sRGB primaries.
# Slot order matches drivers/epd13in3E.py getbuffer() palette exactly:
#   0=black, 1=white, 2=yellow, 3=red, 4=unused(black), 5=blue, 6=green
_PALETTE_COLORS = [
    (0, 0, 0),        # 0 black
    (255, 255, 255),  # 1 white
    (255, 255, 0),    # 2 yellow
    (255, 0, 0),      # 3 red
    (0, 0, 0),        # 4 unused (maps to black)
    (0, 0, 255),      # 5 blue
    (0, 255, 0),      # 6 green
]


def _make_palette_image():
    pal = Image.new('P', (1, 1))
    flat = []
    for r, g, b in _PALETTE_COLORS:
        flat += [r, g, b]
    flat += [0, 0, 0] * (256 - len(_PALETTE_COLORS))
    pal.putpalette(flat)
    return pal

_PALETTE_IMAGE = _make_palette_image()


def _auto_text_color(image: Image.Image) -> tuple:
    """Return black or white based on average luminance of the bottom STRIP_HEIGHT rows."""
    strip_region = image.crop((0, HEIGHT - STRIP_HEIGHT, WIDTH, HEIGHT))
    gray = strip_region.convert('L')
    avg = sum(gray.getdata()) / (WIDTH * STRIP_HEIGHT)
    return (0, 0, 0) if avg > 128 else (255, 255, 255)


# Cache of rounded (lat, lon) → "City, Country" to avoid repeated Nominatim calls
_geo_cache: dict[str, str] = {}


def _extract_gps(img: Image.Image) -> tuple[float, float] | None:
    """Extract GPS coordinates from PIL image EXIF. Returns (lat, lon) or None."""
    try:
        exif = img.getexif()
        if not exif:
            return None
        gps_ifd = exif.get_ifd(0x8825)  # GPSInfo tag
        if not gps_ifd:
            return None

        def _to_decimal(vals, ref):
            d, m, s = float(vals[0]), float(vals[1]), float(vals[2])
            dec = d + m / 60 + s / 3600
            return -dec if ref in ('S', 'W') else dec

        lat = _to_decimal(gps_ifd.get(2, (0, 0, 0)), gps_ifd.get(1, 'N'))
        lon = _to_decimal(gps_ifd.get(4, (0, 0, 0)), gps_ifd.get(3, 'E'))
        if lat == 0.0 and lon == 0.0:
            return None
        return lat, lon
    except Exception:
        return None


def _reverse_geocode(lat: float, lon: float) -> str | None:
    """Reverse-geocode (lat, lon) to 'City, Country' using Nominatim. Cached."""
    key = f'{lat:.2f},{lon:.2f}'
    if key in _geo_cache:
        return _geo_cache[key]
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'format': 'json', 'lat': lat, 'lon': lon},
            headers={'User-Agent': 'epaper-frame/1.0'},
            timeout=5,
        )
        resp.raise_for_status()
        addr = resp.json().get('address', {})
        city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county', '')
        country = addr.get('country', '')
        result = ', '.join(p for p in [city, country] if p) or None
        if result:
            _geo_cache[key] = result
        return result
    except Exception as exc:
        logger.warning('Reverse geocode failed: %s', exc)
        return None


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Try common monospace fonts, fall back to Pillow default."""
    candidates = (
        [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
            'DejaVuSansMono-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf',
            'LiberationMono-Bold.ttf',
            '/usr/share/fonts/truetype/ubuntu/UbuntuMono-B.ttf',
            'UbuntuMono-B.ttf',
        ] if bold else [
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
            'DejaVuSansMono.ttf',
            'DejaVuSansMono-Bold.ttf',
            'cour.ttf',
            'LiberationMono-Regular.ttf',
            'UbuntuMono-R.ttf',
            'FreeMono.ttf',
        ]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            pass
    logger.warning('No TrueType font found, using Pillow default')
    return ImageFont.load_default()


class Renderer:
    WIDTH = WIDTH
    HEIGHT = HEIGHT

    def __init__(self):
        self._last_location: str | None = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def render(self, path, strip_data=None, strip_fg=(255, 255, 255), auto_color=False) -> Image.Image:
        """Full pipeline: load → fit → compose → return RGB Image."""
        image = self.load(path)
        sd = dict(strip_data) if strip_data else {}
        if self._last_location:
            sd['location'] = self._last_location
        return self.compose(image, sd, strip_fg=strip_fg, auto_color=auto_color)

    def load(self, path) -> Image.Image:
        """Open image, apply EXIF rotation, extract GPS location, return RGB."""
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)  # respect camera orientation
        gps = _extract_gps(img)
        self._last_location = _reverse_geocode(*gps) if gps else None
        return img.convert('RGB')

    def fit_image(self, image: Image.Image) -> Image.Image:
        """Cover-fit to WIDTH x HEIGHT (1200x1600), center crop."""
        target_w, target_h = WIDTH, HEIGHT
        src_w, src_h = image.size

        scale = max(target_w / src_w, target_h / src_h)
        new_w = round(src_w * scale)
        new_h = round(src_h * scale)

        resized = image.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    def enhance_for_epaper(self, image: Image.Image) -> Image.Image:
        """
        Boost saturation and contrast before quantization.
        E-paper dithering tends to wash out colors — pre-enhancing
        compensates so the final result looks vivid on the panel.
        """
        from PIL import ImageEnhance
        image = ImageEnhance.Contrast(image).enhance(1.5)
        image = ImageEnhance.Color(image).enhance(2.0)
        image = ImageEnhance.Sharpness(image).enhance(1.5)
        return image

    def quantize_6color(self, image: Image.Image) -> Image.Image:
        """Floyd-Steinberg dither to the 6-color e-Paper palette, returns RGB."""
        rgb = image.convert('RGB')
        quantized = rgb.quantize(
            palette=_PALETTE_IMAGE,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        return quantized.convert('RGB')

    def render_strip(self, strip_data: dict | None,
                     text_color=(255, 255, 255)) -> Image.Image:
        """
        Render a transparent 1200x150 info strip (text only, no background).

        strip_data keys (all optional):
          weather: {temp, condition, city}
          transit: [{time, delay}, ...]
          pi: {ip, cpu_temp, updated}
        text_color: text RGB tuple (default white for overlay on photos)
        """
        strip = Image.new('RGBA', (WIDTH, STRIP_HEIGHT), (0, 0, 0, 0))
        if strip_data is None:
            return strip

        # Strip visibility config — default all enabled when absent
        cfg = strip_data.get('strip_cfg') or {}
        if not cfg.get('enabled', True):
            return strip
        show_weather  = cfg.get('weather', True)
        show_transit  = cfg.get('transit', True)
        show_ip       = cfg.get('ip', True)
        show_cpu      = cfg.get('cpu_temp', True)
        show_aqi      = cfg.get('aqi', True)
        show_location = cfg.get('location', True)

        draw = ImageDraw.Draw(strip)
        font_large = _load_font(36, bold=True)
        font_small = _load_font(28, bold=True)

        LEFT_X = 20
        RIGHT_MAX_X = WIDTH - 20
        y_positions = [10, 52, 94]

        # --- LEFT: weather (row 0) + transit (rows 1-2) ---
        weather = strip_data.get('weather') or {}
        if show_weather and weather:
            temp = weather.get('temp', '')
            city = weather.get('city', '')
            cond = weather.get('condition', '')
            parts = [p for p in [
                f"{temp}°C" if temp != '' else None,
                city or None,
                cond or None,
            ] if p]
            draw.text((LEFT_X, y_positions[0]), '  '.join(parts),
                      font=font_large, fill=text_color)

        if show_transit:
            transit = strip_data.get('transit') or []
            for i, dep in enumerate(transit[:2]):
                row = y_positions[i + 1]
                t = dep.get('time', '')
                delay = dep.get('delay', 0)
                delay_str = 'on time' if delay == 0 else f'+{delay} min'
                draw.text((LEFT_X, row), f'S8  {t}  {delay_str}',
                          font=font_small, fill=text_color)

        # --- RIGHT: Pi stats (right-aligned) ---
        pi = strip_data.get('pi') or {}
        air = strip_data.get('air') or {}
        right_lines = []
        if show_ip and pi.get('ip'):
            right_lines.append(pi['ip'])
        if show_cpu and pi.get('cpu_temp') is not None:
            right_lines.append(f"CPU {pi['cpu_temp']}°C")
        # Line 3 priority: GPS location > AQI label > updated time
        line3 = (
            (strip_data.get('location') if show_location else None)
            or (f"AQI: {air['label']}" if show_aqi and air.get('label') else None)
        )
        if line3:
            right_lines.append(line3)

        for i, line in enumerate(right_lines[:3]):
            font = font_large if i == 0 else font_small
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((RIGHT_MAX_X - text_w, y_positions[i]), line,
                      font=font, fill=text_color)

        return strip

    def compose(self, image: Image.Image, strip_data=None,
                strip_fg=(255, 255, 255), auto_color=False) -> Image.Image:
        """
        Fit + enhance photo, overlay strip text, compose into 1200x1600 RGB.
        Strip text is drawn directly on the photo — no white bar.
        Returns RGB — the EPD driver handles final palette quantization.
        """
        photo = self.fit_image(image)
        photo = self.enhance_for_epaper(photo)

        if auto_color:
            strip_fg = _auto_text_color(photo)

        canvas = photo.convert('RGBA')
        strip = self.render_strip(strip_data, text_color=strip_fg)
        canvas.alpha_composite(strip, dest=(0, HEIGHT - STRIP_HEIGHT))

        # Single quantize pass — driver's getbuffer() will do its own
        # quantize, so we return plain RGB and let it handle the ink mapping.
        return canvas.convert('RGB')
