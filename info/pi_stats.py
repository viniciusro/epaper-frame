import logging
import socket
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMP_PATH = Path('/sys/class/thermal/thermal_zone0/temp')


class PiStats:
    def fetch(self):
        return {
            'ip': _get_ip(),
            'cpu_temp': _get_cpu_temp(),
            'hostname': socket.gethostname(),
            'updated': datetime.now().strftime('%H:%M'),
        }


def _get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return '0.0.0.0'


def _get_cpu_temp():
    try:
        raw = _TEMP_PATH.read_text().strip()
        return round(int(raw) / 1000, 1)
    except Exception:
        return None
