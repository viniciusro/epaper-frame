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
            'cpu_load': _get_cpu_load(),
            'disk_used_pct': _get_disk_used_pct(),
            'core_voltage': _get_core_voltage(),
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


def _get_cpu_load():
    """Return 1-minute CPU load average as a percentage (0-100), or None."""
    try:
        import os
        load1, _, _ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        return round(load1 / cpu_count * 100, 1)
    except Exception:
        return None


def _get_disk_used_pct():
    """Return used percentage of the root filesystem (SD card), or None."""
    try:
        import shutil
        usage = shutil.disk_usage('/')
        return round(usage.used / usage.total * 100, 1)
    except Exception:
        return None


def _get_core_voltage():
    """Return core voltage in volts via vcgencmd, or None if unavailable."""
    try:
        import subprocess
        result = subprocess.run(
            ['/usr/bin/vcgencmd', 'measure_volts', 'core'],
            capture_output=True, text=True, timeout=3,
        )
        # output: "volt=1.2000V\n"
        raw = result.stdout.strip()
        if raw.startswith('volt=') and raw.endswith('V'):
            return float(raw[5:-1])
    except Exception:
        pass
    return None
