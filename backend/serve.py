"""Run the API server with a size-capped log file.

`manage.py` starts the server through this module (instead of `python -m
uvicorn` with stdout redirected to a file) so `.server.log` rotates: it is kept
under ~1 MB per file, with 3 old copies. print() output and tracebacks are
captured into the same log.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = BASE_DIR / ".server.log"
MAX_BYTES = 1_000_000
BACKUPS = 3


class _StreamToLog:
    """File-like object that sends whatever is written to it to the logger."""

    def __init__(self, logger, level):
        self.logger, self.level = logger, level

    def write(self, text):
        for line in text.rstrip().splitlines():
            self.logger.log(self.level, line)
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


def setup_logging():
    handler = RotatingFileHandler(LOG_PATH, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    sys.stdout = _StreamToLog(logging.getLogger("stdout"), logging.INFO)
    sys.stderr = _StreamToLog(logging.getLogger("stderr"), logging.ERROR)


def main(host="127.0.0.1", port=8000):
    setup_logging()
    # log_config=None: keep our handler instead of uvicorn's console one.
    uvicorn.run("backend.api:app", host=host, port=port, log_config=None)


if __name__ == "__main__":
    main(*(int(a) if a.isdigit() else a for a in sys.argv[1:]))
