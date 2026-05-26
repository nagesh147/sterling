"""Strategy 1: Price Action scalping on 15min after 4H level test.

Bullish patterns (after test of 4H support):
  - Ascending triangle (flat top, rising lows)
  - Double bottom (two lows near same price)
  - Horizontal range / consolidation above support
  - Cup & handle approximation

Bearish patterns (after test of 4H resistance):
  - Descending triangle (flat bottom, declining highs)
  - Double top (two highs near same price)
  - Horizontal range / consolidation below resistance

Signal = breakout above/below the pattern's neckline.
Entry = current close (immediate on breakout confirmation).
Stop = below pattern low / above pattern high.
Target = nearest opposing 4H level, or 2R minimum.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level
from app.engines.directional.dynamic_tp import dynamic_tp


@dataclass
class PriceActionSignal:
    underlying: str
    direction: str          # "long" | "short" | "none"
    pattern: str            # e.g. "ascending_triangle"
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    tp_source: str = ""
    reason: str
    entry_ok: bool
    timestamp_ms: int


def detect_ascending_triangle(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    """Relaxed ascending triangle: roughly flat top with rising/lateral lows, and
    the close has broken above that ceiling in the last few bars."""
    if len(highs) < lookback:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    top = float(np.max(h))
    top_mean = float(np.mean(h))
    # Relaxed flat top: allow up to 3% coefficient of variation
    if top_mean == 0:
        return None
    top_cv = float(np.std(h)) / top_mean
    if top_cv > 0.04:
        return None
    # Rising lows: second-half lows should be higher than first-half lows on average
    mid = len(l) // 2
    low_early = float(np.min(l[:mid])) if mid > 0 else float(np.min(l))
    low_late = float(np.min(l[mid:])) if mid > 0 else float(np.min(l))
    # At minimum, late lows should not be much lower than early lows (.allowing some noise)
    if low_late < low_early * 0.97:
        return None
    resistance = round(top, 4)
    # Breakout in the last few bars: close above resistance * (1 + small margin)
    margin = top * 0.001  # 0.1% margin for confirmation
    for i in range(len(c) - 1, max(len(c) - 6, -1), -1):
        if c[i] > resistance - margin:
            return {
                "pattern": "ascending_triangle",
                "direction": "long",
                "neckline": resistance,
                "stop_below": round(float(np.min(l)), 4),
            }
    return None


def detect_double_bottom(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int = 30
) -> Optional[dict]:
    """
    Detects a valid structural 'W' Double Bottom pattern using localized pivot points.
    """
    # 1. Identify local pivot lows (a low lower than 2 bars left and right)
    pivot_low_indices = []
    for idx in range(len(lows) - lookback, len(lows) - 2):
        if lows[idx] < lows[idx-1] and lows[idx] < lows[idx-2] and \
           lows[idx] < lows[idx+1] and lows[idx] < lows[idx+2]:
            pivot_low_indices.append(idx)
            
    if len(pivot_low_indices) < 2:
        return None
        
    # Get the two most recent distinct pivot lows
    b1_idx = pivot_low_indices[-2]
    b2_idx = pivot_low_indices[-1]
    
    # Ensure they have adequate structural breathing room (at least 5 bars apart)
    if (b2_idx - b1_idx) < 5:
        return None
        
    b1_val = float(lows[b1_idx])
    b2_val = float(lows[b2_idx])
    
    # Check if the two bottoms are within a strict 1% variance of each other
    if abs(b1_val - b2_val) / max(b1_val, 1e-6) > 0.01:
        return None
        
    # 2. Extract Neckline: Find the distinct structural peak between the two bottoms
    inter_highs = highs[b1_idx:b2_idx + 1]
    neckline = float(np.max(inter_highs))
    
    # Ensure the neckline is a real structural peak (at least 1% higher than the bottoms)
    avg_bottom = (b1_val + b2_val) / 2
    if (neckline - avg_bottom) / avg_bottom < 0.01:
        return None
        
    # 3. Confirmation: Current candle must be breaking cleanly ABOVE the neckline
    # Avoid chasing huge overextended candles; ensure breakout is fresh
    current_close = float(closes[-1])
    if current_close > neckline and closes[-2] <= neckline * 1.002:
        return {
            "pattern": "double_bottom_confirmed",
            "direction": "long",
            "neckline": round(neckline, 4),
            "stop_below": round(min(b1_val, b2_val) * 0.998, 4), # Local pattern invalidation
        }
        
    return None


def detect_bullish_consolidation(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    """Tight range above support — price bouncing in a narrow band, momentum
    building for a breakout. Relaxed pattern: range < 2% of price, close near
    the top of the range."""
    if len(closes) < 10:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    range_high = float(np.max(h))
    range_low = float(np.min(l))
    mid_price = (range_high + range_low) / 2
    if mid_price == 0:
        return None
    range_pct = (range_high - range_low) / mid_price
    # Consolidation: range < 3% of price (relaxed for crypto)
    if range_pct > 0.03:
        return None
    # Close is in the upper 40% of the range (building pressure)
    if range_high == range_low:
        return None
    position = (c[-1] - range_low) / (range_high - range_low)
    if position < 0.6:
        return None
    return {
        "pattern": "consolidation",
        "direction": "long",
        "neckline": round(range_high, 4),
        "stop_below": round(range_low, 4),
    }


def detect_descending_triangle(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    """Relaxed descending triangle: roughly flat bottom with declining/lateral highs,
    and the close has broken below that floor in the last few bars."""
    if len(lows) < lookback:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    bottom = float(np.min(l))
    bottom_mean = float(np.mean(l))
    if bottom_mean == 0:
        return None
    bottom_cv = float(np.std(l)) / bottom_mean
    if bottom_cv > 0.04:
        return None
    # Highs should be declining
    mid = len(h) // 2
    high_early = float(np.max(h[:mid])) if mid > 0 else float(np.max(h))
    high_late = float(np.max(h[mid:])) if mid > 0 else float(np.max(h))
    if high_late >= high_early * 0.995:
        return None
    support = round(bottom, 4)
    margin = bottom * 0.001
    for i in range(len(c) - 1, max(len(c) - 6, -1), -1):
        if c[i] < support + margin:
            return {
                "pattern": "descending_triangle",
                "direction": "short",
                "neckline": support,
                "stop_above": round(float(np.max(h)), 4),
            }
    return None


def detect_double_top(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    """Relaxed double top: two peaks near the same price, current close below
    the neckline (the valley between the peaks)."""
    if len(highs) < lookback:
        return None
    hi = highs[-lookback:]
    lo = lows[-lookback:]
    c = closes[-lookback:]
    sorted_indices = np.argsort(-hi)  # descending
    top_idx = int(sorted_indices[0])
    top_val = float(hi[top_idx])
    second_idx = None
    for idx in sorted_indices[1:]:
        idx = int(idx)
        if abs(idx - top_idx) < 3:
            continue
        if abs(float(hi[idx]) - top_val) / max(top_val, 1e-6) < 0.02:
            second_idx = idx
            break
    if second_idx is None:
        return None
    lo_idx, hi_idx = min(top_idx, second_idx), max(top_idx, second_idx)
    neckline = round(float(np.min(lo[lo_idx:hi_idx + 1])), 4)
    if c[-1] > neckline * 1.002:
        return None
    return {
        "pattern": "double_top",
        "direction": "short",
        "neckline": neckline,
        "stop_above": round(top_val, 4),
    }


def detect_bearish_consolidation(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    """Tight range below resistance — price compressing, sellers absorbing,
    close near the bottom of the range."""
    if len(closes) < 10:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    range_high = float(np.max(h))
    range_low = float(np.min(l))
    mid_price = (range_high + range_low) / 2
    if mid_price == 0:
        return None
    range_pct = (range_high - range_low) / mid_price
    if range_pct > 0.03:
        return None
    if range_high == range_low:
        return None
    position = (c[-1] - range_low) / (range_high - range_low)
    if position > 0.4:
        return None
    return {
        "pattern": "consolidation",
        "direction": "short",
        "neckline": round(range_low, 4),
        "stop_above": round(range_high, 4),
    }


def evaluate_price_action(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> PriceActionSignal:
    """Evaluate Strategy 1: Price Action on 15min near 4H levels."""
    from app.schemas.market import Candle

    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < cfg.warmup_bars_15m or len(candles_4h) < cfg.warmup_bars_4h:
        return PriceActionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not cfg.enable_price_action:
        return PriceActionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 3)
    if nearby is None:
        return PriceActionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H level", entry_ok=False, timestamp_ms=now_ms,
        )

    o15 = np.array([c.open for c in candles_15m], dtype=np.float64)
    h15 = np.array([c.high for c in candles_15m], dtype=np.float64)
    l15 = np.array([c.low for c in candles_15m], dtype=np.float64)
    c15 = np.array([c.close for c in candles_15m], dtype=np.float64)
    lookback = min(cfg.pa_lookback, len(c15) - 1)

    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    if nearby.level_type == "support" and cfg.allow_long:
        # Try bullish patterns in order
        result = detect_ascending_triangle(h15, l15, c15, lookback)
        if result is None:
            result = detect_double_bottom(h15, l15, c15, lookback)
        if result is None:
            result = detect_bullish_consolidation(h15, l15, c15, lookback)
        if result is not None:
            pattern = result["pattern"]
            direction = result["direction"]
            neckline = result["neckline"]
            stop_below = result.get("stop_below", result.get("stop_above", nearby.price * 0.98))
            entry = round(current_price, 4)
            stop_loss = round(float(stop_below) * 0.998, 4)
            tp_level = nearest_level(current_price, levels, "resistance")
            tp_level_price = float(tp_level.price * 0.998) if tp_level else None
            take_profit, tp_source = dynamic_tp(
                direction="long",
                entry=entry,
                stop_dist=entry - stop_loss,
                rr=2.0,
                highs=h15,
                lows=l15,
                atr=(entry - stop_loss), # Proxy
                swing_lookback=10,
                tp_level=tp_level_price
            )
            entry_ok = True
            reason = f"{pattern} near 4H support {nearby.price:.0f}"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        # Try bearish patterns in order
        result = detect_descending_triangle(h15, l15, c15, lookback)
        if result is None:
            result = detect_double_top(h15, l15, c15, lookback)
        if result is None:
            result = detect_bearish_consolidation(h15, l15, c15, lookback)
        if result is not None:
            pattern = result["pattern"]
            direction = result["direction"]
            neckline = result["neckline"]
            stop_above = result.get("stop_above", result.get("stop_below", nearby.price * 1.02))
            entry = round(current_price, 4)
            stop_loss = round(float(stop_above) * 1.002, 4)
            tp_level = nearest_level(current_price, levels, "support")
            tp_level_price = float(tp_level.price * 1.002) if tp_level else None
            take_profit, tp_source = dynamic_tp(
                direction="short",
                entry=entry,
                stop_dist=stop_loss - entry,
                rr=2.0,
                highs=h15,
                lows=l15,
                atr=(stop_loss - entry),
                swing_lookback=10,
                tp_level=tp_level_price
            )
            entry_ok = True
            reason = f"{pattern} near 4H resistance {nearby.price:.0f}"

    if not pattern:
        reason = f"near 4H {nearby.level_type} @ {nearby.price:.0f} — no confirmed pattern"

    return PriceActionSignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(nearby.price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source if 'tp_source' in locals() else "",
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
    )