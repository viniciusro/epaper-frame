"""
Generate favicon.ico for the e-paper digital photo frame web UI.

Produces a multi-size .ico (16x16, 32x32, 48x48) with:
- Dark background (#111111)
- White/light-gray picture frame border
- Warm-colored inner rectangle suggesting a photo
"""

from PIL import Image, ImageDraw
import pathlib


def draw_frame_icon(size: int) -> Image.Image:
    """Draw the picture-frame icon at the given square pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- background ---
    bg_color = (17, 17, 17, 255)          # #111111
    draw.rectangle([0, 0, size - 1, size - 1], fill=bg_color)

    # Proportional margins (all values scale with `size`)
    s = size

    # Outer frame rect (rounded slightly via a 1-px inset from the edge)
    outer_margin = max(1, round(s * 0.06))
    frame_color = (220, 220, 220, 255)    # light gray, nearly white
    frame_thickness = max(1, round(s * 0.10))  # border width

    ox0, oy0 = outer_margin, outer_margin
    ox1, oy1 = s - 1 - outer_margin, s - 1 - outer_margin

    # Draw filled outer rect then carve out the inner area to make a frame border
    draw.rectangle([ox0, oy0, ox1, oy1], fill=frame_color)

    # Inner rect (the "glass" / photo area) — dark so the photo pop stands out
    ix0 = ox0 + frame_thickness
    iy0 = oy0 + frame_thickness
    ix1 = ox1 - frame_thickness
    iy1 = oy1 - frame_thickness

    inner_bg = (30, 30, 30, 255)
    if ix1 > ix0 and iy1 > iy0:
        draw.rectangle([ix0, iy0, ix1, iy1], fill=inner_bg)

    # Small photo suggestion: a warm yellow/orange rectangle inside the frame
    # Positioned slightly off-center toward the bottom to feel like a landscape photo
    photo_margin = max(1, round(s * 0.06))
    px0 = ix0 + photo_margin
    py0 = iy0 + photo_margin
    px1 = ix1 - photo_margin
    py1 = iy1 - photo_margin

    if px1 > px0 and py1 > py0:
        photo_color = (255, 180, 40, 255)   # warm amber/orange
        draw.rectangle([px0, py0, px1, py1], fill=photo_color)

        # Optional: tiny darker line across the lower third of the photo rect
        # to hint at a horizon / landscape subject — only at 32px+
        if size >= 32:
            horizon_y = py0 + round((py1 - py0) * 0.62)
            sky_color = (100, 170, 230, 255)   # soft blue sky hint
            draw.rectangle([px0, py0, px1, horizon_y], fill=sky_color)

    return img


def main():
    sizes = [16, 32, 48]
    images = [draw_frame_icon(sz) for sz in sizes]

    out_path = pathlib.Path(__file__).parent / "web" / "static" / "favicon.ico"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Pillow requires the `sizes` kwarg to list ALL desired dimensions and the
    # source image must be large enough (or exactly matching) each target size.
    # The cleanest approach: pass the largest image and let Pillow downsample,
    # explicitly listing every size we want embedded in the .ico container.
    largest = images[-1]   # 48x48
    largest.save(
        out_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
    )
    print(f"Saved {out_path}  ({', '.join(str(s)+'px' for s in sizes)})")


if __name__ == "__main__":
    main()
