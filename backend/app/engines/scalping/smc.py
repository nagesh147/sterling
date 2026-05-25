"""Strategy 2: Smart Money Concepts (SMC) scalping.

After a 4H liquidity zone test:
  Bullish: inducement (false breakdown) then bullish imbalance candle
             (large bullish body engulfing prior bearish candle's range)
  Bearish: inducement (false breakout) then bearish imbalance candle
             (large bearish body engulfing prior bullish candle's range)

Entry  = immediately after imbalance candle close
Stop   = below imbalance candle low (long) / above high (short)
Target = nearest 15min resistance (long) / support (short)

Relaxed detection: we scan the last N bars for the pattern sequence
(SMC valid candle near a level), not just one candle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level


@dataclass
class SMCESignal:
    underlying: str
    direction: str          # "long" | "short" | "none"
    pattern: str            # "bullish_imbalance" | "bearish_imbalance" | ""
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str
    entry_ok: bool
    timestamp_ms: int


def evaluate_smc(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> SMCESignal:
    """Evaluate Strategy 2: SMC inducement + imbalance."""
    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < cfg.warmup_bars_15m or len(candles_4h) < cfg.warmup_bars_4h:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not cfg.enable_smc:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 3)
    if nearby is None:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H liquidity zone", entry_ok=False, timestamp_ms=now_ms,
        )

    n = len(candles_15m)
    highs = np.array([c.high for c in candles_15m], dtype=np.float64)
    lows = np.array([c.low for c in candles_15m], dtype=np.float64)
    opens = np.array([c.open for c in candles_15m], dtype=np.float64)
    closes = np.array([c.close for c in candles_15m], dtype=np.float64)
    level_price = nearby.price
    tol = cfg.level_tolerance_pct / 100.0

    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    # Search the last `lookback` bars for the SMC pattern:
    # 1. An inducement bar (wicks below/above the level)
    # 2. Followed by an imbalance candle (body engulfs previous candle's full range)
    lookback = min(20, n - 1)

    if nearby.level_type == "support" and cfg.allow_long:
        # Bullish: look for a bar that wicked below support (inducement),
        # then a bullish candle whose body engulfs the prior bar's range.
        for i in range(n - lookback, n):
            if closes[i] <= opens[i]:
                continue  # skip bearish candles — we need a bullish imbalance
            body = closes[i] - opens[i]
            if i < 1:
                continue
            prev_range = highs[i - 1] - lows[i - 1]
            if prev_range <= 0:
                continue
            # Imbalance: current bullish body > previous candle's range * ratio
            if body < prev_range * cfg.smc_imbalance_ratio * 0.5:
                continue
            # Look for an inducement in the window before this candle:
            # a bar that wicked below support (showing a false breakdown)
            inducement_found = False
            for j in range(max(n - lookback, 0), i):
                if lows[j] < level_price * (1 - tol * 0.5):
                    inducement_found = True
                    break
            if not inducement_found:
                continue
            # This is a valid bullish SMC signal
            direction = "long"
            pattern = "bullish_imbalance"
            entry = round(float(closes[i]), 4)
            stop_loss = round(float(lows[i]) * 0.999, 4)
            tp_level = nearest_level(current_price, levels, "resistance")
            take_profit = round(float(tp_level.price), 4) if tp_level else round(entry + (entry - stop_loss) * 2, 4)
            entry_ok = True
            reason = f"bullish imbalance after inducement below 4H support {level_price:.0f}"
            break

    elif nearby.level_type == "resistance" and cfg.allow_short:
        # Bearish: look for a bar that wicked above resistance (inducement),
        # then a bearish candle whose body engulfs the prior bar's range.
        for i in range(n - lookback, n):
            if closes[i] >= opens[i]:
                continue  # skip bullish candles — we need a bearish imbalance
            body = opens[i] - closes[i]
            if i < 1:
                continue
            prev_range = highs[i - 1] - lows[i - 1]
            if prev_range <= 0:
                continue
            # Imbalance: current bearish body > previous candle's range * ratio
            if body < prev_range * cfg.smc_imbalance_ratio * 0.5:
                continue
            # Look for inducement: a bar that wicked above resistance
            inducement_found = False
            for j in range(max(n - lookback, 0), i):
                if highs[j] > level_price * (1 + tol * 0.5):
                    inducement_found = True
                    break
            if not inducement_found:
                continue
            direction = "short"
            pattern = "bearish_imbalance"
            entry = round(float(closes[i]), 4)
            stop_loss = round(float(highs[i]) * 1.001, 4)
            tp_level = nearest_level(current_price, levels, "support")
            take_profit = round(float(tp_level.price), 4) if tp_level else round(entry - (stop_loss - entry) * 2, 4)
            entry_ok = True
            reason = f"bearish imbalance after inducement above 4H resistance {level_price:.0f}"
            break

    if not pattern:
        # Provide context even when no pattern is found
        if nearby.level_type == "support":
            reason = f"near 4H support @ {level_price:.0f} — no inducement + imbalance confirmed"
        else:
            reason = f"near 4H resistance @ {level_price:.0f} — no inducement + imbalance confirmed"

    return SMCESignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
    )