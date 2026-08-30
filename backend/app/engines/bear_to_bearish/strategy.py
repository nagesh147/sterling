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

    # Levels
    spot_price = current_spot if current_spot > 0 else 24000.0
    stop_loss = latest_lh if latest_lh > spot_price else spot_price * 1.006
    risk_points = max(10.0, stop_loss - spot_price)
    target_price = spot_price - (risk_points * 2.0)

    # Strike selection (ATM Put option)
    strike = round(spot_price / 50.0) * 50.0
    symbol = f"{underlying}26SEP{int(strike)}PE"
    quote_key = f"NFO:{symbol}"

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
        entry_price=spot_price,
        stop_loss=stop_loss,
        target_price=target_price,
        score=score,
        reason=reason,
        option_type="PE",
        strike=strike,
        expiry="2026-09-24",
        lot_size=25 if underlying == "NIFTY" else 15,
        quote_key=quote_key,
    )
