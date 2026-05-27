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

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level
from app.engines.scalping.risk import resolve_trade_risk


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


def current_atr(closes: NDArray[np.float64], highs: NDArray[np.float64], lows: NDArray[np.float64], period: int = 14) -> float:
    if len(closes) < period + 1:
        return float(np.mean(highs[-period:] - lows[-period:])) if len(closes) > 0 else 0.0
    tr = np.maximum(
        highs[-period:] - lows[-period:],
        np.maximum(
            np.abs(highs[-period:] - closes[-period-1:-1]),
            np.abs(lows[-period:] - closes[-period-1:-1])
        )
    )
    return float(np.mean(tr))


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
    tp_source: str = ""
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

    fast = cfg.ma_fast_sma
    slow = cfg.ma_slow_ema
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
    cross_bars = min(cfg.ma_cross_window, i)

    for j in range(i - cross_bars + 1, i + 1):
        if j < 1 or sma[j] == 0 or ema[j] == 0 or sma[j-1] == 0 or ema[j-1] == 0:
            continue
        if sma[j] > ema[j] and sma[j - 1] <= ema[j - 1]:
            recent_cross_bull = True
        if sma[j] < ema[j] and sma[j - 1] >= ema[j - 1]:
            recent_cross_bear = True

    sma_above = sma[i] > ema[i]
    sma_below = sma[i] < ema[i]

    # ── Anti-whipsaw filter ──────────────────────────────────────────────────
    # In sideways chop SMA(5)/EMA(9) cross back and forth. Count crosses over the
    # last `chop_window` bars — more than one recent flip is a whipsaw regime.
    # Also require the MAs to be meaningfully separated vs ATR so a flat/overlapping
    # pair (the visual "no trend" case) can't arm a trade on micro-noise.
    atr_val = current_atr(closes, highs_15m, lows_15m)
    chop_window = min(10, i)
    flips = 0
    for j in range(i - chop_window + 1, i + 1):
        if j < 1 or sma[j] == 0 or ema[j] == 0 or sma[j - 1] == 0 or ema[j - 1] == 0:
            continue
        if (sma[j] > ema[j]) != (sma[j - 1] > ema[j - 1]):
            flips += 1
    sep_ok = atr_val <= 0 or abs(sma[i] - ema[i]) >= 0.10 * atr_val
    clean_cross = (flips <= 1) and sep_ok

    level_price = nearby.price
    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    if nearby.level_type == "support" and cfg.allow_long:
        if recent_cross_bull and clean_cross:
            # Fresh, non-choppy bullish crossover near 4H support.
            entry = round(current_price, 4)
            # Stop below the entire 4H support zone (per doc, this gives MA its
            # bigger profit potential). The risk module adds an ATR cushion, floors
            # the distance, R:R-gates the 4H target and rejects un-scalpable width.
            plan = resolve_trade_risk(
                direction="long", entry=entry, structure_stop=min(level_price, current_price),
                atr_val=atr_val, levels=levels, tp_level_type="resistance",
                max_risk_pct=4.0, max_stop_atr=6.0,
            )
            if plan.ok:
                direction = "long"; pattern = "sma_cross_above_ema"
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"SMA({fast}) crossed above EMA({slow}) near 4H support {level_price:.0f} · R:R {plan.rr}"
            else:
                reason = f"bull cross near 4H support {level_price:.0f} — skipped: {plan.reason}"
        elif recent_cross_bull:
            reason = f"bull cross near 4H support {level_price:.0f} — skipped: choppy/flat MAs (whipsaw filter)"
        elif sma_above:
            direction = "long"; pattern = "sma_above_ema"
            reason = f"Watching: SMA({fast}) > EMA({slow}) near 4H support {level_price:.0f} — awaiting crossover"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        if recent_cross_bear and clean_cross:
            # Fresh, non-choppy bearish crossover near 4H resistance.
            entry = round(current_price, 4)
            plan = resolve_trade_risk(
                direction="short", entry=entry, structure_stop=max(level_price, current_price),
                atr_val=atr_val, levels=levels, tp_level_type="support",
                max_risk_pct=4.0, max_stop_atr=6.0,
            )
            if plan.ok:
                direction = "short"; pattern = "sma_cross_below_ema"
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"SMA({fast}) crossed below EMA({slow}) near 4H resistance {level_price:.0f} · R:R {plan.rr}"
            else:
                reason = f"bear cross near 4H resistance {level_price:.0f} — skipped: {plan.reason}"
        elif recent_cross_bear:
            reason = f"bear cross near 4H resistance {level_price:.0f} — skipped: choppy/flat MAs (whipsaw filter)"
        elif sma_below:
            direction = "short"; pattern = "sma_below_ema"
            reason = f"Watching: SMA({fast}) < EMA({slow}) near 4H resistance {level_price:.0f} — awaiting crossover"

    if not pattern:
        if nearby.level_type == "support":
            reason = f"near 4H support @ {level_price:.0f} — SMA{'above' if sma_above else 'below'} EMA"
        else:
            reason = f"near 4H resistance @ {level_price:.0f} — SMA{'above' if sma_above else 'below'} EMA"

    return MACrossignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source if 'tp_source' in locals() else "",
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
        sma_value=round(float(sma[i]), 4), ema_value=round(float(ema[i]), 4),
    )