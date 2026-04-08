import os
import tempfile
import logging
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Palette used for test_pattern — matches EPD 6-color palette
_COLORS = [
    ((0, 0, 0), 'Black'),
    ((255, 255, 255), 'White'),
    ((255, 255, 0), 'Yellow'),
    ((255, 0, 0), 'Red'),
    ((0, 0, 255), 'Blue'),
    ((0, 255, 0), 'Green'),
]


class Display:
    WIDTH = 1200
    HEIGHT = 1600

    @property
    def MOCK(self):
        """Read EPAPER_MOCK at call time so it works when set after import."""
        return os.environ.get('EPAPER_MOCK', '0') == '1'

    def show(self, image: Image.Image):
        out = os.path.join(tempfile.gettempdir(), 'epaper_preview.png')
        image.save(out)
        if self.MOCK:
            logger.info('[MOCK] Saved preview to %s', out)
            return
        logger.info('Saved preview to %s', out)
        from drivers.epd13in3E import EPD
        epd = EPD()
        epd.Init()
        epd.display(epd.getbuffer(image))
        epd.sleep()

    def sleep(self):
        if self.MOCK:
            logger.info('[MOCK] Display sleep (no-op)')
            return
        from drivers.epd13in3E import EPD
        epd = EPD()
        epd.sleep()

    def clear(self):
        """Blank the display to white (used during sleep schedule)."""
        self.show(Image.new('RGB', (self.WIDTH, self.HEIGHT), (255, 255, 255)))

    def test_pattern(self):
        """Render 6 color blocks across the full display area."""
        img = Image.new('RGB', (self.WIDTH, self.HEIGHT), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        block_w = self.WIDTH // len(_COLORS)
        for i, (color, _) in enumerate(_COLORS):
            draw.rectangle(
                [i * block_w, 0, (i + 1) * block_w - 1, self.HEIGHT - 1],
                fill=color,
            )
        self.show(img)
        return img
