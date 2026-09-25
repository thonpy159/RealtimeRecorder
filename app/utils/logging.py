import logging
from logging.handlers import RotatingFileHandler


def configure_logging(root):
    root.mkdir(exist_ok=True)
    handler = RotatingFileHandler(root / 'app.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
