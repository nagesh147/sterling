"""The entry rule: open interest falling while volume and premium rise.

Measured behaviour, on 167,253 evaluable bars from 598 NSE stock-option
contracts (see ``config`` and the validation report):

* the triple **on its own** did not separate from the unconditional population
  -- 24.7% [20.9, 28.9] of triggered bars reached a 30% favourable excursion
  within two sessions, against 21.7% [21.5, 21.9] for every bar;
* restricted to bars where spot sat within 1% of a confirmed level it reached
  45.0% [30.7, 60.2].

So this module is a *necessary* condition, not a sufficient one, and the caller
must apply the level filter before treating a trigger as a setup. Nothing here
enforces that -- ``strategy.py`` does -- but any future caller reading only this
file needs to know it is holding half a rule.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from .config import GammaMoveConfig
from .models import OICandle, TriggerMetrics

_IST = timezone(timedelta(hours=5, minutes=30))


def session_day(ts_ms: int) -> str:
    """The IST trading day a bar belongs to."""
    return datetime.fromtimestamp(ts_ms / 1000, _IST).strftime("%Y-%m-%d")


def slice_session(candles: Sequence[OICandle], day: Optional[str] = None) -> list[OICandle]:
    """Only the bars belonging to one session.

    Open interest must never be differenced across a session boundary. Measured
    on the calibration sample: 2.95% of boundary transitions show a >=5% drop
    against 0.85% within a session, and at >=20% it is 0.57% against 0.11% -- a
    five-fold inflation that would fire at the first bar of *every* trading day.
    """
    if not candles:
        return []
    target = day or session_day(candles[-1].ts_ms)
    return [c for c in candles if session_day(c.ts_ms) == target]


def volume_baseline(candles: Sequence[OICandle], upto: int, lookback: int) -> Optional[float]:
    """Mean volume of the ``lookback`` bars before ``upto``, or None.

    Deliberately allowed to reach back across sessions. A volume baseline is a
    statistic about how busy this contract usually is, and a within-session-only
    window would be undefined until the twentieth bar of the day -- which is
    13:15, after most of the session the strategy cares about. The *difference*
    that must not cross a boundary is the OI one, not this.
    """
    if upto < lookback:
        return None
    window = candles[upto - lookback:upto]
    if len(window) < lookback:
        return None
    total = sum(c.volume for c in window)
    mean = total / lookback
    return mean if mean > 0 else None


def evaluate_bar(candles: Sequence[OICandle], index: int,
                 cfg: GammaMoveConfig) -> Optional[TriggerMetrics]:
    """The three conditions at ``index``, or None when they cannot be judged.

    None is not "no signal". A caller that renders an unjudgeable bar as a clean
    miss cannot tell a quiet contract from a broken feed, so the two stay
    distinguishable all the way to the board.
    """
    if index <= 0 or index >= len(candles):
        return None
    cur, prev = candles[index], candles[index - 1]
    if session_day(cur.ts_ms) != session_day(prev.ts_ms):
        return None                       # first bar of a session: no prior inside it
    if prev.oi <= 0 or prev.close <= 0 or cur.close <= 0:
        return None                       # a zero prior OI makes the ratio undefined
    base = volume_baseline(candles, index, cfg.volume_lookback)
    if base is None:
        return None

    oi_drop = (prev.oi - cur.oi) / prev.oi * 100.0
    vol_ratio = cur.volume / base
    price_gain = (cur.close - prev.close) / prev.close * 100.0
    return TriggerMetrics(
        oi_drop_pct=oi_drop, volume_ratio=vol_ratio, price_gain_pct=price_gain,
        unwinding=oi_drop >= cfg.min_oi_drop_pct,
        abnormal=vol_ratio >= cfg.volume_spike_mult,
        rising=price_gain >= cfg.min_price_gain_pct,
        bars_confirmed=0, bars_required=cfg.confirm_bars,
    )


def evaluate(candles: Sequence[OICandle], cfg: GammaMoveConfig,
             *, day: Optional[str] = None) -> Optional[TriggerMetrics]:
    """The trigger state on the most recently closed bar of one session.

    ``confirm_bars`` counts *consecutive* qualifying bars ending at the last one,
    which is the source's "confirms within 45 minutes" read at three bars.
    """
    if not candles:
        return None
    today = slice_session(candles, day)
    if len(today) < 2:
        return None
    # The volume baseline reaches back through earlier sessions, so index into
    # the full series and locate today's bars inside it.
    full = list(candles)
    last_ts = today[-1].ts_ms
    idx = next((i for i in range(len(full) - 1, -1, -1) if full[i].ts_ms == last_ts), None)
    if idx is None:
        return None

    latest = evaluate_bar(full, idx, cfg)
    if latest is None:
        return None

    confirmed = 0
    for back in range(cfg.confirm_bars):
        m = evaluate_bar(full, idx - back, cfg)
        if m is None or not (m.unwinding and m.abnormal and m.rising):
            break
        confirmed += 1
    return TriggerMetrics(
        oi_drop_pct=latest.oi_drop_pct, volume_ratio=latest.volume_ratio,
        price_gain_pct=latest.price_gain_pct, unwinding=latest.unwinding,
        abnormal=latest.abnormal, rising=latest.rising,
        bars_confirmed=confirmed, bars_required=cfg.confirm_bars,
    )
