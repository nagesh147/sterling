import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

import asyncio
log_queue = None

class WsLogHandler(logging.Handler):
    def emit(self, record):
        global log_queue
        if log_queue is None:
            return
        try:
            msg = self.format(record)
            # Try to push to queue from threadsafe mechanism if possible, but put_nowait is ok for same thread
            # Or better, just get the running loop
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(log_queue.put_nowait, {"type": "log", "message": msg, "level": record.levelname, "name": record.name})
        except Exception:
            pass

def attach_ws_logger():
    global log_queue
    if log_queue is None:
        log_queue = asyncio.Queue()
    root = logging.getLogger()
    handler = WsLogHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    root.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

