import logging
import yaml
from core.frame_controller import FrameController

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    controller = FrameController(config)
    controller.run()
