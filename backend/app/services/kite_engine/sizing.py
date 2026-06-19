"""Per-trade risk sizing for Kite option auto-exec (workstream F).

Pure functions — no I/O. The caller supplies the live inputs (entry premium,
stop premium, available FO capital, lot size); this module decides how many lots
to buy so the premium-at-risk stays within a percentage of capital, then floors
and caps the result. Isolating the arithmetic here keeps it trivially testable
and free of broker/network concerns.

Premium-at-risk (NOT notional) is the right risk basis for long options: the most
you lose if the stop is hit is ``(entry_premium − stop_premium) × qty``. We size
lots against that, never against the full premium outlay.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizingResult:
    lots: int
    qty: int                 # lots × lot_size (what actually gets ordered)
    risk_per_lot: float      # (entry − stop) × lot_size, in INR
    est_risk: float          # risk_per_lot × lots
    est_cost: float          # entry × qty (margin/outlay needed)
    reason: str              # human-readable explanation of the sizing decision


def size_position(
    *,
    entry_premium: float,
    stop_premium: float,
    lot_size: int,
    available_capital: float,
    risk_pct: float,
    max_lots: int,
) -> SizingResult:
    """Decide lots for one option BUY.

    Target: ``risk_per_lot × lots ≤ risk_pct% × available_capital``.
    Then floor at 1 lot (we always take at least the minimum tradable size when a
    signal fires) and cap by both ``max_lots`` and what the margin can afford.

    Degenerate inputs (non-positive lot size, or stop ≥ entry so risk is undefined)
    fall back to a single lot — the signal is real, we just can't risk-size it, so
    we take the smallest position rather than skip or over-buy.
    """
    lot_size = int(lot_size or 0)
    if lot_size <= 0:
        return SizingResult(0, 0, 0.0, 0.0, 0.0, "no lot size — cannot size")

    entry = float(entry_premium or 0.0)
    stop = float(stop_premium or 0.0)
    risk_per_unit = entry - stop  # per-share premium at risk
    risk_per_lot = risk_per_unit * lot_size

    if risk_per_unit <= 0 or entry <= 0:
        # Stop above/at entry (or no premium) — risk undefined. Take 1 lot.
        qty = lot_size
        return SizingResult(1, qty, max(0.0, risk_per_lot), max(0.0, risk_per_lot),
                            entry * qty, "stop ≥ entry — risk undefined, defaulting to 1 lot")

    budget = max(0.0, float(available_capital or 0.0)) * (float(risk_pct) / 100.0)
    by_risk = int(budget // risk_per_lot) if risk_per_lot > 0 else 0

    # Margin affordability: never order more than the outlay we can pay for.
    cost_per_lot = entry * lot_size
    by_margin = int(float(available_capital or 0.0) // cost_per_lot) if cost_per_lot > 0 else 0

    lots = max(1, by_risk)                 # floor at 1 lot
    lots = min(lots, int(max_lots))        # ceiling
    if by_margin >= 1:
        lots = min(lots, by_margin)        # affordability (only if we can afford ≥1)

    qty = lots * lot_size
    est_risk = risk_per_lot * lots

    if by_risk < 1:
        reason = (f"risk/lot ₹{risk_per_lot:.0f} > budget ₹{budget:.0f} "
                  f"({risk_pct:.1f}% of ₹{available_capital:.0f}) — floored to 1 lot")
    elif lots == int(max_lots) and by_risk > int(max_lots):
        reason = f"risk allows {by_risk} lots, capped at max_lots={max_lots}"
    elif by_margin >= 1 and lots == by_margin and by_margin < max(1, by_risk):
        reason = f"margin affords {by_margin} lots (risk allowed {by_risk})"
    else:
        reason = (f"{lots} lot(s): risk ₹{est_risk:.0f} ≤ budget ₹{budget:.0f} "
                  f"({risk_pct:.1f}% of ₹{available_capital:.0f})")

    return SizingResult(lots, qty, risk_per_lot, est_risk, entry * qty, reason)
