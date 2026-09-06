"""
Observability (Phase 2) — structured JSON logging + correlation IDs.

ADDITIVE and opt-in. The existing plain-text `setup_logging()` and the UI
`WsLogHandler` in app/core/logging.py are NOT modified. New code can:

  * tag a request/trade flow with a correlation id (contextvar-based), and
  * optionally switch the root handler to JSON via configure_json_logging().

JSON logging is enabled only when settings.log_json is true (default False),
so default runtime behavior is identical to before.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

# ── correlation id (per async-task / per-thread via contextvars) ───────────
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """Return a fresh short unique id (does not bind it)."""
    return uuid.uuid4().hex[:16]


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def set_correlation_id(cid: str) -> Token:
    """Bind a correlation id; returns a token for reset_correlation_id()."""
    return _correlation_id.set(cid)


def reset_correlation_id(token: Token) -> None:
    _correlation_id.reset(token)


@contextmanager
def correlation_scope(cid: Optional[str] = None) -> Iterator[str]:
    """Bind `cid` (or a fresh one) for the duration of the block."""
    cid = cid or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)


# ── JSON formatter ─────────────────────────────────────────────────────────
# Standard LogRecord attributes we don't want to duplicate into "extra".
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message", "asctime", "taskName",
}


class JsonLogFormatter(logging.Formatter):
    """Render a LogRecord as a single JSON line, including the correlation id
    (when bound) and any structured `extra=` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": _dt.datetime.fromtimestamp(
                record.created, tz=_dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid is not None:
            payload["correlation_id"] = cid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any user-supplied extras (e.g. log.info("x", extra={"symbol": "NIFTY"}))
        for key, val in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str)


def configure_json_logging(level: Optional[str] = None, force: bool = False) -> bool:
    """Opt-in: switch the root logger to JSON output on stdout.

    No-op unless `force` is True or settings.log_json is enabled, so importing
    this module never changes default behavior. Returns True if applied.
    """
    if not force:
        try:
            from app.core.config import settings
            if not getattr(settings, "log_json", False):
                return False
            level = level or settings.log_level
        except Exception:
            return False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.StreamHandler)]
    root.addHandler(handler)
    if level:
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
    return True
