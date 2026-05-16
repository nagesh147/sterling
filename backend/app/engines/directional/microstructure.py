"""
B1/B2: Microstructure detectors used by the 15m execution engine.

Liquidity sweep — bar wick pierces a recent extreme and closes back through
it (classic stop-hunt + reversal). Strong rejection signal that adds an
exec_score bump on pullback entries.

Displacement bar — large body relative to ATR with a small wick share
(institutional move). Acts as a continuation-quality booster.

Both are pure functions on numpy arrays; no schema dependencies. Each
returns a (detected: bool, score_bonus: float, reason: str) tuple.
"""
from __future__ import annotations
from typing import Tuple
import numpy as np


def detect_liquidity_sweep(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
    direction: str,
    lookback: int = 5,
    reclaim_buffer_pct: float = 0.1,
) -> Tuple[bool, float, str]:
    """
    Long sweep: latest low pierces min(prior `lookback` lows) AND latest close
                is back ABOVE that prior low (reclaimed liquidity).
    Short sweep: latest high pierces max(prior `lookback` highs) AND latest
                 close is back BELOW that prior high.

    `reclaim_buffer_pct` requires a small reclaim margin (default 0.1% of
    price) to avoid flagging marginal touches as sweeps.

    Returns (detected, +exec_score bonus 0-2, reason).
    """
    if len(high) < lookback + 1:
        return (False, 0.0, "")

    prev_lows  = low[-(lookback + 1):-1]
    prev_highs = high[-(lookback + 1):-1]
    cur_low    = float(low[-1])
    cur_high   = float(high[-1])
    cur_close  = float(close[-1])
    cur_open   = float(open_[-1])

    d = direction.lower()
    if d in ("long", "bullish"):
        prior_low = float(np.min(prev_lows))
        # Pierce + reclaim: wick below, close above (with buffer)
        pierced = cur_low < prior_low
        reclaimed = cur_close > prior_low * (1 + reclaim_buffer_pct / 100.0)
        # Bullish-body confirmation prevents flagging a heavy down candle
        bullish_body = cur_close >= cur_open
        if pierced and reclaimed and bullish_body:
            depth_pct = (prior_low - cur_low) / prior_low * 100.0 if prior_low > 0 else 0.0
            bonus = min(2.0, 0.5 + depth_pct * 0.5)
            return (True, round(bonus, 2),
                    f"liquidity sweep: low {cur_low:.2f} swept {prior_low:.2f} ({depth_pct:.2f}% depth), reclaimed")
        return (False, 0.0, "")

    if d in ("short", "bearish"):
        prior_high = float(np.max(prev_highs))
        pierced = cur_high > prior_high
        reclaimed = cur_close < prior_high * (1 - reclaim_buffer_pct / 100.0)
        bearish_body = cur_close <= cur_open
        if pierced and reclaimed and bearish_body:
            depth_pct = (cur_high - prior_high) / prior_high * 100.0 if prior_high > 0 else 0.0
            bonus = min(2.0, 0.5 + depth_pct * 0.5)
            return (True, round(bonus, 2),
                    f"liquidity sweep: high {cur_high:.2f} swept {prior_high:.2f} ({depth_pct:.2f}% depth), reclaimed")
        return (False, 0.0, "")

    return (False, 0.0, "")


def detect_displacement(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
    atr: float,
    direction: str,
    body_atr_mult: float = 1.5,
    max_wick_share: float = 0.25,
) -> Tuple[bool, float, str]:
    """
    Displacement bar: |body| > body_atr_mult × ATR AND
                      total wick / body < max_wick_share AND
                      direction matches signal direction.

    Returns (detected, +exec_score bonus 0-2, reason).
    """
    if len(close) == 0 or atr <= 0:
        return (False, 0.0, "")

    cur_open  = float(open_[-1])
    cur_close = float(close[-1])
    cur_high  = float(high[-1])
    cur_low   = float(low[-1])
    body = abs(cur_close - cur_open)

    if body < body_atr_mult * atr:
        return (False, 0.0, "")

    total_range = cur_high - cur_low
    if total_range <= 0:
        return (False, 0.0, "")
    wick_share = (total_range - body) / total_range

    if wick_share > max_wick_share:
        return (False, 0.0, "")

    d = direction.lower()
    is_bull_bar = cur_close > cur_open
    if d in ("long", "bullish") and not is_bull_bar:
        return (False, 0.0, "")
    if d in ("short", "bearish") and is_bull_bar:
        return (False, 0.0, "")

    body_atr = body / atr
    bonus = min(2.0, round((body_atr - body_atr_mult) * 1.0 + 0.75, 2))
    bonus = max(0.5, bonus)
    return (True, round(bonus, 2),
            f"displacement: body {body_atr:.2f}× ATR, wick {wick_share*100:.0f}%")
