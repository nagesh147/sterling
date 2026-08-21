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


def optional_target_price(entry_fill: float,
                          cfg: ATMPremiumImbalanceConfig) -> Optional[float]:
    """The target, or ``None`` when the policy has no ceiling.

    Under TRAILING_STOP with zero target points, ``entry + 0`` is the entry, and
    reporting the entry price as a target reads as a target of zero profit. There
    is no target; saying so is the honest answer.
    """
    if cfg.target_points <= 0:
        return None
    return target_price(entry_fill, cfg)


def target_price(entry_fill: float, cfg: ATMPremiumImbalanceConfig) -> float:
    """``entry_fill + target_points``.

    The one formula the recordings state as a literal: the summary block prints
    ``Target Hit (+15)`` and the trigger fired at 149.10 against a 133.40 fill.
    """
    if entry_fill is None or entry_fill <= 0:
        raise ValueError("target requires a positive entry fill price")
    return q2(entry_fill + cfg.target_points)


def stop_price(entry_fill: float, cfg: ATMPremiumImbalanceConfig) -> Optional[float]:
    """The initial stop, before any trailing. ``None`` unless one is enabled.

    No stop was observed in any recording. The plumbing exists so a stop can be
    configured and researched, and it defaults off so we never claim the source
    bot had one.
    """
    if not cfg.stop_enabled or cfg.stop_distance <= 0:
        return None
    return q2(max(0.0, entry_fill - cfg.stop_distance_inr(entry_fill)))


def trailing_stop_price(
    entry_fill: float,
    high_water: float,
    cfg: ATMPremiumImbalanceConfig,
) -> Optional[float]:
    """Where the stop sits now, given the best price seen since entry.

    Three rungs, applied in order, and the result only ever moves **up**:

    1. the initial stop, ``entry - stop_distance`` -- the most this trade may lose
    2. break-even: once the price has been ``breakeven`` in front, the stop moves
       to the entry fill, so the trade can no longer lose
    3. the trail: once the price has been ``trail_start`` in front, the stop
       follows the high-water mark at ``trail_distance`` behind it

    The ratchet is the whole point. A stop that can move down is not protection,
    it is a way to lose more than you agreed to -- so each rung takes ``max``
    against the rung below, and the caller's job is only to feed a high-water
    mark that never decreases.

    Percentages are measured against the **entry fill**, not the current price:
    the risk the operator agreed to is fixed at entry and must not drift with the
    market. The trail distance is the exception -- it is measured against the
    high-water mark, because that is what it follows.
    """
    base = stop_price(entry_fill, cfg)
    if base is None:
        return None
    stop = base
    gain = float(high_water) - float(entry_fill)

    if cfg.breakeven_enabled and gain >= cfg.breakeven_inr(entry_fill):
        stop = max(stop, q2(entry_fill))

    if cfg.trails and gain >= cfg.trail_start_inr(entry_fill):
        trailed = q2(float(high_water) - cfg.trail_distance_inr(high_water))
        stop = max(stop, trailed)

    return q2(max(0.0, stop))


def should_exit(
    *,
    last_price: float,
    entry_fill: float,
    cfg: ATMPremiumImbalanceConfig,
    held_seconds: float = 0.0,
    counter_leg_price: Optional[float] = None,
    high_water: Optional[float] = None,
) -> tuple[bool, str]:
    """Evaluate the configured exit policy against the latest price.

    ``high_water`` is the best price seen since entry. It is a parameter rather
    than something derived here because the caller owns the position's history;
    passing the last price instead would silently disable trailing, so it
    defaults to the entry fill (no gain yet) rather than to ``last_price``.
    """
    peak = float(entry_fill if high_water is None else high_water)

    if cfg.exit_policy == "FIXED_POINT_TARGET":
        if last_price >= target_price(entry_fill, cfg):
            return True, "target_hit"
    elif cfg.exit_policy == "PREMIUM_CONVERGENCE":
        # Research-only. The earliest build was named SENSEX_MEETING_POINT_BOT,
        # so convergence is a plausible original identity -- but the latest build
        # is target-based, so this can never be the default.
        if counter_leg_price is not None and last_price >= counter_leg_price:
            return True, "premium_convergence"
        if last_price >= target_price(entry_fill, cfg):
            return True, "target_hit"
    elif cfg.exit_policy == "TRAILING_STOP":
        # No fixed target: the position is closed by the stop coming up to meet
        # it. A target here would cap exactly the runs the trail exists to keep,
        # unless the operator asks for one explicitly.
        if cfg.target_points > 0 and last_price >= target_price(entry_fill, cfg):
            return True, "target_hit"
        stop = trailing_stop_price(entry_fill, peak, cfg)
        if stop is not None and last_price <= stop:
            # Name which rung caught it: "stopped out" and "gave back some of a
            # win" are different outcomes and the log should not blur them.
            if stop > entry_fill:
                return True, "trailing_stop_hit"
            if stop == q2(entry_fill):
                return True, "breakeven_stop_hit"
            return True, "stop_hit"
        if cfg.max_hold_seconds > 0 and held_seconds >= cfg.max_hold_seconds:
            return True, "time_stop"
        return False, ""

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
