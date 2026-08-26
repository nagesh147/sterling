"""Where a Gamma Move trade stops and where it ends.

Only one of these rules comes from the source. It says to stop at the swing low
of the option's own premium and to hold one day, two at most; it gives **no
exit rule at all** -- its 2x and 3x figures are outcomes of discretionary exits,
not a rule that produced them. So ``TIME_STOP`` is the only policy supported by
evidence, and it is the only one live mode will run.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .config import GammaMoveConfig
from .models import ExitEvent, OICandle, PositionState, align_to_tick, q2
from .trigger import session_day


def swing_low_stop(candles: Sequence[OICandle], cfg: GammaMoveConfig) -> Optional[float]:
    """The option's own recent swing low.

    Explicitly the option chart, not the underlying: "this is in that particular
    strike -- I am not talking about that particular strike [spot]".
    """
    if len(candles) < 2:
        return None
    window = list(candles)[-cfg.swing_lookback:]
    lows = [c.low for c in window if c.low > 0]
    return q2(min(lows)) if lows else None


def initial_stop(entry: float, candles: Sequence[OICandle],
                 cfg: GammaMoveConfig) -> Optional[float]:
    """The stop to enter with, or None when no valid one exists.

    The percent floor is not a second opinion -- it is a cap on how much of the
    premium the swing low is allowed to put at risk. A swing low 70% below the
    entry is a stop in name only, so the tighter of the two wins.
    """
    if entry <= 0:
        return None
    swing = swing_low_stop(candles, cfg)
    floor = entry - cfg.stop_distance_inr(entry)
    if cfg.stop_basis == "PERCENT" and floor > 0:
        stop = max(swing, floor) if swing is not None else floor
    else:
        stop = swing if swing is not None else floor
    if stop is None or stop <= 0 or stop >= entry:
        # An inverted or zero stop is a rejected setup, never a trade entered
        # with the stop quietly moved to somewhere it can be honoured.
        return None
    return q2(stop)


def target_price(entry: float, cfg: GammaMoveConfig) -> Optional[float]:
    if cfg.exit_policy != "PERCENT_TARGET" or cfg.target_pct <= 0 or entry <= 0:
        return None
    return q2(entry * (1 + cfg.target_pct / 100.0))


def update_trail(pos: PositionState, ltp: float, cfg: GammaMoveConfig) -> Optional[float]:
    """Ratchet the trail. Never loosens -- a trail that can fall is not a trail."""
    if cfg.exit_policy != "TRAILING_STOP" or cfg.trail_pct <= 0 or ltp <= 0:
        return pos.trail
    pos.high_water = max(pos.high_water, ltp)
    if cfg.trail_start_pct > 0 and \
            pos.high_water < pos.entry * (1 + cfg.trail_start_pct / 100.0):
        return pos.trail
    candidate = q2(pos.high_water * (1 - cfg.trail_pct / 100.0))
    pos.trail = candidate if pos.trail is None else max(pos.trail, candidate)
    return pos.trail


def should_exit(pos: PositionState, ltp: float, now_ms: int, today: str,
                cfg: GammaMoveConfig, *, session_over: bool = False) -> Optional[str]:
    """Why this position should close now, or None. Order is worst-first."""
    if ltp > 0 and pos.stop > 0 and ltp <= pos.stop:
        return "stop"
    if pos.trail is not None and ltp > 0 and ltp <= pos.trail:
        return "trail"
    if pos.target is not None and ltp > 0 and ltp >= pos.target:
        return "target"
    # Sessions held, not wall-clock hours: the source counts trading days, and a
    # weekend must not age a position by two.
    if today != pos.entry_day:
        held = pos.sessions_held
        if held >= cfg.max_hold_days:
            return "time_stop"
    if session_over and cfg.close_at_session_end:
        return "session_end"
    return None


def exit_order_price(ltp: float, tick: float) -> float:
    """A marketable limit for the exit, aligned to the instrument's tick."""
    return align_to_tick(max(ltp, tick), tick)


def build_exit_event(pos: PositionState, reason: str, price: float,
                     at_ms: int) -> ExitEvent:
    return ExitEvent(signal_id=pos.signal_id, reason=reason, price=q2(price), at_ms=at_ms)


def realised_inr(pos: PositionState, exit_price: float) -> float:
    """Gross rupees. Costs belong to the caller that knows the broker's charges."""
    return q2((float(exit_price) - pos.entry) * pos.quantity)
