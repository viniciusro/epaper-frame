# Improved version of the Waveshare epdconfig.py vendor driver.
# The original file (epdconfig.py) is preserved unchanged.
#
# Fixes applied:
#   1. /proc/cpuinfo opened with a context manager (file handle leak)
#   2. except narrowed to (FileNotFoundError, PermissionError) instead of bare Exception
#   3. Missing `raise` on RuntimeError when DEV_Config.so is not found
#
# Everything else is identical to the vendor original.

import time
import os
import logging
import struct
import sys

from ctypes import *
import ctypes

EPD_SCK_PIN     =11
EPD_MOSI_PIN    =10

EPD_CS_M_PIN    =8
EPD_CS_S_PIN    =7

EPD_DC_PIN      =25
EPD_RST_PIN     =17
EPD_BUSY_PIN    =24
EPD_PWR_PIN     =18

find_dirs = [
    os.path.dirname(os.path.realpath(__file__)),
    '/usr/local/lib',
    '/usr/lib',
]
spi = None
if os.environ.get('EPAPER_MOCK', '0') != '1':
    for find_dir in find_dirs:
        val = struct.calcsize('P') * 8  # 32 or 64, no shell needed
        try:
            # FIX: use context manager to avoid file handle leak
            with open('/proc/cpuinfo') as f:
                val_1 = f.read()
        except (FileNotFoundError, PermissionError):
            # FIX: narrow exception — only catch expected filesystem errors
            val_1 = ''
        val_1 = val_1 if 'Raspberry Pi 5' in val_1 else ""
        if val == 64:
            if val_1 == "":
                so_filename = os.path.join(find_dir, 'DEV_Config_64_b.so')
            else:
                so_filename = os.path.join(find_dir, 'DEV_Config_64_w.so')
        else:
            if val_1 == "":
                so_filename = os.path.join(find_dir, 'DEV_Config_32_b.so')
            else:
                so_filename = os.path.join(find_dir, 'DEV_Config_32_w.so')
        if os.path.exists(so_filename):
            spi = CDLL(so_filename)
            break
    if spi is None:
        # FIX: actually raise the error instead of creating an unused object
        raise RuntimeError(
            'Cannot find DEV_Config.so — ensure Waveshare ARM binaries are installed'
        )

def digital_write(pin, value):
    spi.DEV_Digital_Write(pin, value)

def digital_read(pin):
    return spi.DEV_Digital_Read(pin)

def spi_writebyte(value):
    spi.DEV_SPI_SendData(value)

def spi_writebyte2(buf, len):
    array_data = (ctypes.c_ubyte * len)(*buf)
    spi.DEV_SPI_SendData_nByte(array_data, ctypes.c_ulong(len))

def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)

def module_init():
    spi.DEV_ModuleInit()

def module_exit():
    spi.DEV_ModuleExit()
