import logging
import sys
from pathlib import Path

import yaml

LOG_DIR = Path('logs')
LOG_FILE = LOG_DIR / 'epaper-frame.log'


def _setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


if __name__ == '__main__':
    _setup_logging()
    logger = logging.getLogger(__name__)

    cfg_path = Path('config.yaml')
    if not cfg_path.exists():
        logger.error('config.yaml not found — copy config.yaml.example and fill in values')
        sys.exit(1)

    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    logger.info('Starting epaper-frame')

    from core.frame_controller import FrameController
    controller = FrameController(config)
    controller.run()
