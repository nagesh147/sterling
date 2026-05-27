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

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level, detect_levels
from app.engines.scalping.risk import atr, resolve_trade_risk


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
    reason: str
    entry_ok: bool
    timestamp_ms: int
    tp_source: str = ""


def _pivots(arr: NDArray, kind: str, dist: int = 2) -> List[int]:
    """Indices of local extrema (`kind` = 'high' | 'low') with `dist` bars of
    clear space on each side."""
    out: List[int] = []
    for i in range(dist, len(arr) - dist):
        seg = arr[i - dist:i + dist + 1]
        if kind == "high" and int(np.argmax(seg)) == dist:
            out.append(i)
        elif kind == "low" and int(np.argmin(seg)) == dist:
            out.append(i)
    return out


def _fresh_breakout(closes: NDArray, level: float, direction: str, confirm_bars: int) -> bool:
    """A confirmed breakout of `level` in the trade's favour.

    True when, within the last `confirm_bars` closed bars, a close *crossed*
    `level` (prior bar on the wrong side, this bar on the right side) AND the
    most recent close is *still* beyond `level`. This widens the old single-bar
    guard (`c[-1] cross, c[-2] didn't`) to a small confirmation window so a
    breakout that closed 1–N bars ago still arms — yet it never re-introduces
    the stale-breakout bug, because price must remain past the neckline now
    (a retrace back inside invalidates the setup).
    """
    n = len(closes)
    if n < 2:
        return False
    is_long = direction == "long"
    # Must still be beyond the neckline on the latest close.
    if is_long and closes[-1] <= level:
        return False
    if not is_long and closes[-1] >= level:
        return False
    w = max(1, min(int(confirm_bars), n - 1))
    for i in range(n - w, n):
        if i < 1:
            continue
        prev, cur = float(closes[i - 1]), float(closes[i])
        if is_long and cur > level and prev <= level:
            return True
        if not is_long and cur < level and prev >= level:
            return True
    return False


def detect_inverse_head_shoulders(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig) -> Optional[dict]:
    """Bullish inverse H&S: left shoulder, lower head, right shoulder (symmetric),
    breakout on a close above the neckline (peaks between the lows)."""
    lb = cfg.pa_lookback_bars
    if len(closes) < lb:
        return None
    h, l, c = highs[-lb:], lows[-lb:], closes[-lb:]
    piv = _pivots(l, "low", 2)
    if len(piv) < 3:
        return None
    ls, head, rs = piv[-3], piv[-2], piv[-1]
    lv, hv, rv = float(l[ls]), float(l[head]), float(l[rs])
    if not (hv < lv and hv < rv):                       # head is the lowest low
        return None
    if abs(lv - rv) / max(lv, 1e-6) > 0.03:             # shoulders roughly symmetric
        return None
    neckline = float(np.max(h[ls:rs + 1]))
    if not _fresh_breakout(c, neckline, "long", cfg.pa_confirm_bars):   # confirmed break above
        return None
    return {"pattern": "inverse_head_shoulders", "direction": "long",
            "neckline": round(neckline, 4), "stop_below": round(hv, 4)}


def detect_head_shoulders(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig) -> Optional[dict]:
    """Bearish H&S: left shoulder, higher head, right shoulder (symmetric),
    breakdown on a close below the neckline (valleys between the highs)."""
    lb = cfg.pa_lookback_bars
    if len(closes) < lb:
        return None
    h, l, c = highs[-lb:], lows[-lb:], closes[-lb:]
    piv = _pivots(h, "high", 2)
    if len(piv) < 3:
        return None
    ls, head, rs = piv[-3], piv[-2], piv[-1]
    lv, hv, rv = float(h[ls]), float(h[head]), float(h[rs])
    if not (hv > lv and hv > rv):                       # head is the highest high
        return None
    if abs(lv - rv) / max(lv, 1e-6) > 0.03:             # shoulders roughly symmetric
        return None
    neckline = float(np.min(l[ls:rs + 1]))
    if not _fresh_breakout(c, neckline, "short", cfg.pa_confirm_bars):  # confirmed break below
        return None
    return {"pattern": "head_shoulders", "direction": "short",
            "neckline": round(neckline, 4), "stop_above": round(hv, 4)}


def detect_cup_handle(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig) -> Optional[dict]:
    """Bullish cup & handle: rounded bottom (U) that recovers to near the left
    rim, then breaks above the rim. (The recent handle dip is the stop anchor.)"""
    lb = cfg.pa_lookback_bars
    if len(closes) < lb:
        return None
    h, l, c = highs[-lb:], lows[-lb:], closes[-lb:]
    third = lb // 3
    if third < 2:
        return None
    left_rim = float(np.max(h[:third]))
    bottom = float(np.min(l[third:2 * third]))
    right = float(np.max(h[2 * third:]))
    if left_rim == 0:
        return None
    if (left_rim - bottom) / left_rim < 0.02:           # cup at least 2% deep
        return None
    if abs(right - left_rim) / left_rim > 0.03:         # right side recovered to the rim
        return None
    rim = max(left_rim, right)
    if not _fresh_breakout(c, rim, "long", cfg.pa_confirm_bars):        # confirmed break above rim
        return None
    handle_low = float(np.min(l[2 * third:]))
    return {"pattern": "cup_handle", "direction": "long",
            "neckline": round(rim, 4), "stop_below": round(handle_low, 4)}


def detect_inverse_cup_handle(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig) -> Optional[dict]:
    """Bearish inverted cup & handle: rounded top (∩) that falls back to near the
    left rim, then breaks below the rim."""
    lb = cfg.pa_lookback_bars
    if len(closes) < lb:
        return None
    h, l, c = highs[-lb:], lows[-lb:], closes[-lb:]
    third = lb // 3
    if third < 2:
        return None
    left_rim = float(np.min(l[:third]))
    top = float(np.max(h[third:2 * third]))
    right = float(np.min(l[2 * third:]))
    if left_rim == 0:
        return None
    if (top - left_rim) / left_rim < 0.02:              # cap at least 2% tall
        return None
    if abs(right - left_rim) / left_rim > 0.03:         # right side fell back to the rim
        return None
    rim = min(left_rim, right)
    if not _fresh_breakout(c, rim, "short", cfg.pa_confirm_bars):       # confirmed break below rim
        return None
    handle_high = float(np.max(h[2 * third:]))
    return {"pattern": "inverse_cup_handle", "direction": "short",
            "neckline": round(rim, 4), "stop_above": round(handle_high, 4)}


def detect_ascending_triangle(highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig) -> Optional[dict]:
    """Relaxed ascending triangle: roughly flat top with rising/lateral lows, and
    the close has broken above that ceiling in the last few bars."""
    lookback = cfg.pa_lookback_bars
    w = max(1, min(cfg.pa_confirm_bars, len(highs) - 2))
    if len(highs) < lookback + w:
        return None
    # Ceiling is defined by the consolidation BEFORE the breakout window, so the
    # breakout bars don't raise the very level they're meant to clear (the old
    # `top = max(highs[-lookback:])` included the breakout bar, making `close >
    # ceiling` structurally near-impossible — a close never exceeds its own high).
    h = highs[-lookback - w:-w]
    l = lows[-lookback - w:-w]
    top = float(np.max(h))
    top_mean = float(np.mean(h))
    if top_mean == 0:
        return None
    top_cv = float(np.std(h)) / top_mean
    if top_cv > 0.015:                       # genuinely flat ceiling (≤1.5% var), not a drift
        return None
    # Rising lows: second-half lows must be genuinely higher than first-half lows.
    mid = len(l) // 2
    low_early = float(np.min(l[:mid])) if mid > 0 else float(np.min(l))
    low_late = float(np.min(l[mid:])) if mid > 0 else float(np.min(l))
    if low_late <= low_early:                # must actually rise (not merely "not fall")
        return None
    resistance = round(top, 4)
    # Confirmed breakout within the last `w` bars, price still above the ceiling.
    if not _fresh_breakout(closes, resistance, "long", w):
        return None
    return {
        "pattern": "ascending_triangle",
        "direction": "long",
        "neckline": resistance,
        "stop_below": round(float(np.min(l)), 4),
    }


def detect_double_bottom(
    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig
) -> Optional[dict]:
    """
    Evaluates 15m geometry for a structurally valid Double Bottom at 4H Support.
    """
    lookback = cfg.pa_lookback_bars
    
    # 1. Locate structural pivot lows (local minima with 2 bars of clear space on both sides)
    pivot_low_indices = []
    for idx in range(len(lows) - lookback, len(lows) - 2):
        if lows[idx] < lows[idx-1] and lows[idx] < lows[idx-2] and \
           lows[idx] < lows[idx+1] and lows[idx] < lows[idx+2]:
            pivot_low_indices.append(idx)
            
    if len(pivot_low_indices) < 2:
        return None
        
    # Extract the two most recent distinct structural bottoms
    b1_idx = pivot_low_indices[-2]
    b2_idx = pivot_low_indices[-1]
    
    # Enforce structural width constraint
    if (b2_idx - b1_idx) < cfg.pa_min_pivot_distance:
        return None
        
    b1_val = float(lows[b1_idx])
    b2_val = float(lows[b2_idx])
    
    # Enforce value variance constraint (bottoms must line up within 1%)
    if abs(b1_val - b2_val) / max(b1_val, 1e-6) > cfg.pa_max_bottom_variance:
        return None
        
    # 2. Track the structural neckline peak dividing the two bottoms
    inter_highs = highs[b1_idx:b2_idx + 1]
    neckline = float(np.max(inter_highs))
    
    # Enforce depth constraint (neckline peak must be a meaningful bounce)
    avg_bottom = (b1_val + b2_val) / 2
    if (neckline - avg_bottom) / avg_bottom < cfg.pa_min_neckline_height:
        return None
        
    # 3. Confirmation Evaluation — confirmed break above the neckline within the
    # last `pa_confirm_bars` bars, price still above it (windowed; see _fresh_breakout).
    if _fresh_breakout(closes, neckline, "long", cfg.pa_confirm_bars):
        return {
            "pattern": "double_bottom_confirmed",
            "direction": "long",
            "entry": round(float(closes[-1]), 4),
            "neckline": round(neckline, 4),
            "stop_loss": round(min(b1_val, b2_val) * 0.998, 4), # Invalidation tucked under pattern low
        }

    return None


def detect_bullish_consolidation(
    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig
) -> Optional[dict]:
    """Horizontal-range breakout (bullish). The doc's "horizontal range" pattern
    signals on a NECKLINE BREAKOUT — not on price merely sitting inside the range.
    The previous version fired whenever the close was in the upper 40% of a ≤3%
    band, i.e. on pure sideways chop. This requires a tight prior range and a
    FRESH close above its top."""
    lookback = cfg.pa_lookback_bars
    w = max(1, min(cfg.pa_confirm_bars, len(closes) - 2))
    if len(closes) < lookback + w + 1:
        return None
    # Range measured over the window PRIOR to the confirmation window, so the
    # post-breakout bars don't inflate the range that defines the level.
    h = highs[-lookback - w:-w]
    l = lows[-lookback - w:-w]
    if len(h) < 5:
        return None
    range_high = float(np.max(h))
    range_low = float(np.min(l))
    mid_price = (range_high + range_low) / 2
    if mid_price == 0 or range_high == range_low:
        return None
    if (range_high - range_low) / mid_price > 0.03:      # must be a tight coil
        return None
    # Confirmed breakout within the last `w` bars, price still above the range top.
    if not _fresh_breakout(closes, range_high, "long", w):
        return None
    return {
        "pattern": "range_breakout",
        "direction": "long",
        "neckline": round(range_high, 4),
        "stop_below": round(range_low, 4),
    }


def detect_descending_triangle(
    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig
) -> Optional[dict]:
    """Relaxed descending triangle: roughly flat bottom with declining/lateral highs,
    and the close has broken below that floor in the last few bars."""
    lookback = cfg.pa_lookback_bars
    w = max(1, min(cfg.pa_confirm_bars, len(lows) - 2))
    if len(lows) < lookback + w:
        return None
    # Floor defined by the consolidation BEFORE the breakdown window (same reason
    # as the ascending triangle: don't let the breakdown bar lower its own floor).
    h = highs[-lookback - w:-w]
    l = lows[-lookback - w:-w]
    bottom = float(np.min(l))
    bottom_mean = float(np.mean(l))
    if bottom_mean == 0:
        return None
    bottom_cv = float(np.std(l)) / bottom_mean
    if bottom_cv > 0.015:                    # genuinely flat floor (≤1.5% var)
        return None
    # Highs must be genuinely declining (the defining trait).
    mid = len(h) // 2
    high_early = float(np.max(h[:mid])) if mid > 0 else float(np.max(h))
    high_late = float(np.max(h[mid:])) if mid > 0 else float(np.max(h))
    if high_late >= high_early:
        return None
    support = round(bottom, 4)
    # Confirmed breakdown within the last `w` bars, price still below the floor.
    if not _fresh_breakout(closes, support, "short", w):
        return None
    return {
        "pattern": "descending_triangle",
        "direction": "short",
        "neckline": support,
        "stop_above": round(float(np.max(h)), 4),
    }


def detect_double_top(
    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig
) -> Optional[dict]:
    """Bearish double top — a strict mirror of `detect_double_bottom`.

    Two structural pivot HIGHS near the same price, a meaningful neckline trough
    between them, and a confirmed breakdown below it. This previously used a
    permissive `argsort` with hardcoded 2% / 3-bar thresholds and *no* neckline
    gate — far looser than double_bottom's config-driven 4-bar pivot test — so
    short setups armed far more readily than longs (a mechanical short bias:
    double_top was ~90% of all shorts). Mirroring the geometry removes it; the
    long/short split now reflects market structure, not the detector.
    """
    lookback = cfg.pa_lookback_bars

    # 1. Locate structural pivot highs (local maxima with 2 bars clear each side).
    pivot_high_indices = []
    for idx in range(len(highs) - lookback, len(highs) - 2):
        if highs[idx] > highs[idx - 1] and highs[idx] > highs[idx - 2] and \
           highs[idx] > highs[idx + 1] and highs[idx] > highs[idx + 2]:
            pivot_high_indices.append(idx)

    if len(pivot_high_indices) < 2:
        return None

    # The two most recent distinct structural tops.
    t1_idx = pivot_high_indices[-2]
    t2_idx = pivot_high_indices[-1]

    # Structural width (same constraint as double_bottom).
    if (t2_idx - t1_idx) < cfg.pa_min_pivot_distance:
        return None

    t1_val = float(highs[t1_idx])
    t2_val = float(highs[t2_idx])

    # Peaks must line up within the same variance band as the bottoms.
    if abs(t1_val - t2_val) / max(t1_val, 1e-6) > cfg.pa_max_bottom_variance:
        return None

    # Neckline = the trough between the two tops; require a meaningful dip.
    inter_lows = lows[t1_idx:t2_idx + 1]
    neckline = float(np.min(inter_lows))
    avg_top = (t1_val + t2_val) / 2
    if (avg_top - neckline) / avg_top < cfg.pa_min_neckline_height:
        return None

    # Confirmed breakdown below the neckline within the last `pa_confirm_bars`
    # bars, price still below it (windowed; see _fresh_breakout).
    if _fresh_breakout(closes, neckline, "short", cfg.pa_confirm_bars):
        return {
            "pattern": "double_top",
            "direction": "short",
            "entry": round(float(closes[-1]), 4),
            "neckline": round(neckline, 4),
            "stop_loss": round(max(t1_val, t2_val) * 1.002, 4),  # invalidation above pattern high
        }

    return None


def detect_bearish_consolidation(
    highs: NDArray, lows: NDArray, closes: NDArray, cfg: ScalpingConfig
) -> Optional[dict]:
    """Horizontal-range breakdown (bearish). Mirror of the bullish breakout:
    a tight prior range and a FRESH close below its floor (not just price sitting
    in the lower part of a band)."""
    lookback = cfg.pa_lookback_bars
    w = max(1, min(cfg.pa_confirm_bars, len(closes) - 2))
    if len(closes) < lookback + w + 1:
        return None
    h = highs[-lookback - w:-w]
    l = lows[-lookback - w:-w]
    if len(h) < 5:
        return None
    range_high = float(np.max(h))
    range_low = float(np.min(l))
    mid_price = (range_high + range_low) / 2
    if mid_price == 0 or range_high == range_low:
        return None
    if (range_high - range_low) / mid_price > 0.03:
        return None
    # Confirmed breakdown within the last `w` bars, price still below the range floor.
    if not _fresh_breakout(closes, range_low, "short", w):
        return None
    return {
        "pattern": "range_breakdown",
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
    ts15 = np.array([c.timestamp_ms for c in candles_15m], dtype=np.int64)
    lookback = min(cfg.pa_lookback_bars, len(c15) - 1)
    # Per the strategy doc, the price-action target is the closest *15-minute*
    # key level (not the 4H level used for the entry structure).
    levels_15m = detect_levels(h15, l15, c15, ts15, cfg)

    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    if nearby.level_type == "support" and cfg.allow_long:
        # Try bullish patterns in order (all 5 from the strategy doc)
        result = detect_ascending_triangle(h15, l15, c15, cfg)
        if result is None:
            result = detect_double_bottom(h15, l15, c15, cfg)
        if result is None:
            result = detect_inverse_head_shoulders(h15, l15, c15, cfg)
        if result is None:
            result = detect_cup_handle(h15, l15, c15, cfg)
        if result is None:
            result = detect_bullish_consolidation(h15, l15, c15, cfg)
        if result is not None:
            pattern = result["pattern"]
            direction = "long"
            entry = result.get("entry", round(current_price, 4))
            structure_stop = float(result.get("stop_loss", result.get("stop_below", nearby.price * 0.98)))
            plan = resolve_trade_risk(
                direction="long", entry=entry, structure_stop=structure_stop,
                atr_val=atr(h15, l15, c15), levels=levels_15m, tp_level_type="resistance",
                min_rr=cfg.pa_min_rr,
            )
            if plan.ok:
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"{pattern} long, 15m breakout above neckline near 4H support {nearby.price:.0f} · R:R {plan.rr}"
            else:
                entry = stop_loss = take_profit = None
                reason = f"{pattern} near 4H support {nearby.price:.0f} — skipped: {plan.reason}"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        # Try bearish patterns in order (all 5 from the strategy doc)
        result = detect_descending_triangle(h15, l15, c15, cfg)
        if result is None:
            result = detect_double_top(h15, l15, c15, cfg)
        if result is None:
            result = detect_head_shoulders(h15, l15, c15, cfg)
        if result is None:
            result = detect_inverse_cup_handle(h15, l15, c15, cfg)
        if result is None:
            result = detect_bearish_consolidation(h15, l15, c15, cfg)
        if result is not None:
            pattern = result["pattern"]
            direction = "short"
            entry = result.get("entry", round(current_price, 4))
            structure_stop = float(result.get("stop_loss", result.get("stop_above", nearby.price * 1.02)))
            plan = resolve_trade_risk(
                direction="short", entry=entry, structure_stop=structure_stop,
                atr_val=atr(h15, l15, c15), levels=levels_15m, tp_level_type="support",
                min_rr=cfg.pa_min_rr,
            )
            if plan.ok:
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"{pattern} short, 15m breakdown below neckline near 4H resistance {nearby.price:.0f} · R:R {plan.rr}"
            else:
                entry = stop_loss = take_profit = None
                reason = f"{pattern} near 4H resistance {nearby.price:.0f} — skipped: {plan.reason}"

    if not pattern:
        reason = f"near 4H {nearby.level_type} @ {nearby.price:.0f} — no confirmed pattern"

    return PriceActionSignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(nearby.price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source if 'tp_source' in locals() else "",
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
    )