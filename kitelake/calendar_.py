"""Trading sessions and holidays — used for *expectations*, never to gate fetching.

Two jobs:

1. Frame each API request so a chunk covers whole sessions (asking for ``00:00:00`` to
   ``00:00:00`` would clip the last day's bars).
2. Tell coverage/gap reporting how many bars a range *should* contain, so a genuinely
   missing day is distinguishable from a market holiday.

Deliberately permissive: session windows are upper bounds, and an unknown year falls
back to "weekdays only". A too-narrow window would make the verifier cry wolf on every
special session, which is worse than missing a holiday. Nothing here ever prevents a
download attempt — if we are wrong about a holiday, Kite simply returns no candles and
the chunk is recorded as ``empty``.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Iterable

from .config import IST, SECOND_INTERVAL

__all__ = [
    "NSE_HOLIDAYS_2026",
    "holidays",
    "is_session_day",
    "session_days",
    "session_bounds",
    "session_minutes",
    "interval_minutes",
    "expected_bars",
]

#: Verified NSE **equity segment** trading holidays for 2026 (Zerodha holiday calendar,
#: cross-checked against multiple broker publications, 2026-08-13). Dates falling on a
#: weekend are omitted — they are already non-sessions.
#:
#: Only 2026 is listed because that is the only year we verified. Any other year falls
#: back to weekdays-only, which over-counts expected days on ~15 dates a year; override
#: by dropping ``instruments/holidays.txt`` (one ``YYYY-MM-DD`` per line) into the lake.
NSE_HOLIDAYS_2026: frozenset[date] = frozenset(
    {
        date(2026, 1, 15),   # Municipal Corporation Elections, Maharashtra
        date(2026, 1, 26),   # Republic Day
        date(2026, 3, 3),    # Holi
        date(2026, 3, 26),   # Shri Ram Navami
        date(2026, 3, 31),   # Shri Mahavir Jayanti
        date(2026, 4, 3),    # Good Friday
        date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
        date(2026, 5, 1),    # Maharashtra Day
        date(2026, 5, 28),   # Bakri Eid
        date(2026, 6, 26),   # Moharram
        date(2026, 9, 14),   # Ganesh Chaturthi
        date(2026, 10, 2),   # Mahatma Gandhi Jayanti
        date(2026, 10, 20),  # Dussehra
        date(2026, 11, 10),  # Diwali-Balipratipada
        date(2026, 11, 24),  # Prakash Gurpurb Sri Guru Nanak Dev
        date(2026, 12, 25),  # Christmas
    }
)

#: Session windows in IST, per exchange, as (open, close). Upper bounds by design.
_SESSIONS: dict[str, tuple[time, time]] = {
    "NSE": (time(9, 15), time(15, 30)),
    "BSE": (time(9, 15), time(15, 30)),
    "NFO": (time(9, 15), time(15, 30)),
    "BFO": (time(9, 15), time(15, 30)),
    "CDS": (time(9, 0), time(17, 0)),
    "BCD": (time(9, 0), time(17, 0)),
    "MCX": (time(9, 0), time(23, 30)),
    "NCO": (time(9, 0), time(23, 30)),
}
_DEFAULT_SESSION = (time(9, 0), time(23, 30))


@lru_cache(maxsize=4)
def _override_holidays() -> frozenset[date]:
    """Read ``instruments/holidays.txt`` from the lake, if reachable."""
    try:
        from .volume import instruments_dir

        path = instruments_dir(create=False) / "holidays.txt"
        text = path.read_text()
    except Exception:
        # No lake, no file, unreadable — all mean "no overrides", never an error.
        return frozenset()
    out: set[date] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            out.add(date.fromisoformat(line))
        except ValueError:
            continue
    return frozenset(out)


def holidays(exchange: str = "NSE") -> frozenset[date]:
    """Known full-day closures. MCX keeps its own calendar; we only special-case NSE/BSE."""
    override = _override_holidays()
    if override:
        return override
    if exchange.upper() in {"MCX", "NCO"}:
        # Commodity segments trade on several equity holidays; claiming otherwise would
        # under-count expected days. Weekend-only is the safer expectation here.
        return frozenset()
    return NSE_HOLIDAYS_2026


def is_session_day(day: date, exchange: str = "NSE") -> bool:
    """Weekday and not a known holiday."""
    if day.weekday() >= 5:
        return False
    return day not in holidays(exchange)


def session_days(frm: date, to: date, exchange: str = "NSE") -> list[date]:
    """Every expected trading day in the inclusive range ``[frm, to]``."""
    if to < frm:
        return []
    out: list[date] = []
    day = frm
    while day <= to:
        if is_session_day(day, exchange):
            out.append(day)
        day += timedelta(days=1)
    return out


def session_bounds(day: date, exchange: str = "NSE") -> tuple[datetime, datetime]:
    """IST-aware (open, close) datetimes for ``day`` on ``exchange``."""
    start, end = _SESSIONS.get((exchange or "").upper(), _DEFAULT_SESSION)
    return (
        datetime.combine(day, start, tzinfo=IST),
        datetime.combine(day, end, tzinfo=IST),
    )


def session_minutes(exchange: str = "NSE") -> int:
    """Length of one session in minutes (375 for NSE equity)."""
    start, end = _SESSIONS.get((exchange or "").upper(), _DEFAULT_SESSION)
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def interval_minutes(interval: str) -> float:
    """Minutes per bar. ``day`` is a whole session; ``second`` is 1/60."""
    if interval == "day":
        return float(session_minutes())
    if interval == SECOND_INTERVAL:
        return 1.0 / 60.0
    if interval == "minute":
        return 1.0
    if interval.endswith("minute"):
        return float(interval[: -len("minute")])
    raise ValueError(f"cannot size interval {interval!r}")


def expected_bars(frm: date, to: date, interval: str, exchange: str = "NSE") -> int:
    """Upper-bound bar count for a range — the denominator for completeness percentages.

    An upper bound, not a promise: illiquid instruments legitimately have no trade in a
    given minute and Kite omits that candle entirely, so a stock at 8% completeness is
    usually thin, not broken.
    """
    days = len(session_days(frm, to, exchange))
    if not days:
        return 0
    if interval == "day":
        return days
    per_day = session_minutes(exchange) / interval_minutes(interval)
    return int(days * per_day)
