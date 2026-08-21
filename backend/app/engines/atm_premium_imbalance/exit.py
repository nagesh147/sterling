"""Exit policies and exit order pricing.

Two things this file refuses to conflate:

* The **target** is computed from the broker's average entry fill. Not the
  requested limit, not the first tick. In the observed trade the requested limit
  was 288.75 and the fill was 133.40; a target built on 288.75 would never fire.
* The **trigger**, the **order price** and the **fill** are three separate
  facts. Observed: trigger 149.10, order 148.70, fill 156.85.
"""
from __future__ import annotations

from typing import Optional

from .config import ATMPremiumImbalanceConfig
from .models import ExitEvent, OptionType, align_to_tick, q2


def target_price(entry_fill: float, cfg: ATMPremiumImbalanceConfig) -> float:
    """``entry_fill + target_points``.

    The one formula the recordings state as a literal: the summary block prints
    ``Target Hit (+15)`` and the trigger fired at 149.10 against a 133.40 fill.
    """
    if entry_fill is None or entry_fill <= 0:
        raise ValueError("target requires a positive entry fill price")
    return q2(entry_fill + cfg.target_points)


def stop_price(entry_fill: float, cfg: ATMPremiumImbalanceConfig) -> Optional[float]:
    """``None`` unless a stop was explicitly enabled.

    No stop was observed in any recording. We provide the plumbing so research
    can test one, and default it off so we never claim the source bot had it.
    """
    if not cfg.stop_enabled or cfg.stop_points <= 0:
        return None
    return q2(max(0.0, entry_fill - cfg.stop_points))


def should_exit(
    *,
    last_price: float,
    entry_fill: float,
    cfg: ATMPremiumImbalanceConfig,
    held_seconds: float = 0.0,
    counter_leg_price: Optional[float] = None,
) -> tuple[bool, str]:
    """Evaluate the configured exit policy against the latest price."""
    tgt = target_price(entry_fill, cfg)

    if cfg.exit_policy == "FIXED_POINT_TARGET":
        if last_price >= tgt:
            return True, "target_hit"
    elif cfg.exit_policy == "PREMIUM_CONVERGENCE":
        # Research-only. The earliest build was named SENSEX_MEETING_POINT_BOT,
        # so convergence is a plausible original identity -- but the latest build
        # is target-based, so this can never be the default.
        if counter_leg_price is not None and last_price >= counter_leg_price:
            return True, "premium_convergence"
        if last_price >= tgt:
            return True, "target_hit"

    stop = stop_price(entry_fill, cfg)
    if stop is not None and last_price <= stop:
        return True, "stop_hit"
    if cfg.max_hold_seconds > 0 and held_seconds >= cfg.max_hold_seconds:
        return True, "time_stop"
    return False, ""


def exit_order_price(
    best_bid: Optional[float],
    cfg: ATMPremiumImbalanceConfig,
    *,
    tick_size: float = 0.05,
    fallback_price: Optional[float] = None,
) -> Optional[float]:
    """``best_bid - exit_buffer_points``, tick-aligned downward.

    OBSERVED in both builds: 149.2 -> 148.7 and 127.1 -> 126.6, i.e. a 0.50
    buffer. Rounding down keeps a sell marketable; rounding up could leave it
    resting above the bid.

    ``None`` when there is no bid and no fallback -- the caller must escalate
    rather than invent a price for a real exit.
    """
    ref = best_bid if best_bid is not None and best_bid > 0 else fallback_price
    if ref is None or ref <= 0:
        return None
    raw = q2(float(ref) - cfg.exit_buffer_points)
    if raw <= 0:
        return None
    return align_to_tick(raw, tick_size, mode="down")


def build_exit_event(
    *,
    trigger_price: float,
    trigger_ts_ms: int,
    entry_fill: float,
    cfg: ATMPremiumImbalanceConfig,
    best_bid: Optional[float],
    tick_size: float = 0.05,
    reason: str = "target_hit",
) -> ExitEvent:
    """Freeze the trigger, then price the order. Fill is attached later."""
    return ExitEvent(
        trigger_price=q2(trigger_price),
        trigger_ts_ms=int(trigger_ts_ms),
        target_price=target_price(entry_fill, cfg),
        reference_bid=None if best_bid is None else q2(best_bid),
        exit_order_price=exit_order_price(best_bid, cfg, tick_size=tick_size, fallback_price=trigger_price),
        reason=reason,
    )


def format_exit_block(event: ExitEvent, instrument_id: str) -> str:
    """Reproduce the observed exit block for conformance diffing."""
    bid = "-" if event.reference_bid is None else f"{event.reference_bid}"
    price = "-" if event.exit_order_price is None else f"{event.exit_order_price}"
    return (
        "EXIT - LIMIT SELL AT BEST BID - BUFFER\n"
        f"Instrument   : {instrument_id}\n"
        f"Best Bid     : {bid}\n"
        f"Order Price  : {price}"
    )
