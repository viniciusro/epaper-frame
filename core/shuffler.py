class Shuffler:
    def __init__(self, config, sources):
        self.config = config
        self.sources = sources

    def next(self):
        raise NotImplementedError
