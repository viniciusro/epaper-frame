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
    """Return the first non-loopback IPv4 address, or fallback to gethostbyname."""
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for addr in addrs:
                ip = addr.get('addr', '')
                if ip and not ip.startswith('127.'):
                    return ip
    except ImportError:
        pass
    # Fallback: connect UDP to trigger OS routing and read source IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
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
