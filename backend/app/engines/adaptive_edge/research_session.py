"""Operational NSE session clock used by the tick acquirer.

Not a recovered F-103/F-110 formula. Label: IMPLEMENTATION ASSUMPTION.
Session 09:15–15:30 IST weekdays matches tick_history.py, not a TrueData v2.6 contract.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)

# A126: new entries forbidden and open positions flatten 45 minutes before session close.
A126_CUTOFF_BEFORE_CLOSE = timedelta(minutes=45)


def nse_regular_session(decision_time: str) -> bool:
    parsed = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {decision_time}")
    local = parsed.astimezone(IST)
    if local.weekday() >= 5:
        return False
    clock = local.timetz().replace(tzinfo=None)
    return SESSION_OPEN <= clock < SESSION_CLOSE


def session_zone_name() -> str:
    return IST.key if isinstance(IST, ZoneInfo) else "Asia/Kolkata"


def session_date_ist(decision_time: str) -> str:
    """Calendar date in the operational session zone. Not an F-103 threshold."""
    parsed = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {decision_time}")
    return parsed.astimezone(IST).date().isoformat()


def minutes_until_a126_cutoff(decision_time: str) -> float:
    """Minutes remaining before A126 cutoff. Zero if cutoff already reached."""
    parsed = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {decision_time}")
    local = parsed.astimezone(IST)
    close_dt = datetime.combine(local.date(), SESSION_CLOSE, tzinfo=IST)
    cutoff = close_dt - A126_CUTOFF_BEFORE_CLOSE
    return max(0.0, (cutoff - local).total_seconds() / 60.0)


def a126_session_cutoff_reached(decision_time: str) -> bool:
    """True at/after SESSION_CLOSE - 45m (A126). Not an F-111 prediction threshold."""
    parsed = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {decision_time}")
    local = parsed.astimezone(IST)
    close_dt = datetime.combine(local.date(), SESSION_CLOSE, tzinfo=IST)
    cutoff = close_dt - A126_CUTOFF_BEFORE_CLOSE
    return local >= cutoff
