"""Options-aware monitoring helpers — what _background_position_monitor
needs to call when it processes an options position rather than futures.

Phase 1 of the derivatives build. Five concerns, one module:

  • per-underlying option-chain caching — one fetch per underlying per
    poll, shared across every open position on that underlying. The
    existing Semaphore(3) per-position fetch suffocates on 10+ open
    options at the 5s scalping cadence.
  • chain staleness gate — if the cached chain (or its last_updated_ms)
    is more than 30s old, skip Greek-dependent updates for this poll
    and log. Prevents acting on a stale snapshot during exchange
    flakiness.
  • DTE force-close — at `expiry − force_close_minutes_before_expiry`,
    fire a market-reduce close. Tier the window by notional: positions
    > $1k use the full 120 min, smaller use 30 min (settlement spreads
    matter less when the size is tiny).
  • premium-aware exit PnL — when closing on a trail or signal, pass
    the current option mark_price as `exit_premium` so paper_store's
    fixed PnL formula returns the right number instead of falling
    back to the delta-linear estimate.
  • microstructure veto on amend — before cancel_replace_stop on a live
    option stop, check the option's spread_pct. If > 8%, defer the
    amend by one poll; pushing a carrier order through a 20% spread
    creates fills at terrible prices.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from app.schemas.market import OptionSummary

log = logging.getLogger(__name__)


# ── per-poll chain cache ──────────────────────────────────────────────


class OptionChainCache:
    """Per-poll cache: fetches each underlying's option chain at most once
    per polling cycle, regardless of how many open positions reference it.

    Instantiated fresh at the top of each polling cycle and discarded at
    the end — no inter-poll persistence. Each entry stores `(chain,
    fetch_ts_ms)`; downstream callers use `fetch_ts_ms` for the
    staleness gate.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[list[OptionSummary], int]] = {}
        self._failed: set[str] = set()

    async def get_or_fetch(
        self, underlying: str, adapter: Any, registry,
    ) -> tuple[list[OptionSummary], int] | None:
        """Returns `(chain, fetch_ts_ms)` for this underlying, hitting the
        adapter exactly once per polling cycle. Returns None on
        unrecoverable fetch error or when the underlying has no
        instrument registered."""
        ul = (underlying or "").upper()
        if not ul or ul in self._failed:
            return None
        cached = self._cache.get(ul)
        if cached is not None:
            return cached
        inst = registry.get_instrument(ul)
        if inst is None or not getattr(inst, "has_options", False):
            self._failed.add(ul)
            return None
        try:
            chain = await adapter.get_option_chain(inst)
        except Exception as exc:
            log.warning("OptionChainCache: fetch failed for %s: %s", ul, exc)
            self._failed.add(ul)
            return None
        ts_ms = int(time.time() * 1000)
        self._cache[ul] = (chain, ts_ms)
        return chain, ts_ms


def find_option(chain: list[OptionSummary], instrument_name: str) -> Optional[OptionSummary]:
    """Return the first OptionSummary in `chain` whose instrument_name
    matches. Used to read current premium/IV/Greeks for an open option
    position from the freshly-fetched chain."""
    target = (instrument_name or "").strip()
    if not target:
        return None
    for o in chain:
        if o.instrument_name == target:
            return o
    return None


# ── staleness gate ────────────────────────────────────────────────────


CHAIN_STALENESS_MAX_AGE_MS = 30_000


def is_chain_stale(chain_fetch_ts_ms: int, now_ms: Optional[int] = None) -> bool:
    """True when the chain is older than 30s. Greek-dependent monitor
    updates (premium-aware trail, microstructure veto, DTE force-close)
    skip stale chains and log so we don't act on a snapshot that lags
    the real market by half a minute or more.
    """
    if chain_fetch_ts_ms <= 0:
        return True
    cur = now_ms if now_ms is not None else int(time.time() * 1000)
    return (cur - chain_fetch_ts_ms) > CHAIN_STALENESS_MAX_AGE_MS


# ── DTE force-close ───────────────────────────────────────────────────


SMALL_NOTIONAL_FORCE_CLOSE_MIN = 30
SMALL_NOTIONAL_USD_THRESHOLD = 1_000.0


def remaining_minutes_to_expiry(pos: Any, now_ms: Optional[int] = None) -> Optional[float]:
    """Minutes between now and the position's option expiry. Uses
    `entry_dte` + `entry_timestamp_ms` to compute elapsed days so the
    same elapsed-time math the trailing engine uses also gates expiry.
    Returns None when the position has no DTE data (futures or legacy
    pre-Phase-0 records)."""
    if getattr(pos, "entry_dte", None) is None or pos.entry_dte <= 0:
        return None
    entry_ts = getattr(pos, "entry_timestamp_ms", 0) or 0
    if entry_ts <= 0:
        return None
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    elapsed_minutes = (now_ms - entry_ts) / 60_000.0
    total_minutes = pos.entry_dte * 24 * 60
    return max(0.0, total_minutes - elapsed_minutes)


def should_force_close(
    pos: Any, mode_force_close_min: int, now_ms: Optional[int] = None,
    *, notional_usd: Optional[float] = None,
) -> tuple[bool, str]:
    """Should this options position be force-closed pre-expiry?

    Returns `(should, reason)`. Reason is "" on pass, otherwise a
    machine-readable tag like "force_close_dte:42min<120min".

    Tiering: positions with notional > `SMALL_NOTIONAL_USD_THRESHOLD`
    use the full mode-configured window (default 120 min). Smaller
    positions use `SMALL_NOTIONAL_FORCE_CLOSE_MIN` (default 30 min) —
    settlement-period spread widening matters less when the size is
    tiny, so we let small positions ride closer to settlement.
    """
    remaining = remaining_minutes_to_expiry(pos, now_ms)
    if remaining is None:
        return False, ""

    if notional_usd is None:
        try:
            notional_usd = float(pos.sized_trade.position_value or 0.0)
        except Exception:
            notional_usd = 0.0

    if notional_usd > SMALL_NOTIONAL_USD_THRESHOLD:
        window = max(1, int(mode_force_close_min))
    else:
        window = SMALL_NOTIONAL_FORCE_CLOSE_MIN

    if remaining <= window:
        return True, f"force_close_dte:{remaining:.0f}min<{window}min"
    return False, ""


def is_at_settlement(pos: Any, now_ms: Optional[int] = None) -> bool:
    """True when the position has crossed actual expiry — the close
    should be tagged settlement_recorded=True and fill_type="settlement"
    so post-tax PnL and audit accounting are correct."""
    remaining = remaining_minutes_to_expiry(pos, now_ms)
    return remaining is not None and remaining <= 0.0


# ── microstructure veto on amend ──────────────────────────────────────


MAX_AMEND_SPREAD_PCT = 0.08


def should_veto_amend(option: OptionSummary) -> tuple[bool, str]:
    """When the current spread is wider than 8% of mid, defer any
    cancel_replace_stop on this option's bracket. The cancel side fires
    fine, but the replace-side carrier order can fill at a synthetic
    mid that's 10-20% from the true price on illiquid strikes.

    Returns `(should_veto, reason)`. The monitor loop calls back on the
    next poll; if the spread has tightened, the amend goes through.
    """
    sp = float(getattr(option, "spread_pct", 0.0) or 0.0)
    if sp <= 0:
        return False, ""        # no spread info → don't block
    if sp > MAX_AMEND_SPREAD_PCT:
        return True, f"spread_too_wide:{sp:.2%}>{MAX_AMEND_SPREAD_PCT:.0%}"
    return False, ""


# ── premium-aware exit pricing ────────────────────────────────────────


def option_close_kwargs(
    option: Optional[OptionSummary], at_settlement: bool, trigger_reason: str,
) -> dict:
    """Build the kwargs to pass into `paper_store.close_position` for
    an options exit so the realised PnL uses the current premium and
    the settlement/exit-reason audit fields are stamped correctly.

    `trigger_reason` is the upstream cause ("trail" / "stop" / "tp" /
    "signal:<type>" / "force_close_dte" / "manual"). When the close
    crosses actual expiry, settlement_recorded=True is set and
    fill_type is "settlement"; otherwise fill_type is "normal".

    Returns a dict; spread as `close_position(pos_id, spot, **kwargs)`.
    """
    kwargs: dict[str, Any] = {"exit_reason": trigger_reason}
    if option is not None:
        # Use mark_price as the closing premium; the live order, when it
        # fires, will report its own average_fill_price which the order
        # router records — this is for paper bookkeeping.
        kwargs["exit_premium"] = float(option.mark_price or option.mid_price or 0.0)
    if at_settlement:
        kwargs["settlement_recorded"] = True
        kwargs["fill_type"] = "settlement"
    else:
        kwargs["fill_type"] = "normal"
    return kwargs
