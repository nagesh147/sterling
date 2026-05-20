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
from typing import Any, Dict, Optional, List

from app.engines.risk.slippage import slippage_bps, effective_entry


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
    structure_type: str = "futures"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_cost_model(structure_type: str) -> float:
    """
    Return the total round-trip taker fee rate for the given structure type.
    """
    struct_lower = structure_type.lower() if structure_type else "futures"
    if struct_lower in (
        "bull_call_spread",
        "bear_put_spread",
        "bull_put_spread",
        "bear_call_spread",
        "spread",
    ):
        return 0.002  # 2 legs * 0.10% RT = 0.20%
    elif struct_lower in ("naked_call", "naked_put", "futures", "naked"):
        return 0.001  # 1 leg * 0.10% RT = 0.10%
    else:
        return 0.001


def compute_trade_costs(
    direction: int,
    entry_price: float,
    exit_price: float,
    *,
    structure_type: str = "futures",
    leverage: float = 1.0,
    oi: Optional[float] = None,
    fee_rt_pct: Optional[float] = None,
    hold_hours: float = 0.0,
    funding_8h_pct: Optional[float] = None,
    option_spread_pct: Optional[float] = None,
    option_legs: Optional[List[dict]] = None,
    apply_slippage: bool = True,
    forced_end: bool = False,
) -> CostBreakdown:
    """
    Compute gross/net PnL and a full cost breakdown for a single trade.

    Parameters
    ----------
    direction : +1 for long, -1 for short.
    entry_price, exit_price : clean fill prices (e.g., next-bar open).
    structure_type : the instrument structure type (e.g. futures, bull_call_spread, etc.)
    leverage, oi : passed to the tiered slippage model.
    fee_rt_pct : optional round-trip taker fee. If None, resolved via make_cost_model.
    hold_hours : actual elapsed hours between entry and exit.
    funding_8h_pct : optional signed funding rate per 8h period.
                     If None or 0.0, defaults to 0.0001 per 8h for futures (drag).
    option_spread_pct : optional round-trip half-spread cost when option quotes
                        are available.
    option_legs : optional list of legs with bid/ask/mid quotes to compute option half-spread.
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

    # 1. Taker Fee rate resolution via make_cost_model if not explicitly set
    if fee_rt_pct is None:
        resolved_fee_rt = make_cost_model(structure_type)
    else:
        resolved_fee_rt = float(fee_rt_pct)

    # 2. Slippage resolution using effective_entry
    bps = float(slippage_bps(leverage, oi)) if apply_slippage else 0.0
    
    if apply_slippage:
        eff_entry = effective_entry(entry_price, direction, leverage, oi)
        # Exit order direction is opposite of trade direction (-direction)
        eff_exit = effective_entry(exit_price, -direction, leverage, oi)
    else:
        eff_entry = entry_price
        eff_exit = exit_price

    # 3. Gross PnL
    gross_pnl_pct = direction * (exit_price - entry_price) / entry_price
    slippage_pct = 2.0 * (bps / 10_000.0)  # round-trip
    fee_pct = resolved_fee_rt

    # 4. Perpetual Funding Accrual
    if structure_type.lower() == "futures":
        if funding_8h_pct is not None and funding_8h_pct != 0.0:
            funding_pct = direction * float(funding_8h_pct) * (float(hold_hours) / 8.0)
        else:
            funding_pct = 0.0001 * (float(hold_hours) / 8.0)
    else:
        if funding_8h_pct is not None and funding_8h_pct != 0.0:
            funding_pct = direction * float(funding_8h_pct) * (float(hold_hours) / 8.0)
        else:
            funding_pct = 0.0

    # 5. Option Half-spread Cost
    spread_pct = 0.0
    if option_legs:
        # Sum of (ask - bid) / (2 * mid) for each leg
        for leg in option_legs:
            ask = float(leg.get("ask", 0.0))
            bid = float(leg.get("bid", 0.0))
            mid = float(leg.get("mid", leg.get("mid_price", (ask + bid) / 2.0)))
            if mid > 0:
                spread_pct += (ask - bid) / (2.0 * mid)
    elif option_spread_pct is not None:
        spread_pct = float(option_spread_pct)

    total_cost_pct = slippage_pct + fee_pct + funding_pct + spread_pct
    net_pnl_pct = gross_pnl_pct - total_cost_pct

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
        structure_type=structure_type,
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
