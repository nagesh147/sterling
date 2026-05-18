"""
Truthful trade-cost attribution for backtests.

Pure functions. No I/O, no DB calls, no time.time(), no exchange calls.

Computes a full breakdown of gross PnL, slippage, taker fees, perpetual
funding accrual, and (optional) option bid/ask half-spread cost. The
attribution always satisfies:

    total_cost_pct = slippage_pct + fee_pct + funding_pct + option_spread_pct
    net_pnl_pct    = gross_pnl_pct - total_cost_pct

Slippage is applied symmetrically as an effective entry/exit price so that
long fills are always worsened (entry up, exit down) and short fills are
always worsened (entry down, exit up). The price-level adjustment is exposed
as `effective_entry_price` and `effective_exit_price` for inspection; the
cost-level attribution uses `slippage_pct` (round-trip) so callers cannot
double-count.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from app.engines.risk.slippage import slippage_bps


@dataclass
class CostBreakdown:
    direction: int                # +1 long, -1 short
    entry_price: float            # clean entry (pre-slippage)
    exit_price: float             # clean exit (pre-slippage)
    effective_entry_price: float  # entry adjusted for slippage
    effective_exit_price: float   # exit adjusted for slippage
    gross_pnl_pct: float          # direction * (exit - entry) / entry
    slippage_bps: float           # one-side slippage in basis points
    slippage_pct: float           # round-trip slippage as pct of notional
    fee_pct: float                # round-trip taker fee
    funding_pct: float            # signed funding cost (positive = drag)
    option_spread_pct: float      # round-trip option bid/ask half-spread cost
    total_cost_pct: float         # sum of all cost components (signed)
    net_pnl_pct: float            # gross - total_cost
    hold_hours: float
    forced_end: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_trade_costs(
    direction: int,
    entry_price: float,
    exit_price: float,
    *,
    leverage: float = 1.0,
    oi: Optional[float] = None,
    fee_rt_pct: float = 0.001,
    hold_hours: float = 0.0,
    funding_8h_pct: float = 0.0,
    option_spread_pct: Optional[float] = None,
    apply_slippage: bool = True,
    forced_end: bool = False,
) -> CostBreakdown:
    """
    Compute gross/net PnL and a full cost breakdown for a single trade.

    Parameters
    ----------
    direction : +1 for long, -1 for short.
    entry_price, exit_price : clean fill prices (e.g., next-bar open).
    leverage, oi : passed to the tiered slippage model.
    fee_rt_pct : round-trip taker fee (e.g., 0.001 = 0.10%).
    hold_hours : actual elapsed hours between entry and exit.
    funding_8h_pct : signed funding rate per 8h period (e.g., 0.0001 = 1bp/8h).
                     Positive rate → longs pay shorts. Cost is direction-aware.
    option_spread_pct : optional round-trip half-spread cost when option quotes
                        are available. Pass `None` when quotes are missing
                        (yields zero spread cost — no fabrication).
    apply_slippage : when False, slippage_bps and slippage_pct are zero.
    forced_end : marker for trades closed at end-of-data (no future bar).

    Returns
    -------
    CostBreakdown — see field docstrings.
    """
    if direction not in (1, -1):
        raise ValueError(f"direction must be +1 or -1, got {direction}")
    if entry_price <= 0:
        raise ValueError(f"entry_price must be > 0, got {entry_price}")

    bps = float(slippage_bps(leverage, oi)) if apply_slippage else 0.0
    slip_one_side = bps / 10_000.0  # decimal half-spread per side

    # Effective fills: long entry pays higher, long exit receives lower;
    # short entry receives lower, short exit pays higher.
    eff_entry = entry_price * (1.0 + direction * slip_one_side)
    eff_exit  = exit_price  * (1.0 - direction * slip_one_side)

    gross_pnl_pct = direction * (exit_price - entry_price) / entry_price
    slippage_pct  = 2.0 * slip_one_side  # round-trip
    fee_pct       = float(fee_rt_pct)

    # Funding: positive rate drags longs, credits shorts. Funding cost is
    # always proportional to actual hold time.
    funding_pct = direction * float(funding_8h_pct) * (float(hold_hours) / 8.0)

    spread_pct = float(option_spread_pct) if option_spread_pct is not None else 0.0

    total_cost_pct = slippage_pct + fee_pct + funding_pct + spread_pct
    net_pnl_pct    = gross_pnl_pct - total_cost_pct

    return CostBreakdown(
        direction=direction,
        entry_price=float(entry_price),
        exit_price=float(exit_price),
        effective_entry_price=float(eff_entry),
        effective_exit_price=float(eff_exit),
        gross_pnl_pct=float(gross_pnl_pct),
        slippage_bps=float(bps),
        slippage_pct=float(slippage_pct),
        fee_pct=float(fee_pct),
        funding_pct=float(funding_pct),
        option_spread_pct=float(spread_pct),
        total_cost_pct=float(total_cost_pct),
        net_pnl_pct=float(net_pnl_pct),
        hold_hours=float(hold_hours),
        forced_end=bool(forced_end),
    )


def next_bar_open_fill(candles, signal_idx: int) -> Optional[tuple]:
    """
    Return (price, bar_idx) for the fill at the open of the bar after
    `signal_idx`. Returns None when there is no future bar — preventing
    last-bar lookahead entries / forcing the caller to explicitly mark
    end-of-data exits.
    """
    nxt = signal_idx + 1
    if nxt >= len(candles):
        return None
    return (float(candles[nxt].open), nxt)
