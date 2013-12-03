
from . import ejsons
import ejson
import os


class EJsonConfig(dict):
    _file = None

    def __init__(self, filename):
        self._file = filename
        self.load()

    def load(self):
        self.clear()
        if os.path.isfile(self._file):
            with file(self._file, 'r') as f:
                raw = f.read()
                if raw:
                    data = ejson.loads(raw)
                    self.update(data)

    def save(self):
        raw = ejson.dumps(self, indent=4)
        with file(self._file, 'w') as f:
            f.write(raw)
