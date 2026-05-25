"""Strategy 3: MA Crossover scalping.

SMA(fast) × EMA(slow) crossover near 4H key levels.

  Bullish (near 4H support): SMA(5) crosses above EMA(9) → go long immediately
    Stop: below the entire 4H support zone
    Target: nearest 4H resistance

  Bearish (near 4H resistance): SMA(5) crosses below EMA(9) → go short immediately
    Stop: above the entire 4H resistance zone
    Target: nearest 4H support

Relaxed: we also accept "recent crossover" (within last 3 bars) and
"aligned near level" (MAs in correct order — watching state).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level


def rolling_sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """SMA with warmup zeros."""
    n = len(values)
    out = np.zeros(n)
    if n < period or period < 1:
        return out
    csum = np.cumsum(values)
    out[period - 1] = csum[period - 1] / period
    out[period:] = (csum[period:] - csum[:-period]) / period
    return out


def rolling_ema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """EMA with warmup zeros."""
    n = len(values)
    out = np.zeros(n)
    if n < period or period < 1:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = np.mean(values[:period])
    for i in range(period, n):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


@dataclass
class MACrossignal:
    underlying: str
    direction: str          # "long" | "short" | "watch_long" | "watch_short" | "none"
    pattern: str            # "sma_cross_above_ema" | "sma_above_ema" | etc.
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str
    entry_ok: bool
    timestamp_ms: int
    sma_value: float = 0.0
    ema_value: float = 0.0


def evaluate_ma_crossover(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> MACrossignal:
    """Evaluate Strategy 3: SMA(fast) × EMA(slow) crossover."""
    from app.schemas.market import Candle

    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < cfg.warmup_bars_15m or len(candles_4h) < cfg.warmup_bars_4h:
        return MACrossignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not cfg.enable_ma_crossover:
        return MACrossignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 3)
    if nearby is None:
        return MACrossignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H level", entry_ok=False, timestamp_ms=now_ms,
        )

    closes = np.array([c.close for c in candles_15m], dtype=np.float64)
    lows_15m = np.array([c.low for c in candles_15m], dtype=np.float64)
    highs_15m = np.array([c.high for c in candles_15m], dtype=np.float64)

    fast = cfg.ma_fast_period
    slow = cfg.ma_slow_period
    sma = rolling_sma(closes, fast)
    ema = rolling_ema(closes, slow)

    i = len(closes) - 1
    if sma[i] == 0 or ema[i] == 0:
        return MACrossignal(
            underlying=underlying, direction="none", pattern="",
            near_level=round(nearby.price, 4), level_type=nearby.level_type,
            entry=None, stop_loss=None, take_profit=None,
            reason="MA warmup incomplete", entry_ok=False, timestamp_ms=now_ms,
            sma_value=float(sma[i]), ema_value=float(ema[i]),
        )

    # Check for recent crossover (within last 3 bars) — more practical than exact bar
    recent_cross_bull = False
    recent_cross_bear = False
    cross_bars = min(3, i)

    for j in range(i - cross_bars + 1, i + 1):
        if j < 1 or sma[j] == 0 or ema[j] == 0 or sma[j-1] == 0 or ema[j-1] == 0:
            continue
        if sma[j] > ema[j] and sma[j - 1] <= ema[j - 1]:
            recent_cross_bull = True
        if sma[j] < ema[j] and sma[j - 1] >= ema[j - 1]:
            recent_cross_bear = True

    sma_above = sma[i] > ema[i]
    sma_below = sma[i] < ema[i]
    level_price = nearby.price
    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    if nearby.level_type == "support" and cfg.allow_long:
        if recent_cross_bull:
            # Fresh bullish crossover near support — ARMED, can execute
            direction = "long"
            pattern = "sma_cross_above_ema"
            entry = round(current_price, 4)
            support_zone_low = round(float(np.min([c.low for c in candles_4h[-20:]])), 4) if len(candles_4h) >= 20 else round(level_price * 0.99, 4)
            stop_loss = round(support_zone_low * 0.999, 4)
            tp_level = nearest_level(current_price, levels, "resistance")
            take_profit = round(float(tp_level.price), 4) if tp_level else round(current_price + (current_price - support_zone_low) * 2, 4)
            entry_ok = True
            reason = f"SMA({fast}) crossed above EMA({slow}) near 4H support {level_price:.0f}"
        elif sma_above:
            # MAs aligned but no fresh cross — watching, NOT executable
            direction = "long"
            pattern = "sma_above_ema"
            support_zone_low = round(float(np.min([c.low for c in candles_4h[-20:]])), 4) if len(candles_4h) >= 20 else round(level_price * 0.99, 4)
            tp_level = nearest_level(current_price, levels, "resistance")
            reason = f"Watching: SMA({fast}) > EMA({slow}) near 4H support {level_price:.0f} — awaiting crossover"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        if recent_cross_bear:
            # Fresh bearish crossover near resistance — ARMED, can execute
            direction = "short"
            pattern = "sma_cross_below_ema"
            entry = round(current_price, 4)
            resistance_zone_high = round(float(np.max([c.high for c in candles_4h[-20:]])), 4) if len(candles_4h) >= 20 else round(level_price * 1.01, 4)
            stop_loss = round(resistance_zone_high * 1.001, 4)
            tp_level = nearest_level(current_price, levels, "support")
            take_profit = round(float(tp_level.price), 4) if tp_level else round(current_price - (resistance_zone_high - current_price) * 2, 4)
            entry_ok = True
            reason = f"SMA({fast}) crossed below EMA({slow}) near 4H resistance {level_price:.0f}"
        elif sma_below:
            # MAs aligned but no fresh cross — watching, NOT executable
            direction = "short"
            pattern = "sma_below_ema"
            resistance_zone_high = round(float(np.max([c.high for c in candles_4h[-20:]])), 4) if len(candles_4h) >= 20 else round(level_price * 1.01, 4)
            tp_level = nearest_level(current_price, levels, "support")
            reason = f"Watching: SMA({fast}) < EMA({slow}) near 4H resistance {level_price:.0f} — awaiting crossover"

    if not pattern:
        if nearby.level_type == "support":
            reason = f"near 4H support @ {level_price:.0f} — SMA{'above' if sma_above else 'below'} EMA"
        else:
            reason = f"near 4H resistance @ {level_price:.0f} — SMA{'above' if sma_above else 'below'} EMA"

    return MACrossignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
        sma_value=round(float(sma[i]), 4), ema_value=round(float(ema[i]), 4),
    )