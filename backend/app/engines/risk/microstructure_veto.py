"""
Sterling v4 — Microstructure Veto

Last-stage gate executed at the moment of order submission. Inspects the
top-of-book imbalance, last-trades direction, and spread regime to veto
trades entering into a hostile print.

Cheap: relies on data the adapter has already fetched. No extra REST calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class MicroSnapshot:
    """Snapshot of book + recent trades for one instrument."""
    bid_qty: float
    ask_qty: float
    mid_spread: float
    ref_spread_1h: float                    # rolling 1h average mid-spread
    last_trades: List[Tuple[float, str]]    # [(size, side), ...] — newest last; side = "buy"|"sell"


@dataclass(frozen=True)
class MicroVetoConfig:
    book_imbalance_max:   float = 0.7    # |Δ| / total > this against trade direction → veto
    trade_pressure_max:   float = 0.8    # last-trades fraction in opposing direction → veto
    spread_blow_out_x:    float = 1.5    # mid_spread > 1.5× rolling 1h mean → veto
    last_trades_window:   int   = 50     # tail size to evaluate trade pressure


@dataclass(frozen=True)
class MicroDecision:
    veto: bool
    code: str = ""
    reason: str = ""


def evaluate(
    direction: str,                             # "long" | "short"
    snapshot: MicroSnapshot,
    config: Optional[MicroVetoConfig] = None,
) -> MicroDecision:
    """
    Returns MicroDecision(veto=True, code, reason) when any of the three
    micro-conditions fires; otherwise MicroDecision(veto=False).

    The trade direction maps to the order side:
      long  → buying  → unfriendly book has heavy ask side (sellers on offer)
      short → selling → unfriendly book has heavy bid side (buyers absorbing)
    """
    cfg = config or MicroVetoConfig()

    # ── 1. book imbalance ──────────────────────────────────────────────
    total = snapshot.bid_qty + snapshot.ask_qty
    if total > 0:
        # Positive imbalance favors buyers. Long wants positive imbalance;
        # short wants negative. We veto when the imbalance is heavily
        # AGAINST the trade direction.
        imbalance = (snapshot.bid_qty - snapshot.ask_qty) / total
        hostile = -imbalance if direction == "long" else imbalance
        if hostile > cfg.book_imbalance_max:
            return MicroDecision(
                True, "micro_book_imbalance",
                f"book imbalance {hostile:+.2f} hostile to {direction} > {cfg.book_imbalance_max:.2f}",
            )

    # ── 2. trade pressure ──────────────────────────────────────────────
    tail = snapshot.last_trades[-cfg.last_trades_window:] if snapshot.last_trades else []
    if tail:
        opposing = "sell" if direction == "long" else "buy"
        opposing_size = sum(s for s, side in tail if side == opposing)
        total_size = sum(s for s, _ in tail)
        if total_size > 0:
            opposing_frac = opposing_size / total_size
            if opposing_frac > cfg.trade_pressure_max:
                return MicroDecision(
                    True, "micro_trade_pressure",
                    f"last {len(tail)} prints {opposing_frac:.0%} {opposing} > {cfg.trade_pressure_max:.0%}",
                )

    # ── 3. spread blow-out ─────────────────────────────────────────────
    if snapshot.ref_spread_1h > 0 and snapshot.mid_spread > 0:
        ratio = snapshot.mid_spread / snapshot.ref_spread_1h
        if ratio > cfg.spread_blow_out_x:
            return MicroDecision(
                True, "micro_spread_blow_out",
                f"spread {snapshot.mid_spread:.4f} is {ratio:.1f}× the 1h mean {snapshot.ref_spread_1h:.4f}",
            )

    return MicroDecision(False)
