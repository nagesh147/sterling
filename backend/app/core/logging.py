import logging
import sys
from collections import deque
from app.core.config import settings


# ── In-memory ring buffer of recent server logs ──────────────────────────────
# Lets the UI (Kite Terminal) interleave real backend logs with engine activity
# without writing/tailing a file. Bounded so it can never grow unbounded.
_LOG_RING: "deque[dict]" = deque(maxlen=1000)


class RingBufferLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _LOG_RING.append({
                "ts_ms": int(record.created * 1000),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            })
        except Exception:
            pass


def attach_ring_logger() -> None:
    root = logging.getLogger()
    if any(isinstance(h, RingBufferLogHandler) for h in root.handlers):
        return
    root.addHandler(RingBufferLogHandler())


def recent_logs(limit: int = 300) -> list[dict]:
    items = list(_LOG_RING)
    return items[-limit:] if limit and limit > 0 else items


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    attach_ring_logger()

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

