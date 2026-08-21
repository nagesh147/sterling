"""Session-boundary arithmetic, kept in one place.

The strategy needs to know when the session opened in order to date a quote. That
is a calendar question, not a strategy question, so it lives here rather than
being recomputed at each call site with a slightly different timezone assumption.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def parse_hhmm(value: str) -> tuple[int, int]:
    hh, mm = str(value).split(":")
    return int(hh), int(mm)


def session_open_ms_for(now_ms: int, session_start: str = "09:15") -> int:
    """Epoch ms of ``session_start`` IST on the day containing ``now_ms``.

    Anchored on the IST calendar date of ``now_ms`` rather than on UTC, because a
    session that opens at 09:15 IST spans a single Indian trading day and the UTC
    date rolls over mid-session for no useful reason.
    """
    hh, mm = parse_hhmm(session_start)
    local = datetime.fromtimestamp(int(now_ms) / 1000, tz=IST)
    opened = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return int(opened.timestamp() * 1000)


def session_close_ms_for(now_ms: int, session_end: str = "15:25") -> int:
    """Epoch ms of ``session_end`` IST on the day containing ``now_ms``.

    Same anchoring as :func:`session_open_ms_for`. Exists because a position that
    outlives the session is a different risk from the one that was taken on: held
    to expiry, a bought option can settle worthless.
    """
    hh, mm = parse_hhmm(session_end)
    local = datetime.fromtimestamp(int(now_ms) / 1000, tz=IST)
    closed = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return int(closed.timestamp() * 1000)
