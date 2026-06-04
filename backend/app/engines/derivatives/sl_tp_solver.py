"""SL/TP resolution for futures + options.

Futures path delegates to the existing scalping risk solver which
handles ATR cushion, anti-stop-hunt, R:R gating, and max-stop-ATR cap.

Options path takes spot SL/TP from the signal and computes the
EQUIVALENT premium SL/TP via BSM (time-shifted revaluation already
gave us premium_at_tp / premium_at_sl). The premium SL has a floor
at 50% of entry premium so a tiny adverse move can't immediately
trigger close due to ordinary bid-ask noise — Plan-agent's anti-
whipsaw rule, mirroring what we already do in the monitor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class SLTPResolution:
    ok: bool
    stop_loss: Optional[float]              # spot SL (futures + options)
    take_profit: Optional[float]            # spot TP
    sl_premium: Optional[float] = None      # options-only — BSM-derived
    tp_premium: Optional[float] = None      # options-only — BSM-derived
    tp_source: str = ""
    rr: float = 0.0
    risk_pct: float = 0.0
    reason: str = ""


def solve_futures(
    *, direction: str, entry: float, structure_stop: float,
    atr_val: float, take_profit: Optional[float], rr: float = 2.0,
    validated: bool = False,
) -> SLTPResolution:
    """Wrap app/engines/sterling_engine/risk.resolve_trade_risk for futures.

    For the integration path we have a direct stop/target so we synthesize
    a degenerate "levels" list with just the target and ask the solver to
    produce the cushioned SL + R:R-gated TP.

    `validated=True` (edge feed): the stop/target were already proven in the
    backtest with this exact geometry, so we pass them through unchanged —
    no anti-stop-hunt cushion, no scalping risk-cap, no R:R re-gate. Adding
    those would make the live trade differ from the validated one. We still
    reject geometrically-incoherent stops (wrong side of entry).
    """
    if validated:
        is_long = direction == "long"
        bad_stop = (is_long and structure_stop >= entry) or \
                   (not is_long and structure_stop <= entry)
        if bad_stop or entry <= 0:
            return SLTPResolution(ok=False, stop_loss=None, take_profit=None,
                                  reason="validated stop on wrong side of entry")
        stop_dist = abs(entry - structure_stop)
        rr_val = (abs(take_profit - entry) / stop_dist
                  if take_profit and stop_dist > 0 else 0.0)
        return SLTPResolution(
            ok=True, stop_loss=structure_stop, take_profit=take_profit,
            tp_source="validated", rr=round(rr_val, 3),
            risk_pct=stop_dist / entry * 100.0, reason="ok",
        )

    from app.engines.sterling_engine.risk import resolve_trade_risk
    from dataclasses import dataclass as _dc

    @_dc
    class _L:
        price: float
        level_type: str

    is_long = direction == "long"
    tp_level_type = "resistance" if is_long else "support"
    # Provide the supplied TP as the structural level; solver R:R-gates.
    levels = [_L(price=take_profit, level_type=tp_level_type)] if take_profit else []

    plan = resolve_trade_risk(
        direction=direction, entry=entry, structure_stop=structure_stop,
        atr_val=atr_val, levels=levels, tp_level_type=tp_level_type,
        min_rr=rr,
    )

    return SLTPResolution(
        ok=plan.ok, stop_loss=plan.stop_loss, take_profit=plan.take_profit,
        tp_source=plan.tp_source, rr=plan.rr, risk_pct=plan.risk_pct,
        reason=plan.reason,
    )


def solve_options(
    *, direction: str, entry_spot: float, stop_spot: float, target_spot: float,
    premium_now: float, premium_at_tp: float, premium_at_sl: float,
    premium_floor_pct: float = 0.50, expected_hold_days: float = 0.0,
    current_iv: float = 0.0, entry_iv: float = 0.0,
) -> SLTPResolution:
    """Spot SL/TP pass through unchanged; option SL/TP premium derives
    from BSM (caller already computed via time_shifted_revaluation)
    with a floor at `premium_floor_pct × premium_now` so noise can't
    trigger.
    
    Hybrid Approach:
    Monitors both option premium and underlying. Trigger SL if either:
    - Option mark drops to SL_premium.
    - Underlying hits invalidation (stop_spot).
    """
    if premium_now <= 0:
        return SLTPResolution(ok=False, stop_loss=None, take_profit=None,
                               reason="bsm_no_premium")

    # Add a 10-20% buffer for slippage/theta over the BSM SL
    buffer = 1.10
    
    # Dynamic IV bump: pad the SL if in high vol regime
    if current_iv > 0.60:
        buffer = 1.20 # assume a harsher crush
        
    sl_premium = max(premium_at_sl * buffer, premium_floor_pct * premium_now)
    tp_premium = premium_at_tp

    # Extra Guards: IV Crush & Theta
    if entry_iv > 0 and current_iv > 0:
        iv_drop_pct = (entry_iv - current_iv) / entry_iv
        if iv_drop_pct > 0.15: # IV drops > 15%
            sl_premium = max(sl_premium * 1.20, premium_floor_pct * premium_now)
            
    if expected_hold_days > 1.0: # > 24h holds
        sl_premium = max(sl_premium * 1.15, premium_floor_pct * premium_now)

    risk_pct = abs(entry_spot - stop_spot) / entry_spot * 100 if entry_spot else 0.0
    rr = (premium_at_tp - premium_now) / max(1e-9, premium_now - sl_premium)

    return SLTPResolution(
        ok=True, stop_loss=stop_spot, take_profit=target_spot,
        sl_premium=round(sl_premium, 4), tp_premium=round(tp_premium, 4),
        tp_source="bsm_at_exit_T_hybrid", rr=round(rr, 3), risk_pct=risk_pct,
        reason="ok",
    )
