# Improved version of the Waveshare epd13in3E.py vendor driver.
# The original file (epd13in3E.py) is preserved unchanged.
#
# Fixes applied:
#   1. ReadBusyH: adds 30-second timeout — prevents infinite hang on stuck hardware
#   2. getbuffer: raises ValueError on wrong image dimensions instead of crashing with NameError
#   3. Clear: pre-allocates the line buffer once instead of 1600 times per call
#   4. __enter__/__exit__: context manager guarantees Init/sleep pairing
#
# All inherited methods (Init, Reset, SendCommand, display, sleep, etc.) are
# unchanged from the vendor original but are redirected to use epdconfig_improved
# via the monkey-patch below.

import time
import logging

import drivers.epd13in3E as _vendor_module
import drivers.epdconfig_improved as epdconfig_improved

# Monkey-patch the vendor module's epdconfig reference so that all inherited
# methods (Init, Reset, TurnOnDisplay, display, sleep, etc.) use the improved
# config rather than the original buggy one.
_vendor_module.epdconfig = epdconfig_improved

from drivers.epd13in3E import EPD as _VendorEPD

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_SEC = 30  # Maximum seconds to wait for display refresh completion


class EPD(_VendorEPD):
    """Improved EPD driver for 13.3" Spectra 6 (1200x1600, 6-color).

    Wraps the vendor EPD class with targeted bug fixes. Original vendor files
    (epd13in3E.py, epdconfig.py) are untouched.
    """

    def ReadBusyH(self):
        """Wait for display to become idle.

        Raises TimeoutError if the display stays busy longer than BUSY_TIMEOUT_SEC.
        The vendor original loops forever with no timeout.
        """
        logger.debug("e-Paper busy H")
        deadline = time.monotonic() + BUSY_TIMEOUT_SEC
        while epdconfig_improved.digital_read(self.EPD_BUSY_PIN) == 0:  # 0: busy, 1: idle
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Display stayed busy for >{BUSY_TIMEOUT_SEC}s — hardware may be stuck"
                )
            epdconfig_improved.delay_ms(5)
        logger.debug("e-Paper busy H release")

    def getbuffer(self, image):
        """Convert a PIL image to the 4-bit display buffer.

        Raises ValueError on wrong image dimensions.
        The vendor original logs an error but continues, causing a NameError crash.
        """
        from PIL import Image
        pal_image = Image.new("P", (1, 1))
        # Palette order: Black, White, Yellow, Red, Black (slot 4 unused — driver
        # ordering requirement), Blue, Green. Remaining 249 slots padded with black.
        pal_image.putpalette(
            (0,0,0,  255,255,255,  255,255,0,  255,0,0,  0,0,0,  0,0,255,  0,255,0)
            + (0,0,0) * 249
        )

        imwidth, imheight = image.size
        if imwidth == self.width and imheight == self.height:
            image_temp = image
        elif imwidth == self.height and imheight == self.width:
            image_temp = image.rotate(90, expand=True)
        else:
            raise ValueError(
                f"Invalid image dimensions: {imwidth}x{imheight}, "
                f"expected {self.width}x{self.height} or {self.height}x{self.width}"
            )

        # Quantize to 7-color palette (dithering if needed)
        image_7color = image_temp.convert("RGB").quantize(palette=pal_image)
        buf_7color = bytearray(image_7color.tobytes('raw'))

        # Pack two 4-bit color indices per byte for SPI transfer
        buf = [0x00] * int(self.width * self.height / 2)
        idx = 0
        for i in range(0, len(buf_7color), 2):
            buf[idx] = (buf_7color[i] << 4) + buf_7color[i + 1]
            idx += 1
        return buf

    def Clear(self, color=0x11):
        """Blank the display to a solid color.

        Pre-allocates the line buffer once instead of on every row iteration.
        The vendor original creates [color]*600 on each of the 3200 loop iterations.
        """
        line = [color] * int(self.width / 2)
        line_len = len(line)

        epdconfig_improved.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x10)
        for _ in range(self.height):
            epdconfig_improved.spi_writebyte2(line, line_len)
        self.CS_ALL(1)

        epdconfig_improved.digital_write(self.EPD_CS_S_PIN, 0)
        self.SendCommand(0x10)
        for _ in range(self.height):
            epdconfig_improved.spi_writebyte2(line, line_len)
        self.CS_ALL(1)

        self.TurnOnDisplay()

    def __enter__(self):
        """Initialize the display and return self."""
        self.Init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Put the display to sleep regardless of whether an exception occurred."""
        self.sleep()
        return False  # do not suppress exceptions
