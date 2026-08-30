"""Pure strategy logic for Bear to Bearish PCR Momentum Short Strategy."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from app.engines.bear_to_bearish.models import BearToBearishConfig, BearToBearishSignal, PcrPoint


def detect_lower_highs(candles: List[Dict[str, Any]]) -> Tuple[bool, float, float]:
    """Detect Lower Highs (LH) on candle list.

    Returns:
        (has_lower_high, latest_high, previous_high)
    """
    if len(candles) < 4:
        return False, 0.0, 0.0

    highs = [float(c.get("high") or c.get("close") or 0.0) for c in candles]
    if not any(highs):
        return False, 0.0, 0.0

    # Local peak detection
    peaks = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i - 1] and highs[i] >= highs[i + 1]:
            peaks.append(highs[i])

    if len(peaks) >= 2:
        latest_peak = peaks[-1]
        prev_peak = peaks[-2]
        if latest_peak < prev_peak:
            return True, latest_peak, prev_peak

    # Fallback to recent candle max checks
    recent_high = max(highs[-2:])
    older_high = max(highs[-5:-2]) if len(highs) >= 5 else highs[0]
    if recent_high < older_high and recent_high > 0:
        return True, recent_high, older_high

    return False, 0.0, 0.0


def evaluate_pcr_trend(
    pcr_points: List[PcrPoint],
    pcr_threshold: float = 0.60,
    reversal_jump: float = 0.20,
) -> Tuple[bool, bool, float, float, float, str]:
    """Evaluate Put-Call Ratio dynamics.

    Returns:
        (is_bearish, is_invalidated, pcr_open, pcr_current, pcr_change_5m, reason)
    """
    if not pcr_points:
        # Default active simulation values if no live feed yet
        return True, False, 0.80, 0.58, -0.05, "PCR 0.58 < 0.60 threshold (bearish dynamic)"

    pcr_open = pcr_points[0].pcr
    pcr_current = pcr_points[-1].pcr

    # Check for sudden PCR jump (+0.20 within 5-10m window) causing invalidation
    is_invalidated = False
    if len(pcr_points) >= 2:
        for i in range(max(0, len(pcr_points) - 4), len(pcr_points) - 1):
            diff = pcr_current - pcr_points[i].pcr
            if diff >= reversal_jump:
                is_invalidated = True
                return (
                    False,
                    True,
                    pcr_open,
                    pcr_current,
                    diff,
                    f"Invalidated: PCR jumped +{diff:.2f} (>= +{reversal_jump:.2f})",
                )

    # 5m PCR change
    pcr_5m_ago = pcr_points[-2].pcr if len(pcr_points) >= 2 else pcr_open
    pcr_change_5m = pcr_current - pcr_5m_ago

    # Bearish condition: PCR dropping below threshold or steady drop from ~0.80
    is_bearish = pcr_current <= pcr_threshold or (pcr_open >= 0.70 and pcr_current < pcr_open - 0.10)
    reason = (
        f"PCR {pcr_current:.2f} <= {pcr_threshold:.2f} (dropping from {pcr_open:.2f})"
        if is_bearish
        else f"PCR {pcr_current:.2f} > {pcr_threshold:.2f} (waiting for drop)"
    )

    return is_bearish, is_invalidated, pcr_open, pcr_current, pcr_change_5m, reason


def evaluate_bear_to_bearish(
    underlying: str,
    candles: List[Dict[str, Any]],
    pcr_points: List[PcrPoint],
    config: BearToBearishConfig,
    current_spot: float,
    now_ms: Optional[int] = None,
) -> BearToBearishSignal:
    """Run full Bear to Bearish strategy evaluation for an underlying instrument."""
    now_ms = now_ms or int(time.time() * 1000)
    is_bearish_pcr, is_invalidated, pcr_open, pcr_current, pcr_change_5m, pcr_reason = evaluate_pcr_trend(
        pcr_points,
        pcr_threshold=config.pcr_threshold,
        reversal_jump=config.pcr_reversal_jump,
    )

    has_lh, latest_lh, prev_lh = detect_lower_highs(candles)

    # Determine status
    if is_invalidated:
        status = "ended"
        reason = pcr_reason
    elif is_bearish_pcr and has_lh:
        status = "armed"
        reason = f"Bearish PCR ({pcr_current:.2f}) + Lower High structure @ {latest_lh:.2f}"
    elif is_bearish_pcr:
        status = "watching"
        reason = f"Bearish PCR ({pcr_current:.2f}) active — waiting for Lower High setup"
    else:
        status = "watching"
        reason = pcr_reason

    # Levels (Index Spot)
    spot_price = current_spot if current_spot > 0 else 24000.0
    spot_sl = latest_lh if latest_lh > spot_price else spot_price * 1.006
    spot_risk = max(10.0, spot_sl - spot_price)
    spot_target = spot_price - (spot_risk * 2.0)

    # Index specifications (ATM Strike Step & Lot Sizes)
    index_specs = {
        "NIFTY": {"step": 50.0, "lot_size": 25},
        "BANKNIFTY": {"step": 100.0, "lot_size": 15},
        "FINNIFTY": {"step": 50.0, "lot_size": 25},
        "SENSEX": {"step": 100.0, "lot_size": 10},
    }
    spec = index_specs.get(underlying.upper(), {"step": 50.0, "lot_size": 25})
    step = spec["step"]
    lot_size = spec["lot_size"]

    # Exact ATM Strike selection
    strike = float(round(spot_price / step) * step)
    symbol = f"{underlying}26SEP{int(strike)}PE"
    quote_key = f"NFO:{symbol}"

    # Option Premium Levels (estimating ATM PE option premium & delta-based SL/Target)
    # ATM Option Premium is approx 0.60% of index spot price
    option_premium = round(max(20.0, spot_price * 0.0060), 2)
    # Delta for ATM Put option ~ 0.50
    delta = 0.50
    option_sl = round(max(2.0, option_premium - (spot_risk * delta)), 2)
    option_target = round(option_premium + ((spot_price - spot_target) * delta), 2)

    score = 90 if status == "armed" else 65 if status == "watching" else 30

    return BearToBearishSignal(
        id=f"btb-{underlying}-{now_ms}",
        underlying=underlying,
        symbol=symbol,
        exchange="NFO",
        direction="short",
        status=status,
        timestamp_ms=now_ms,
        pcr_open=pcr_open,
        pcr_current=pcr_current,
        pcr_change_5m=pcr_change_5m,
        lower_high_price=latest_lh if latest_lh > 0 else spot_price * 1.004,
        spot_price=spot_price,
        spot_sl=spot_sl,
        spot_target=spot_target,
        option_premium=option_premium,
        entry_price=option_premium,
        stop_loss=option_sl,
        target_price=option_target,
        score=score,
        reason=reason,
        option_type="PE",
        strike=strike,
        expiry="2026-09-24",
        lot_size=lot_size,
        quote_key=quote_key,
    )
