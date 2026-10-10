"""Bounded, redacted manager logs, separate from independent application stdout."""
import logging
import json
from logging.handlers import RotatingFileHandler
from backend.dependencies import clean_output
from backend.paths import no_symlinks


class Redacted(logging.Formatter):
    def format(self, record):
        return json.dumps({'time': self.formatTime(record), 'level': record.levelname,
                           'category': getattr(record, 'category', 'manager'), 'message': clean_output(record.getMessage())})


def logger(directory):
    directory = no_symlinks(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = no_symlinks(directory / 'manager.log')
    for i in range(1, 4): no_symlinks(directory / f'manager.log.{i}')
    result = logging.getLogger('cdm.' + str(path))
    if not result.handlers:
        handler = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
        handler.setFormatter(Redacted('%(asctime)s %(levelname)s %(message)s'))
        path.chmod(0o600)
        result.addHandler(handler); result.setLevel(logging.INFO); result.propagate = False
    return result
