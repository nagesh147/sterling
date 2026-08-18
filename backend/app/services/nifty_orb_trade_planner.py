"""Option-buying trade-plan layer for the NIFTY ORB universe scanner.

This module deliberately performs no broker I/O. It converts an underlying ORB
signal plus a normalized option chain into one executable BUY-CE/BUY-PE plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.engines.nifty_orb_options import (
    OptionContract,
    Signal,
    StrategyConfig,
    TradePlan,
    build_trade_plan,
    select_option,
)
from app.engines.nifty_orb_universe import UniverseSignal


@dataclass(frozen=True)
class PlannedSignal:
    symbol: str
    kind: str
    signal: Signal
    option: OptionContract
    trade_plan: TradePlan


def plan_signal(
    candidate: UniverseSignal,
    contracts: Sequence[OptionContract],
    cfg: StrategyConfig,
) -> PlannedSignal:
    """Resolve the best liquid option and construct the risk-capped BUY plan."""
    signal = candidate.signal
    if signal.direction not in ("LONG", "SHORT"):
        raise ValueError("Cannot create an option plan from a neutral signal")

    option = select_option(
        spot=signal_to_spot(signal),
        direction=signal.direction,
        contracts=contracts,
        cfg=cfg,
    )
    plan = build_trade_plan(
        signal,
        option,
        cfg,
        spot=signal_to_spot(signal),
    )
    if plan.quantity <= 0:
        raise ValueError("Configured INR risk is below one option lot")
    return PlannedSignal(
        symbol=candidate.instrument.symbol,
        kind=candidate.instrument.kind,
        signal=signal,
        option=option,
        trade_plan=plan,
    )


def signal_to_spot(signal: Signal) -> float:
    """Recover the underlying spot from the ORB boundary plus breakout distance.

    LONG: spot = OR high + breakout distance.
    SHORT: spot = OR low - breakout distance.
    """
    if signal.direction == "LONG":
        return float(signal.or_high + signal.breakout_distance)
    if signal.direction == "SHORT":
        return float(signal.or_low - signal.breakout_distance)
    raise ValueError("Neutral signals do not have an option spot")
