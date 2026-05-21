"""
Hybrid VCP-Momentum Scalper — Strategy V2
Exit rules: initial stop, TP partials, Chandelier trailing, time stop, trend flip.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class ExitReason(str, Enum):
    STOP_OUT       = "stop_out"
    TP_PARTIAL     = "tp_partial"
    TRAIL_STOP     = "trail_stop"
    TIME_STOP      = "time_stop"
    TREND_FLIP     = "trend_flip"
    END_OF_DATA    = "end_of_data"


@dataclass(frozen=True)
class ExitResult:
    reason:       ExitReason
    exit_price:   float
    pnl_pct:       float
    partial_pct:   float = 0.0   # fraction of position closed (0.0 or 0.5)
    new_stop:      float = 0.0  # updated stop for remaining position


@dataclass(frozen=True)
class PositionState:
    entry_price:   float
    direction:     int          # +1 long, -1 short
    entry_bar:      int
    stop_price:     float
    tp_price:       float
    trail_active:   bool = False
    trail_extreme:  float = 0.0   # highest seen (long) / lowest seen (short)
    tp1_done:       bool = False  # 50% partial filled
    bars_in_trade:  int   = 0


# ──────────────────────────────────────────────────────────────────────────────
# Exit Config
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExitConfig:
    stop_mult:      float = 0.9    # × ATR for initial stop
    tp1_mult:       float = 1.5    # × ATR for first TP (50% partial)
    tp2_mult:       float = 2.5    # × ATR for full trail target
    trail_mult:      float = 0.5    # × ATR for Chandelier trail distance
    ratchet_only:   bool  = True   # trail can only tighten, never widen
    hold_bars:      int   = 16     # time stop
    breakeven_after_tp1: bool = True  # move stop to breakeven after TP1


def check_exits(
    pos:        PositionState,
    current_bar: int,
    closes:     NDArray[np.float64],
    highs:      NDArray[np.float64],
    lows:       NDArray[np.float64],
    atr:        NDArray[np.float64],
    trend:      int,              # current signal trend: +1 bull, -1 bear, 0 none
    config:     Optional[ExitConfig] = None,
) -> list[ExitResult]:
    """
    Evaluate all exit conditions. Returns list of ExitResult (may be empty, or 1-2 exits
    if TP partial + stop out happen on the same bar).
    """
    cfg = config or ExitConfig()
    exits: list[ExitResult] = []
    n = len(closes)

    if current_bar >= n or current_bar < 0:
        return exits

    close  = float(closes[current_bar])
    high   = float(highs[current_bar])
    low    = float(lows[current_bar])
    cur_atr = float(atr[current_bar]) if current_bar < len(atr) else 1.0
    dir_   = pos.direction

    # Bars in trade
    bars_held = current_bar - pos.entry_bar

    # ── Time stop ──────────────────────────────────────────────
    if bars_held >= cfg.hold_bars:
        pnl = dir_ * (close - pos.entry_price) / pos.entry_price
        exits.append(ExitResult(ExitReason.TIME_STOP, close, pnl))
        return exits

    # ── Trend flip ─────────────────────────────────────────────
    if trend != 0 and dir_ != trend:
        pnl = dir_ * (close - pos.entry_price) / pos.entry_price
        exits.append(ExitResult(ExitReason.TREND_FLIP, close, pnl))
        return exits

    # ── Stop loss ───────────────────────────────────────────────
    if dir_ == 1:   # long
        if low <= pos.stop_price:
            pnl = dir_ * (pos.stop_price - pos.entry_price) / pos.entry_price
            exits.append(ExitResult(ExitReason.STOP_OUT, float(pos.stop_price), pnl))
            return exits
    else:           # short
        if high >= pos.stop_price:
            pnl = dir_ * (pos.stop_price - pos.entry_price) / pos.entry_price
            exits.append(ExitResult(ExitReason.STOP_OUT, float(pos.stop_price), pnl))
            return exits

    # ── TP1: 50% partial ────────────────────────────────────────
    if not pos.tp1_done:
        tp1_price = pos.entry_price + dir_ * cfg.tp1_mult * cur_atr
        if (dir_ == 1 and close >= tp1_price) or (dir_ == -1 and close <= tp1_price):
            pnl_partial = dir_ * (tp1_price - pos.entry_price) / pos.entry_price * 0.5
            exits.append(ExitResult(
                ExitReason.TP_PARTIAL,
                float(tp1_price),
                pnl_partial,
                partial_pct=0.5,
            ))
            # Return early — remaining position has new stop managed below
            return exits

    # ── Trail stop (remaining position after TP1) ──────────────
    if pos.trail_active:
        if dir_ == 1:   # long: trail tracks the extreme
            new_extreme = max(pos.trail_extreme, high)
            trail_price = new_extreme - cfg.trail_mult * cur_atr
            if trail_price > pos.stop_price:
                new_stop = trail_price
            else:
                new_stop = pos.stop_price
        else:           # short
            new_extreme = min(pos.trail_extreme, low)
            trail_price = new_extreme + cfg.trail_mult * cur_atr
            if trail_price < pos.stop_price:
                new_stop = trail_price
            else:
                new_stop = pos.stop_price

        if dir_ == 1 and low <= new_stop:
            remaining_pnl = dir_ * (new_stop - pos.entry_price) / pos.entry_price
            # Account for already-closed 50% via TP1
            exits.append(ExitResult(ExitReason.TRAIL_STOP, float(new_stop), remaining_pnl))
            return exits
        elif dir_ == -1 and high >= new_stop:
            remaining_pnl = dir_ * (new_stop - pos.entry_price) / pos.entry_price
            exits.append(ExitResult(ExitReason.TRAIL_STOP, float(new_stop), remaining_pnl))
            return exits

    return exits


def next_stop_price(
    pos:        PositionState,
    current_bar: int,
    closes:     NDArray[np.float64],
    highs:      NDArray[np.float64],
    lows:       NDArray[np.float64],
    atr:        NDArray[np.float64],
    tp1_fired:  bool,
    config:     Optional[ExitConfig] = None,
) -> float:
    """Compute the current stop price for the active position."""
    cfg = config or ExitConfig()
    n = len(closes)
    if current_bar >= n:
        return pos.stop_price

    cur_atr = float(atr[current_bar]) if current_bar < len(atr) else 1.0
    dir_ = pos.direction

    if not tp1_fired:
        return pos.stop_price

    # After TP1: stop is at breakeven if configured, else trail
    if cfg.breakeven_after_tp1:
        return pos.entry_price

    # Chandelier trail
    if dir_ == 1:
        extreme = float(np.max(highs[pos.entry_bar:current_bar + 1]))
        return max(pos.stop_price, extreme - cfg.trail_mult * cur_atr)
    else:
        extreme = float(np.min(lows[pos.entry_bar:current_bar + 1]))
        return min(pos.stop_price, extreme + cfg.trail_mult * cur_atr)