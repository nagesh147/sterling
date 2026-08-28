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

from app.engines.sterling_engine.config import ScalpingProfile as ScalpingConfig
from app.engines.sterling_engine.levels import Level, price_near_level, nearest_level
from app.engines.risk.trade_risk import resolve_trade_risk


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


def check_1h_structure(candles_1h: list) -> tuple[bool, bool]:
    """Check if the 1-hour market structure is bullish or bearish (higher highs and higher lows)."""
    if not candles_1h or len(candles_1h) < 2:
        return True, True
    
    c1, c2 = candles_1h[-2], candles_1h[-1]
    bullish = c2.high > c1.high and c2.low > c1.low
    bearish = c2.high < c1.high and c2.low < c1.low
    return bullish, bearish


def _candles_to_df(candles: list):
    """Candle list → DataFrame with OHLC for the edge signal/ATR functions."""
    import pandas as pd
    return pd.DataFrame({
        "open":  [c.open for c in candles],
        "high":  [c.high for c in candles],
        "low":   [c.low for c in candles],
        "close": [c.close for c in candles],
        "volume": [getattr(c, "volume", 0.0) for c in candles],
    })


def evaluate_ma_crossover(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    candles_1h: list,        # retained for signature compat; unused (edge logic is self-gating)
    levels: list[Level],
    cfg: ScalpingConfig,
) -> MACrossignal:
    """Strategy 3 — RECONCILED to the validated edge logic.

    Delegates the crossover decision to the single source of truth
    ``edge/strategies.py:signals_ma_crossover`` (EMA9 × EMA21, long-only) run on
    the **4H** series — the exact function the edge feed trades and the 270-config
    matrix validated (MA Crossover 4h BTC: Sharpe 1.83, +95%). The trade plan is a
    fixed ATR bracket (``cfg.ma_atr_sl`` / ``cfg.ma_atr_tp``, default 2.0/3.5 =
    the validated "Intraday" profile). Long-only: no short branch, no near-level
    or 1h-structure gate — those belonged to the old, BTC-losing SMA(5)/EMA(9)
    implementation that was a different strategy wearing the same name.
    """
    from app.engines.edge.strategies import signals_ma_crossover, atr14

    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    def _none(reason: str) -> MACrossignal:
        return MACrossignal(
            underlying=underlying, direction="none", pattern="", near_level=None,
            level_type="", entry=None, stop_loss=None, take_profit=None,
            reason=reason, entry_ok=False, timestamp_ms=now_ms,
        )

    if not getattr(cfg, "enable_ma_crossover", False):
        return _none("strategy disabled")
    if not getattr(cfg, "allow_long", True):
        return _none("long-only strategy but longs disabled")
    # EMA21 + the fresh-cross shift need a warmup; the 4H series drives the signal.
    if len(candles_4h) < 25 or current_price <= 0:
        return _none("insufficient 4H data")

    df = _candles_to_df(candles_4h)
    sigs = signals_ma_crossover(df)
    fresh_cross = bool(len(sigs) and sigs[-1])

    atr_series = atr14(df)
    atr_val = float(atr_series.iloc[-1]) if len(atr_series) and atr_series.iloc[-1] == atr_series.iloc[-1] else 0.0

    fast = df["close"].ewm(span=9, adjust=False).mean().iloc[-1]
    slow = df["close"].ewm(span=21, adjust=False).mean().iloc[-1]

    if not fresh_cross:
        st = "above" if fast > slow else "below"
        return MACrossignal(
            underlying=underlying, direction="none", pattern=f"ema9_{st}_ema21",
            near_level=None, level_type="", entry=None, stop_loss=None, take_profit=None,
            reason=f"no fresh EMA9×EMA21 bull cross on latest 4H bar (EMA9 {st} EMA21)",
            entry_ok=False, timestamp_ms=now_ms,
            sma_value=round(float(fast), 4), ema_value=round(float(slow), 4),
        )

    if atr_val <= 0:
        return _none("fresh cross but ATR unavailable")

    sl_mult = float(getattr(cfg, "ma_atr_sl", 2.0))
    tp_mult = float(getattr(cfg, "ma_atr_tp", 3.5))
    entry = round(current_price, 4)
    stop_loss = round(entry - sl_mult * atr_val, 4)
    take_profit = round(entry + tp_mult * atr_val, 4)

    nl = nearest_level(current_price, levels) if levels else None
    return MACrossignal(
        underlying=underlying, direction="long", pattern="ema9_cross_above_ema21",
        near_level=round(nl.price, 4) if nl else None,
        level_type=nl.level_type if nl else "",
        entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        tp_source="atr_bracket_validated",
        reason=(f"EMA9 crossed above EMA21 on 4H (validated edge) · "
                f"SL {sl_mult}×ATR / TP {tp_mult}×ATR (R:R {tp_mult/sl_mult:.2f})"),
        entry_ok=True, timestamp_ms=now_ms,
        sma_value=round(float(fast), 4), ema_value=round(float(slow), 4),
    )
