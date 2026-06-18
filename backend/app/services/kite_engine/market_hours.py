"""NSE/BSE market hours check.

Trading hours: 9:15 AM – 3:30 PM IST, Monday–Friday.
Uses Asia/Kolkata timezone (UTC+5:30).
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

_TRADING_START = time(9, 15)
_TRADING_END = time(15, 30)


def is_market_open(now: datetime | None = None) -> bool:
    """True if the Indian equity/derivatives market is currently in session."""
    t = (now or datetime.now(_IST)).astimezone(_IST)
    if t.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    return _TRADING_START <= t.time() <= _TRADING_END
