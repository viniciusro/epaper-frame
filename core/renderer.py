import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# Display geometry
WIDTH = 1200
HEIGHT = 1600
STRIP_HEIGHT = 150
PHOTO_HEIGHT = HEIGHT - STRIP_HEIGHT  # 1450

# 6-color e-Paper palette (Pillow palette format: flat R,G,B list, 256 entries)
# Slot order must match drivers/epd13in3E.py getbuffer() palette:
#   0=black, 1=white, 2=yellow, 3=red, 4=unused(black), 5=blue, 6=green
_PALETTE_COLORS = [
    (0, 0, 0),        # 0 black
    (255, 255, 255),  # 1 white
    (255, 255, 0),    # 2 yellow
    (255, 0, 0),      # 3 red
    (0, 0, 0),        # 4 unused (black)
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


def _load_font(size: int) -> ImageFont.ImageFont:
    """Try common monospace fonts, fall back to Pillow default."""
    candidates = [
        'DejaVuSansMono.ttf',
        'DejaVuSansMono-Bold.ttf',
        'cour.ttf',       # Courier New (Windows)
        'LiberationMono-Regular.ttf',
        'UbuntuMono-R.ttf',
        'FreeMono.ttf',
    ]
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
    STRIP_HEIGHT = STRIP_HEIGHT

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def render(self, path, strip_data=None) -> Image.Image:
        """Full pipeline: load → fit → compose with strip → return Image."""
        image = self.load(path)
        return self.compose(image, strip_data)

    def load(self, path) -> Image.Image:
        """Open any image format and return an RGB PIL Image."""
        img = Image.open(path)
        return img.convert('RGB')

    def fit_image(self, image: Image.Image) -> Image.Image:
        """Cover-fit image to WIDTH x PHOTO_HEIGHT (1200x1450), center crop."""
        target_w, target_h = WIDTH, PHOTO_HEIGHT
        src_w, src_h = image.size

        # Scale so the image covers the target (no black bars)
        scale = max(target_w / src_w, target_h / src_h)
        new_w = round(src_w * scale)
        new_h = round(src_h * scale)

        resized = image.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    def quantize_6color(self, image: Image.Image) -> Image.Image:
        """Floyd-Steinberg dither to the 6-color e-Paper palette."""
        rgb = image.convert('RGB')
        # Apply slight blur before quantize to improve dithering quality
        rgb = rgb.filter(ImageFilter.SMOOTH_MORE)
        quantized = rgb.quantize(
            palette=_PALETTE_IMAGE,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        # Convert back to RGB so callers get a consistent mode
        return quantized.convert('RGB')

    def render_strip(self, strip_data: dict | None) -> Image.Image:
        """
        Render the 1200x150 info strip.

        strip_data keys (all optional):
          weather: {temp: float, condition: str, city: str}
          transit: [{time: str, delay: int}, ...]
          pi: {ip: str, cpu_temp: float, updated: str}
        """
        strip = Image.new('RGB', (WIDTH, STRIP_HEIGHT), (0, 0, 0))
        if strip_data is None:
            return strip

        draw = ImageDraw.Draw(strip)
        font_large = _load_font(36)
        font_small = _load_font(28)
        white = (255, 255, 255)

        LEFT_X = 20
        RIGHT_MAX_X = WIDTH - 20
        y_positions = [10, 52, 94]  # three text rows

        # --- LEFT: weather (row 0) + transit (rows 1-2) ---
        weather = strip_data.get('weather') or {}
        if weather:
            temp = weather.get('temp', '')
            city = weather.get('city', '')
            cond = weather.get('condition', '')
            parts = [p for p in [
                f"{temp}°C" if temp != '' else None,
                city or None,
                cond or None,
            ] if p]
            draw.text((LEFT_X, y_positions[0]), '  '.join(parts), font=font_large, fill=white)

        transit = strip_data.get('transit') or []
        for i, dep in enumerate(transit[:2]):
            row = y_positions[i + 1]
            t = dep.get('time', '')
            delay = dep.get('delay', 0)
            delay_str = 'on time' if delay == 0 else f'+{delay} min'
            draw.text((LEFT_X, row), f'S8  {t}  {delay_str}', font=font_small, fill=white)

        # --- RIGHT: Pi stats (right-aligned) ---
        pi = strip_data.get('pi') or {}
        right_lines = []
        if pi.get('ip'):
            right_lines.append(pi['ip'])
        if pi.get('cpu_temp') is not None:
            right_lines.append(f"CPU {pi['cpu_temp']}°C")
        if pi.get('updated'):
            right_lines.append(f"updated {pi['updated']}")

        for i, line in enumerate(right_lines[:3]):
            font = font_large if i == 0 else font_small
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((RIGHT_MAX_X - text_w, y_positions[i]), line, font=font, fill=white)

        return strip

    def compose(self, image: Image.Image, strip_data=None) -> Image.Image:
        """Fit + quantize photo, render strip, compose into 1200x1600."""
        photo = self.fit_image(image)

        # Render strip before quantizing so we can paste it unquantized first
        strip = self.render_strip(strip_data)

        # Compose full canvas in RGB
        canvas = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
        canvas.paste(photo, (0, 0))
        canvas.paste(strip, (0, PHOTO_HEIGHT))

        # Quantize the entire canvas to 6-color palette
        return self.quantize_6color(canvas)
