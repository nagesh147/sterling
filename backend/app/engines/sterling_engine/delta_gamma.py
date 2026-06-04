"""Delta-Gamma Risk Surface module.

This module proxies Options Market Maker (dealer) positioning.
In the absence of live Delta Exchange India options open interest data, it models
Gamma Exposure (GEX) walls based on heavy psychological round numbers which
historically attract massive option open interest (e.g., BTC at $70,000, $65,000).

Dealers hedge by selling into resistance (Call Walls) and buying into support (Put Walls),
dampening volatility (positive gamma environment). When price breaks these walls,
it triggers violent forced hedging (negative gamma squeeze).
"""
from __future__ import annotations

import math
from typing import Optional

from app.engines.sterling_engine.config import ScalpingProfile
from app.engines.sterling_engine.schemas import ScalpingSignal


def _get_major_strike_interval(price: float) -> float:
    """Determine the major options strike interval based on asset price magnitude.
    For BTC ($60k), strikes are heavy every $1000, massive every $5000.
    For ETH ($3k), heavy every $100, massive every $500.
    For SOL ($150), heavy every $10, massive every $50.
    """
    if price > 10000:
        return 1000.0  # e.g., BTC
    elif price > 1000:
        return 100.0   # e.g., ETH
    elif price > 100:
        return 10.0    # e.g., SOL
    elif price > 10:
        return 1.0     # e.g., LINK, DOT
    elif price > 1:
        return 0.1     # e.g., ADA, MATIC
    else:
        return 0.01    # e.g., DOGE


def _estimate_gamma_walls(price: float) -> tuple[float, float]:
    """Estimate the nearest Put Wall (below) and Call Wall (above).
    Returns (put_wall, call_wall).
    """
    interval = _get_major_strike_interval(price)
    # The nearest massive wall is usually 5x the normal interval (e.g. 5000 for BTC)
    massive_interval = interval * 5.0
    
    put_wall = math.floor(price / massive_interval) * massive_interval
    call_wall = math.ceil(price / massive_interval) * massive_interval
    
    # If we are exactly on the wall, find the next one
    if put_wall == price:
        put_wall -= massive_interval
    if call_wall == price:
        call_wall += massive_interval
        
    return put_wall, call_wall


def evaluate_delta_gamma(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list,
    cfg: ScalpingProfile,
) -> ScalpingSignal:
    """Evaluates the Delta-Gamma risk surface.
    
    Generates a counter-trend (mean reversion) signal when price approaches
    a massive gamma wall (due to dealer hedging suppressing volatility).
    """
    if not candles_15m:
        return ScalpingSignal(
            underlying=underlying, strategy="delta_gamma", direction="none", close=0.0,
            reason="no data", entry_ok=False, executable=False, timestamp_ms=0,
        )
        
    current_price = float(candles_15m[-1].close)
    
    # Estimate massive gamma walls (proxies for OI concentration)
    put_wall, call_wall = _estimate_gamma_walls(current_price)
    
    # Calculate proximity to walls
    call_proximity = (call_wall - current_price) / current_price
    put_proximity = (current_price - put_wall) / current_price
    
    threshold_pct = cfg.dg_wall_proximity_pct  # e.g., 0.005 (0.5%)
    
    direction = "none"
    reason = f"Mid-gamma environment. Nearest Call Wall: {call_wall:,.2f}, Put Wall: {put_wall:,.2f}"
    entry = None
    stop_loss = None
    take_profit = None
    entry_ok = False
    
    # Check if we are pinning against a Call Wall (Positive Gamma resistance)
    if call_proximity <= threshold_pct and cfg.allow_short:
        direction = "short"
        reason = f"Price pinning Call Wall ({call_wall:,.2f}). Dealer hedging (Positive Gamma) implies resistance."
        entry = current_price
        # Stop slightly above the wall (if wall breaks, negative gamma squeeze)
        stop_loss = call_wall * 1.005 
        # Target the midpoint between walls
        take_profit = current_price - (current_price - put_wall) * 0.3
        entry_ok = True
        
    # Check if we are pinning against a Put Wall (Positive Gamma support)
    elif put_proximity <= threshold_pct and cfg.allow_long:
        direction = "long"
        reason = f"Price pinning Put Wall ({put_wall:,.2f}). Dealer hedging (Positive Gamma) implies support."
        entry = current_price
        # Stop slightly below the wall
        stop_loss = put_wall * 0.995
        # Target the midpoint between walls
        take_profit = current_price + (call_wall - current_price) * 0.3
        entry_ok = True

    return ScalpingSignal(
        underlying=underlying,
        strategy="delta_gamma",
        direction=direction,
        close=current_price,
        reason=reason,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        tp_source="gamma_midpoint",
        entry_ok=entry_ok,
        executable=entry_ok,
        timestamp_ms=candles_15m[-1].timestamp_ms,
    )
