"""Past-signal replay for the Kite triple-SuperTrend engine.

Replays the SAME regime/transition logic the live scanner uses, but collects EVERY
entry transition inside a date window (today / week / 15d / month / custom) instead
of only the latest closed bar — so the user can see what fired today (or recently)
and verify the engine is working on indices. Pure functions here (candles in,
signals out); the async fetch orchestration lives on the scanner.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

import numpy as np

from app.domain.models import Candle
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.engines.triple_supertrend.schemas import HistorySignal
from app.services.kite_engine.strikes import OptionPick
from app.services.kite_engine.universe import UniverseItem

_IST = timezone(timedelta(hours=5, minutes=30))
_DAY_MS = 86_400_000


def duration_window(duration: str, now_ms: int) -> Tuple[int, int]:
    """Map a duration keyword → (from_ms, to_ms). ``to`` is always ``now``.

    today = since IST midnight; week/15d/month = trailing N days.
    """
    d = (duration or "").lower()
    if d == "today":
        midnight = datetime.fromtimestamp(now_ms / 1000, _IST).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return int(midnight.timestamp() * 1000), now_ms
    days = {"week": 7, "15d": 15, "month": 30}.get(d, 7)
    return now_ms - days * _DAY_MS, now_ms


def _entries_in_window(
    candles: Sequence[Candle], cfg: TripleSupertrendConfig, *,
    from_ms: int, to_ms: int, longs_only: bool,
):
    """(closes, trail_line, [(i, direction)…], last_index) or None if too few bars."""
    if len(candles) <= cfg.warmup + 1:
        return None
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    line = r.line(cfg.trail_target)
    out: List[Tuple[int, str]] = []
    for i in range(len(candles)):
        ts = int(candles[i].timestamp_ms)
        if ts < from_ms or ts > to_ms:
            continue
        if longs[i]:
            out.append((i, "long"))
        elif shorts[i] and not longs_only:
            out.append((i, "short"))
    return c, line, out, len(candles) - 1


def spot_history_signals(
    item: UniverseItem, candles: Sequence[Candle], cfg: TripleSupertrendConfig, *,
    from_ms: int, to_ms: int,
) -> List[HistorySignal]:
    """Underlying-chart entries in the window (long→CE, short→PE)."""
    res = _entries_in_window(candles, cfg, from_ms=from_ms, to_ms=to_ms, longs_only=False)
    if res is None:
        return []
    c, line, entries, last = res
    return [
        HistorySignal(
            ts_ms=int(candles[i].timestamp_ms), underlying=item.name, source="spot",
            direction=d, option_type="CE" if d == "long" else "PE",
            entry_price=float(c[i]), stop_loss=float(line[i]), is_now=(i == last),
        )
        for i, d in entries
    ]


def deriv_history_signals(
    item: UniverseItem, moneyness: str, pick: OptionPick,
    candles: Sequence[Candle], cfg: TripleSupertrendConfig, *, from_ms: int, to_ms: int,
) -> List[HistorySignal]:
    """Option-premium-chart BUY entries in the window (uptrend transitions only)."""
    res = _entries_in_window(candles, cfg, from_ms=from_ms, to_ms=to_ms, longs_only=True)
    if res is None:
        return []
    c, line, entries, last = res
    return [
        HistorySignal(
            ts_ms=int(candles[i].timestamp_ms), underlying=item.name, source="derivatives",
            direction="long", option_type=pick.option_type, option_symbol=pick.option_symbol,
            moneyness=moneyness, entry_price=float(c[i]), stop_loss=float(line[i]),
            is_now=(i == last),
        )
        for i, _d in entries
    ]
