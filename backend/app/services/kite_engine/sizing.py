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
    #: True when the smallest tradable size would break the risk budget and the
    #: override is off — i.e. there is no size that honours the cap, so the trade must
    #: not be placed at all. Distinct from ``qty == 0`` for a missing lot size, which
    #: is a data problem rather than a risk decision. Callers MUST check this: they
    #: fall back to a default order size when ``qty`` is 0, so a blocked result that
    #: only zeroed the quantity would place the *unsized* order instead of none.
    blocked: bool = False


def size_position(
    *,
    entry_premium: float,
    stop_premium: float,
    lot_size: int,
    available_capital: float,
    risk_pct: float,
    max_lots: int,
    allow_min_lot_over_risk: bool = False,
) -> SizingResult:
    """Decide lots for one option BUY.

    Target: ``risk_per_lot × lots ≤ risk_pct% × available_capital``, capped by both
    ``max_lots`` and what the margin can afford.

    When even ONE lot breaks that budget there is no size that honours the cap, so the
    result is ``blocked`` and the caller must not trade. It used to floor to a single
    lot and place the order anyway, which quietly turned ``risk_pct`` into a
    suggestion — on a lot-size-50 index option a 1% setting could commit well over ten
    times that. ``allow_min_lot_over_risk`` restores the old behaviour for anyone who
    would rather take the minimum size than miss the signal; it is a deliberate choice
    rather than the default.

    Degenerate inputs (non-positive lot size, or stop ≥ entry so risk is undefined)
    still fall back to a single lot. That is not the same case: there is no budget to
    compare against, so there is nothing to honour. It is reached only when the caller
    has already resolved a positive entry and stop, which makes it rare.
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

    # Only a KNOWN budget can be exceeded. ``available_fo_capital`` returns 0.0 when
    # the margins call fails, and treating that as "over budget" would turn a
    # transient broker API outage into a silent halt of every automatic entry — a far
    # bigger behaviour change than the one being fixed here, and one that looks
    # exactly like the engine being broken. Unknown capital keeps the old 1-lot floor.
    if by_risk < 1 and not allow_min_lot_over_risk and float(available_capital or 0.0) > 0:
        return SizingResult(
            0, 0, risk_per_lot, 0.0, 0.0,
            f"risk/lot ₹{risk_per_lot:.0f} > budget ₹{budget:.0f} "
            f"({risk_pct:.1f}% of ₹{available_capital:.0f}) — no size honours the cap",
            blocked=True)

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


def size_future_position(
    *,
    entry_price: float,
    stop_price: float,
    lot_size: int,
    available_capital: float,
    risk_pct: float,
    max_lots: int,
    allow_min_lot_over_risk: bool = False,
) -> SizingResult:
    """Decide lots for one futures position (directional mode).

    Risk basis is ``(entry − stop) × lot_size`` (notional loss at stop). Same rules as
    the options sizer, including blocking when one lot already breaks the budget —
    which bites harder here, since a single index-futures lot carries the full
    notional and its stop distance is measured in index points.
    """
    lot_size = int(lot_size or 0)
    if lot_size <= 0:
        return SizingResult(0, 0, 0.0, 0.0, 0.0, "no lot size — cannot size")

    entry = float(entry_price or 0.0)
    stop = float(stop_price or 0.0)
    risk_per_unit = abs(entry - stop)
    risk_per_lot = risk_per_unit * lot_size

    if risk_per_unit <= 0 or entry <= 0:
        qty = lot_size
        return SizingResult(1, qty, max(0.0, risk_per_lot), max(0.0, risk_per_lot),
                            entry * qty * 0.15,
                            "stop = entry — risk undefined, defaulting to 1 lot")

    budget = max(0.0, float(available_capital or 0.0)) * (float(risk_pct) / 100.0)
    by_risk = int(budget // risk_per_lot) if risk_per_lot > 0 else 0

    # Margin affordability: SPAN margin ≈ 15% of contract value.
    margin_per_lot = entry * lot_size * 0.15
    by_margin = int(float(available_capital or 0.0) // margin_per_lot) if margin_per_lot > 0 else 0

    # Only a KNOWN budget can be exceeded. ``available_fo_capital`` returns 0.0 when
    # the margins call fails, and treating that as "over budget" would turn a
    # transient broker API outage into a silent halt of every automatic entry — a far
    # bigger behaviour change than the one being fixed here, and one that looks
    # exactly like the engine being broken. Unknown capital keeps the old 1-lot floor.
    if by_risk < 1 and not allow_min_lot_over_risk and float(available_capital or 0.0) > 0:
        return SizingResult(
            0, 0, risk_per_lot, 0.0, 0.0,
            f"risk/lot ₹{risk_per_lot:.0f} > budget ₹{budget:.0f} "
            f"({risk_pct:.1f}% of ₹{available_capital:.0f}) — no size honours the cap",
            blocked=True)

    lots = max(1, by_risk)
    lots = min(lots, int(max_lots))
    if by_margin >= 1:
        lots = min(lots, by_margin)

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

    return SizingResult(lots, qty, risk_per_lot, est_risk, margin_per_lot * lots, reason)

