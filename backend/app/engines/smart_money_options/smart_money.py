"""Smart Money Footprint and Volume Surge Analysis."""
from __future__ import annotations

from typing import Sequence
from app.engines.smart_money_options.models import Candle, SmartMoneyMetrics


def analyze_smart_money_volume(
    candles: Sequence[Candle],
    volume_surge_multiplier: float = 1.8,
    lookback: int = 20,
) -> SmartMoneyMetrics:
    """Evaluate relative volume (RVOL) and institutional footprint pressure."""
    if not candles:
        return SmartMoneyMetrics(
            rvol=1.0,
            avg_volume=1.0,
            current_volume=1.0,
            delta_pressure=0.0,
            is_institutional_surge=False,
            footprint_score=0.0,
        )

    current_bar = candles[-1]
    hist = candles[:-1][-lookback:] if len(candles) > 1 else [current_bar]
    volumes = [c.volume for c in hist if c.volume > 0]
    avg_vol = sum(volumes) / len(volumes) if volumes else (current_bar.volume or 1.0)
    avg_vol = max(avg_vol, 1.0)

    cur_vol = current_bar.volume
    rvol = cur_vol / avg_vol

    # Estimate delta pressure: position of close within high-low range + body direction
    bar_range = current_bar.high - current_bar.low
    if bar_range > 0:
        # Normalized location: -1.0 (closed at low) to +1.0 (closed at high)
        loc = ((current_bar.close - current_bar.low) / bar_range) * 2.0 - 1.0
        # Body directional bias
        body = (current_bar.close - current_bar.open) / bar_range
        delta_pressure = round(loc * 0.6 + body * 0.4, 2)
        body_pct = abs(current_bar.close - current_bar.open) / bar_range
    else:
        delta_pressure = 0.0
        body_pct = 0.0

    # Footprint score calculation (0 - 100)
    # 1. RVOL contribution (up to 50 pts)
    rvol_score = min(50.0, (rvol / volume_surge_multiplier) * 40.0)
    # 2. Delta & close location contribution (up to 30 pts)
    loc_score = min(30.0, abs(delta_pressure) * 30.0)
    # 3. Body expansion contribution (up to 20 pts)
    body_score = min(20.0, body_pct * 20.0)

    footprint_score = min(100.0, max(0.0, rvol_score + loc_score + body_score))
    is_surge = rvol >= volume_surge_multiplier and footprint_score >= 60.0

    return SmartMoneyMetrics(
        rvol=round(rvol, 2),
        avg_volume=round(avg_vol, 0),
        current_volume=round(cur_vol, 0),
        delta_pressure=delta_pressure,
        is_institutional_surge=is_surge,
        footprint_score=round(footprint_score, 1),
    )
