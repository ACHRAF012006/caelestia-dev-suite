import logging
from logging.handlers import RotatingFileHandler
from utils.paths import checked, state_dir


def setup():
    path = checked(state_dir() / "touchdeck.log")
    for number in range(1, 4):
        checked(path.with_name(path.name + "." + str(number)))
    handler = RotatingFileHandler(path, maxBytes=256000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("touchdeck")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return path
