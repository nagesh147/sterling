"""Strategy 4: Mean Reversion (Z-Score).

Uses Z-Score (standard deviations from the mean) to identify overextended price action.
If price reaches an extreme Z-Score (e.g., > 2.5 or < -2.5) and is near a 4H level,
it looks for a mean reversion setup.

  Bullish (near 4H support): Z-Score < -2.0 -> price is oversold, look for bounce.
  Bearish (near 4H resistance): Z-Score > 2.0 -> price is overbought, look for reversal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level
from app.engines.scalping.risk import resolve_trade_risk


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
class MeanReversionSignal:
    underlying: str
    direction: str          # "long" | "short" | "none"
    pattern: str            # "oversold_zscore" | "overbought_zscore"
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str
    entry_ok: bool
    timestamp_ms: int
    tp_source: str = ""
    z_score: float = 0.0


def evaluate_mean_reversion(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> MeanReversionSignal:
    """Evaluate Strategy 4: Mean Reversion (Z-Score)."""
    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < 30 or len(candles_4h) < 20:
        return MeanReversionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not getattr(cfg, "enable_mean_reversion", False):
        return MeanReversionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 3)
    if nearby is None:
        return MeanReversionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H level", entry_ok=False, timestamp_ms=now_ms,
        )

    closes = np.array([c.close for c in candles_15m], dtype=np.float64)
    lows_15m = np.array([c.low for c in candles_15m], dtype=np.float64)
    highs_15m = np.array([c.high for c in candles_15m], dtype=np.float64)

    # Z-Score Calculation
    window = getattr(cfg, "mr_zscore_window", 20)
    if len(closes) < window:
        return MeanReversionSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=round(nearby.price, 4), level_type=nearby.level_type,
            entry=None, stop_loss=None, take_profit=None,
            reason="Z-Score warmup incomplete", entry_ok=False, timestamp_ms=now_ms,
        )
    
    recent_closes = closes[-window:]
    mean = np.mean(recent_closes)
    std = np.std(recent_closes)
    if std == 0:
        z_score = 0.0
    else:
        z_score = (current_price - mean) / std

    threshold = getattr(cfg, "mr_zscore_threshold", 2.0)
    atr_val = current_atr(closes, highs_15m, lows_15m)

    level_price = nearby.price
    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False
    tp_source = ""

    if nearby.level_type == "support" and cfg.allow_long:
        if z_score <= -threshold:
            # Oversold at support -> Long
            entry = round(current_price, 4)
            plan = resolve_trade_risk(
                direction="long", entry=entry, structure_stop=min(level_price, current_price),
                atr_val=atr_val, levels=levels, tp_level_type="resistance",
                max_risk_pct=4.0, max_stop_atr=cfg.max_stop_atr, min_rr=cfg.min_rr,
            )
            if plan.ok:
                direction = "long"; pattern = "oversold_zscore"
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"Z-Score {z_score:.2f} (<= -{threshold}) near 4H support {level_price:.0f} · R:R {plan.rr}"
            else:
                reason = f"oversold near 4H support {level_price:.0f} — skipped: {plan.reason}"
        else:
            reason = f"Watching: Z-Score {z_score:.2f} near 4H support {level_price:.0f} — awaiting oversold (<= -{threshold})"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        if z_score >= threshold:
            # Overbought at resistance -> Short
            entry = round(current_price, 4)
            plan = resolve_trade_risk(
                direction="short", entry=entry, structure_stop=max(level_price, current_price),
                atr_val=atr_val, levels=levels, tp_level_type="support",
                max_risk_pct=4.0, max_stop_atr=cfg.max_stop_atr, min_rr=cfg.min_rr,
            )
            if plan.ok:
                direction = "short"; pattern = "overbought_zscore"
                stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                entry_ok = True
                reason = f"Z-Score {z_score:.2f} (>= {threshold}) near 4H resistance {level_price:.0f} · R:R {plan.rr}"
            else:
                reason = f"overbought near 4H resistance {level_price:.0f} — skipped: {plan.reason}"
        else:
            reason = f"Watching: Z-Score {z_score:.2f} near 4H resistance {level_price:.0f} — awaiting overbought (>= {threshold})"

    if not pattern and "Watching" not in reason and "skipped" not in reason:
        reason = f"near 4H {nearby.level_type} @ {level_price:.0f} — Z-Score: {z_score:.2f}"

    return MeanReversionSignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source,
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
        z_score=round(float(z_score), 2),
    )
