#!/usr/bin/env python3
"""Generate PWA icons for epaper-frame. Safe to re-run."""
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Pillow is required: pip install Pillow")

OUT_DIR = Path(__file__).parent.parent / 'web' / 'static' / 'icons'
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG_COLOR = (30, 30, 30)      # #1e1e1e
FG_COLOR = (255, 255, 255)   # white
TEXT = 'eF'
SIZES = [192, 512]


def make_icon(size: int) -> None:
    img = Image.new('RGB', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_size = int(size * 0.45)
    font = None
    for font_path in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        'C:/Windows/Fonts/arialbd.ttf',
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except Exception:
                pass

    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), TEXT, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    draw.text((x, y), TEXT, fill=FG_COLOR, font=font)

    out_path = OUT_DIR / f'icon-{size}.png'
    img.save(str(out_path), 'PNG')
    print(f'  wrote {out_path}')


for sz in SIZES:
    make_icon(sz)
print('Icons generated.')
