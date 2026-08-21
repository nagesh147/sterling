"""The signal. One implementation, shared by live and replay.

There is deliberately no indicator here. The observed bot decided in under a
millisecond from a single tick pair, and adding a filter would make the thing we
validate a different strategy from the thing we reconstructed.

Gates are liveness only. They can reject a signal; they can never invert one.
"""
from __future__ import annotations

from typing import Optional

from .config import ATMPremiumImbalanceConfig
from .models import PremiumPairView, PremiumSignal, q2


def _no(view: PremiumPairView, reason: str) -> PremiumSignal:
    return PremiumSignal(action="NO_TRADE", view=view, difference=view.difference, reason=reason)


def evaluate(
    view: Optional[PremiumPairView],
    cfg: ATMPremiumImbalanceConfig,
    *,
    session_open: bool = True,
    flat: bool = True,
    risk_authorized: bool = True,
    trades_taken: int = 0,
) -> PremiumSignal:
    """Decide from one CE/PE view.

    ``BUY`` the cheaper leg; equal premiums are explicitly no trade rather than
    an arbitrary tie-break, because a coin-flip at the open is not a strategy.
    """
    if view is None:
        # No view could be built at all -- e.g. EXECUTABLE mode with a missing
        # ask. There is no fallback: substituting another mode here would make
        # the configured mode a lie.
        empty = PremiumPairView(mode=cfg.quote_mode, ce_price=0.0, pe_price=0.0)  # type: ignore[arg-type]
        return _no(empty, "no_quote_pair")

    if not session_open:
        return _no(view, "session_closed")
    if not risk_authorized:
        return _no(view, "risk_not_authorized")
    if not flat:
        return _no(view, "position_open")
    if trades_taken >= cfg.max_trades_per_session:
        return _no(view, "session_trade_limit_reached")

    if view.ce_price <= 0 or view.pe_price <= 0:
        return _no(view, "invalid_quote")
    if view.ce_age_ms > cfg.max_quote_age_ms or view.pe_age_ms > cfg.max_quote_age_ms:
        return _no(view, "stale_quote")
    if view.mode == "SYNCHRONIZED" and view.skew_ms > cfg.max_ce_pe_skew_ms:
        return _no(view, "ce_pe_skew_exceeded")

    leg = view.cheaper_leg
    if leg is None:
        return _no(view, "equal_premiums")

    gap = abs(view.difference)
    if cfg.minimum_difference > 0 and gap < cfg.minimum_difference:
        return _no(view, "below_minimum_difference")
    if cfg.minimum_difference_percent > 0:
        cheaper = min(view.ce_price, view.pe_price)
        if cheaper <= 0 or (gap / cheaper) * 100.0 < cfg.minimum_difference_percent:
            return _no(view, "below_minimum_difference_percent")

    return PremiumSignal(
        action="BUY_CE" if leg == "CE" else "BUY_PE",
        view=view,
        option_type=leg,
        difference=view.difference,
        reason=f"cheaper_leg={leg}",
    )


def format_difference_line(view: PremiumPairView) -> str:
    """Reproduce the source bot's line, byte for byte.

    Used by the replay conformance report to diff our output against the
    recordings: ``CE : 141.00 | PE : 196.95 | Difference : 55.95``.
    """
    return (
        f"CE : {view.ce_price:.2f} | PE : {view.pe_price:.2f} "
        f"| Difference : {q2(view.pe_price - view.ce_price):.2f}"
    )
