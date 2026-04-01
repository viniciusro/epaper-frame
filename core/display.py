import os


class Display:
    WIDTH = 1200
    HEIGHT = 1600
    MOCK = os.environ.get('EPAPER_MOCK', '0') == '1'

    def show(self, image):
        raise NotImplementedError
