"""Refresh-aware Greeks aggregation for the OrderRouter Greeks budget gate.

Position Greeks drift with the market — spot moves, IV changes, T decays.
Reading `getattr(pos, 'greeks', None)` from a stored snapshot at order-
submit time silently lets risk creep past caps, because the snapshot is
the value at the time of entry, not now.

This module re-prices each open option position at current market and
computes the would-be Greeks of the new order, so `GreeksBudgetChecker`
can hard-gate against the live portfolio state. The OrderRouter calls
this via a `greeks_budget_gate` dep so the gate is unit-testable and
swappable per dispatch path (paper/shadow/live).

Phase-0 cut: refreshes existing positions using stored `entry_iv` as the
IV fallback (no live chain re-fetch per position — that arrives in
Phase 1 alongside `option_pricing.enrich_with_greeks`). New options
orders DO fetch the live chain to get the strike's current mark_iv,
since the order is about to execute and the marginal accuracy matters.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Optional

from app.engines.risk.greeks_budget import (
    GreeksBudgetChecker, PositionGreeks, bsm_greeks_full,
)

log = logging.getLogger(__name__)


# ── per-position refresh ────────────────────────────────────────────────────


def refresh_position_greeks(
    pos: Any, current_spot: float, iv_override: Optional[float] = None
) -> PositionGreeks:
    """Re-price one open position's Greeks at current spot.

    • Futures contribute pure spot delta — +1 per contract long, −1 short,
      no gamma/vega/theta/rho. The notional captures size.
    • Options: BSM at (current_spot, strike, dte_remaining, iv_override or
      entry_iv). When IV is unavailable AND no entry snapshot exists, we
      log and return zeros — better to under-state risk in the gate than
      to fail closed on every order because a single legacy position has
      no IV. Phase 1 chain refresh closes this gap.

    Multi-leg structures are aggregated by summing leg-wise Greeks; today
    `place_order_option(side="buy")` is the only path, so all legs are
    long. When short-options ships, the per-leg direction sign comes in
    here.
    """
    s = pos.sized_trade.structure
    if s.structure_type == "futures":
        sign = 1.0 if s.direction.value == "long" else -1.0
        return PositionGreeks(delta=sign, vega=0.0, theta=0.0, gamma=0.0, rho=0.0)

    if not s.legs:
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0)

    # Greeks accumulate across legs of a spread.
    accum = PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0)
    for leg in s.legs:
        iv = iv_override if iv_override is not None else (getattr(pos, 'entry_iv', None) or 0.0)
        if iv <= 0:
            # No IV → fall back to the stored entry snapshot if present.
            snap = getattr(pos, 'entry_greeks_snapshot', None)
            if snap is not None:
                accum.delta += snap.delta
                accum.gamma += snap.gamma
                accum.vega  += snap.vega
                accum.theta += snap.theta
                accum.rho   += snap.rho
                continue
            log.debug(
                "refresh_position_greeks[%s]: no IV and no entry snapshot; "
                "leg contributes zero Greeks.", getattr(pos, 'id', '?'),
            )
            continue

        # Remaining DTE: entry_dte minus elapsed days (floors at 0).
        entry_ts = getattr(pos, 'entry_timestamp_ms', 0) or 0
        elapsed_days = (int(time.time() * 1000) - entry_ts) / 86_400_000.0
        dte_at_entry = getattr(pos, 'entry_dte', None) or leg.dte
        dte_now = max(0.0, dte_at_entry - elapsed_days)

        if dte_now <= 0:
            # Expired position — contributes only intrinsic delta. Treated as
            # near-zero exposure; the position should already be closed by
            # the DTE force-close handler (Phase 1).
            continue

        is_call = leg.option_type == "call"
        leg_g = bsm_greeks_full(
            S=current_spot, K=float(leg.strike), T=dte_now / 365.0,
            r=0.0, sigma=float(iv), is_call=is_call,
        )
        accum.delta += leg_g.delta
        accum.gamma += leg_g.gamma
        accum.vega  += leg_g.vega
        accum.theta += leg_g.theta
        accum.rho   += leg_g.rho

    return accum


# ── new-order Greeks computation ────────────────────────────────────────────


def _parse_option_symbol(symbol: str) -> Optional[dict]:
    """Parse a Delta India option symbol like 'C-BTC-50000-310525' into
    {type, underlying, strike, expiry}. Returns None on bad input."""
    parts = (symbol or "").split("-")
    if len(parts) != 4:
        return None
    type_code, underlying, strike_s, expiry = parts
    if type_code not in ("C", "P"):
        return None
    try:
        return {
            "option_type": "call" if type_code == "C" else "put",
            "underlying": underlying,
            "strike": float(strike_s),
            "expiry": expiry,           # DDMMYY
            "is_call": type_code == "C",
        }
    except ValueError:
        return None


async def compute_new_order_greeks(
    req: Any, adapter: Any, current_spot: float,
) -> tuple[PositionGreeks, float]:
    """Compute (Greeks, notional_usd) for a NEW order about to be placed.

    Futures: trivial — delta=±1, others=0, notional=spot×size.
    Options: parses option_symbol, fetches the live option chain to read
    the strike's current mark_iv, BSM-prices, returns scaled per-contract
    Greeks. notional=spot×size (so the budget gate denominates in spot
    exposure, matching how futures contribute).

    On any failure (bad symbol, chain fetch error, missing IV) returns
    zero Greeks + zero notional with a log line; the gate treats this as
    "cannot evaluate", which means the order proceeds (fail-open at the
    gate; the order's eventual settlement still hits other safety rails).
    Erring fail-open is the right call here — false-positive rejects on
    every options order due to a transient chain hiccup is worse than a
    rare miss.
    """
    size = float(req.size or 0)
    if size <= 0 or current_spot <= 0:
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0), 0.0

    notional = current_spot * size

    if req.instrument_type == "futures":
        sign = 1.0 if req.direction == "long" else -1.0
        # Per-contract delta = ±1; we scale by size into the notional.
        per_contract = PositionGreeks(delta=sign, vega=0.0, theta=0.0, gamma=0.0, rho=0.0)
        return per_contract, notional

    # Options path
    parsed = _parse_option_symbol(req.option_symbol or "")
    if parsed is None:
        log.warning(
            "compute_new_order_greeks: cannot parse option_symbol %r; "
            "gate sees zero Greeks for this order (fail-open).",
            req.option_symbol,
        )
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0), 0.0

    # Live IV from the option chain
    try:
        from app.services.exchanges import instrument_registry as _reg
        inst = _reg.get_instrument(parsed["underlying"])
        if inst is None:
            raise RuntimeError(f"no instrument for {parsed['underlying']}")
        chain = await adapter.get_option_chain(inst)
    except Exception as exc:
        log.warning(
            "compute_new_order_greeks: option chain fetch failed for %s: %s; "
            "gate sees zero Greeks for this order (fail-open).",
            parsed["underlying"], exc,
        )
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0), 0.0

    target = None
    for opt in chain:
        if (opt.strike == parsed["strike"]
                and opt.expiry_date.replace("-", "") == parsed["expiry"]
                and opt.option_type == parsed["option_type"]):
            target = opt
            break
    if target is None or not target.mark_iv:
        log.warning(
            "compute_new_order_greeks: strike %s %s expiry %s not in chain "
            "or no IV; gate sees zero Greeks (fail-open).",
            parsed["strike"], parsed["option_type"], parsed["expiry"],
        )
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0), 0.0

    iv = float(target.mark_iv)
    if iv > 5.0:        # adapter sometimes returns IV as a percent
        iv /= 100.0

    g = bsm_greeks_full(
        S=current_spot, K=parsed["strike"], T=max(0.0, target.dte) / 365.0,
        r=0.0, sigma=iv, is_call=parsed["is_call"],
    )
    return g, notional


# ── the gate ────────────────────────────────────────────────────────────────


async def check_against_budget(
    req: Any,
    open_positions: list,
    adapter: Any,
    checker: GreeksBudgetChecker,
    get_spot: Callable[[str], Awaitable[float]] | Callable[[str], float],
) -> Optional[str]:
    """Run a full refresh + budget check for `req`.

    Returns:
        None when the order fits inside the portfolio Greek budget,
        else a machine-readable breach string like "delta_breach:35%>30%"
        which the OrderRouter echoes back as `code=greeks_budget_breach`.

    Fail-open on infrastructure errors (adapter down, no checker bound):
    we'd rather miss a breach than reject every order. The hard rails
    (kill switch, daily loss, idempotency, cooldown) still gate the order
    even when this passes.
    """
    if checker is None or checker.pv <= 0:
        return None

    # 1. Current spot for the new order's underlying. We also need spots for
    #    every underlying that has an open position. Caller supplies an awaitable
    #    `get_spot(sym)` so we can batch / cache however we like.
    try:
        new_spot_val = get_spot(req.underlying.upper())
        if hasattr(new_spot_val, "__await__"):
            new_spot = float(await new_spot_val)
        else:
            new_spot = float(new_spot_val)
    except Exception as exc:
        log.warning("check_against_budget: get_spot failed for %s: %s; gate skipped (fail-open).", req.underlying, exc)
        return None

    if new_spot <= 0:
        return None

    # 2. Refresh existing positions' Greeks at their current spot.
    refreshed: list = []
    seen_spots: dict[str, float] = {req.underlying.upper(): new_spot}
    for pos in open_positions:
        sym = (pos.underlying or "").upper()
        if not sym:
            continue
        # Memoise spot per-underlying for the duration of this check.
        if sym not in seen_spots:
            try:
                sp = get_spot(sym)
                if hasattr(sp, "__await__"):
                    sp = float(await sp)
                else:
                    sp = float(sp)
                seen_spots[sym] = sp
            except Exception:
                seen_spots[sym] = float(pos.entry_spot_price or 0.0)
        spot_for_pos = seen_spots[sym]
        if spot_for_pos <= 0:
            continue
        g = refresh_position_greeks(pos, current_spot=spot_for_pos)
        notional = spot_for_pos * float(pos.sized_trade.contracts or 0)
        # Wrap into the duck-typed shape GreeksBudgetChecker.check reads.
        refreshed.append(_GreeksAndNotional(greeks=g, notional=notional))

    # 3. Compute the new order's Greeks contribution.
    try:
        new_g, new_notional = await compute_new_order_greeks(req, adapter, new_spot)
    except Exception as exc:
        log.warning("check_against_budget: compute_new_order_greeks failed: %s; gate skipped (fail-open).", exc)
        return None

    # 4. Run the checker.
    ok, reason = checker.check(refreshed, new_g, new_notional)
    return None if ok else reason


class _GreeksAndNotional:
    """Duck-typed minimal shape GreeksBudgetChecker.check reads from each
    open position (`.greeks` and `.notional`). Avoids constructing full
    PaperPosition objects just for the budget aggregation."""
    __slots__ = ("greeks", "notional")

    def __init__(self, greeks: PositionGreeks, notional: float):
        self.greeks = greeks
        self.notional = notional
