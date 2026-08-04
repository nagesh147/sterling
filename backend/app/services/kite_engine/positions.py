"""Open auto-exec option positions registry (workstreams E / C / D / F).

A small, DB-persisted store of the option positions auto-exec has opened, plus a
pure exit predicate. It is the shared source of truth for three consumers:

  * the WS order-update handler (E) — confirms fills, stamps the real fill price
    and COMPLETE/REJECTED status instead of assuming success;
  * the tick monitor (C/D) — reads each open position's current trail and exits
    intrabar when the premium breaches it;
  * risk sizing (F) — records the sized qty / premium-at-risk for the order.

Persisted (``kite_engine_positions_{uid}``) so a restart rehydrates open positions
and the monitor can keep guarding them. Pure functions where possible; the store
holds no broker handles and makes no network calls.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

from app.services import db


# Lifecycle of an auto-exec position.
PENDING = "pending"     # entry order placed, fill not yet confirmed
OPEN = "open"           # fill confirmed (or assumed), guarding active
CLOSED = "closed"       # exited (stop hit / manual / trail breach)
REJECTED = "rejected"   # broker rejected/cancelled the entry order


@dataclass
class OpenPosition:
    uid: str
    symbol: str                 # option tradingsymbol or futures tradingsymbol
    exchange: str               # NFO / BFO
    token: int = 0              # instrument token (for tick subscription)
    qty: int = 0                # total quantity (lots × lot_size)
    lot_size: int = 0
    entry_premium: float = 0.0  # intended entry (scan-time premium or futures price)
    stop_premium: float = 0.0   # current trail level (premium ST trail or futures stop)
    order_id: str = ""
    fill_price: float = 0.0     # actual avg fill (from WS order update)
    status: str = PENDING
    gtt_id: int = 0             # broker-side protective stop id (0 = none)
    stop_mode: str = "both"     # broker | monitor | both
    guard_key: str = ""         # the state.auto_open slot this position guards
    direction: str = "long"     # "long" | "short" — options are always long; futures can be either
    vehicle: str = "otm_options" # otm_options | deep_itm_options | futures
    underlying: str = ""        # display underlying ("NIFTY 50") — for correlation grouping
    opened_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    closed_ms: int = 0
    exit_reason: str = ""
    exit_mode: str = "one_red"  # exit counter chosen at entry time (one_red/two_red/three_red/three_red_signal)
    current_red_count: int = 0  # latest computed red ST lines against this position (updated on scans)
    # ── delta-translation context (workstream: spot-mode + deep-ITM premium stop) ──
    # For option vehicles the protective stop lives in PREMIUM space but the signal's
    # trail lives in UNDERLYING space. We store the entry underlying spot + the BS
    # delta so every trailing update can re-translate the fresh underlying ST level
    # into a premium stop (``greeks.premium_stop_from_move``) — both at entry and each
    # scan. 0.0 delta means "no translation context" (e.g. futures, which trail in
    # index points directly).
    entry_spot: float = 0.0     # underlying price at entry (index level)
    entry_delta: float = 0.0    # |BS delta| of the held option at entry
    strike: float = 0.0         # option strike (for re-pricing / display)
    expiry: str = ""            # option expiry "YYYY-MM-DD" (for the expiry square-off guard)
    initial_stop_premium: float = 0.0  # first stop set at entry — the step-out floor (never risk more than this)
    #: Premium at which this position books profit, or 0.0 when the signal has no
    #: target. Only Navigator originations carry one (from the AVWAP proposal); a
    #: SuperTrend row has no target by design — it exits on the trail or the red
    #: counter. Enforced BROKER-side as the second leg of an OCO GTT, so the
    #: exchange cancels the stop when the target fills and vice versa.
    target_premium: float = 0.0
    # derived threshold from exit_mode for convenience in responses/UI


_positions: Dict[str, Dict[str, OpenPosition]] = {}   # uid → {symbol → OpenPosition}


# ── pure exit predicate ──────────────────────────────────────────────────────
def should_exit(stop_premium: float, ltp: float, direction: str = "long") -> bool:
    """True when a position's live price has breached its trail.

    For long positions (options + long futures): exit when LTP ≤ stop (downside).
    For short futures: exit when LTP ≥ stop (upside, buy-to-cover).
    A non-positive stop means 'no stop set' → never auto-exit on it.
    A non-positive ltp is treated as a stale tick and ignored.
    """
    if stop_premium <= 0 or ltp <= 0:
        return False
    if direction == "short":
        return ltp >= stop_premium
    return ltp <= stop_premium


# ── persistence ──────────────────────────────────────────────────────────────
def _load(uid: str) -> Dict[str, OpenPosition]:
    if uid not in _positions:
        out: Dict[str, OpenPosition] = {}
        try:
            raw = db.get_config(f"kite_engine_positions_{uid}")
            if raw:
                for d in json.loads(raw):
                    p = OpenPosition(**d)
                    out[p.symbol] = p
        except Exception:
            out = {}
        _positions[uid] = out
    return _positions[uid]


def _persist(uid: str) -> None:
    try:
        rows = [asdict(p) for p in _positions.get(uid, {}).values()]
        db.set_config(f"kite_engine_positions_{uid}", json.dumps(rows))
    except Exception:
        pass


# ── registry API ─────────────────────────────────────────────────────────────
def register(p: OpenPosition) -> OpenPosition:
    """Record a newly-placed entry order (status pending until a fill confirms)."""
    _load(p.uid)[p.symbol] = p
    _persist(p.uid)
    return p


def get(uid: str, symbol: str) -> Optional[OpenPosition]:
    return _load(uid).get(symbol)


def open_positions(uid: str) -> List[OpenPosition]:
    """Positions still being guarded (pending or open)."""
    return [p for p in _load(uid).values() if p.status in (PENDING, OPEN)]


def all_open_tokens(uid: str) -> List[int]:
    return [p.token for p in open_positions(uid) if p.token]


def mark_filled(uid: str, symbol: str, fill_price: float,
                filled_qty: int = 0) -> Optional[OpenPosition]:
    """Confirm a fill. ``filled_qty``, when supplied by the broker postback, becomes
    the position's quantity.

    The quantity matters as much as the price: every downstream number is derived
    from ``qty`` — the exit SELL, the GTT's order quantity, and the realized PnL. If
    2 of 3 intended lots fill and we keep believing we hold 3, both the broker stop
    and the monitor try to sell 3, and the extra lot is a naked short.
    """
    p = _load(uid).get(symbol)
    if p is None:
        return None
    p.status = OPEN
    if fill_price > 0:
        p.fill_price = float(fill_price)
    if filled_qty > 0:
        p.qty = int(filled_qty)
    _persist(uid)
    return p


def mark_rejected(uid: str, symbol: str, reason: str = "") -> Optional[OpenPosition]:
    p = _load(uid).get(symbol)
    if p is None:
        return None
    p.status = REJECTED
    p.exit_reason = reason or "broker rejected/cancelled"
    p.closed_ms = int(time.time() * 1000)
    _persist(uid)
    return p


def update_stop(uid: str, symbol: str, stop_premium: float, gtt_id: Optional[int] = None) -> Optional[OpenPosition]:
    """Tighten (trail) or set the stop for a held position. The stop only ratchets
    in the protective direction so the monitor never relaxes protection mid-trade:
    UP for a long (option or long future), DOWN for a short future. A looser new
    trail is ignored."""
    p = _load(uid).get(symbol)
    if p is None:
        return None
    if p.direction == "short":
        # short future: the protective stop sits ABOVE price → ratchets DOWN.
        if stop_premium > 0 and (p.stop_premium <= 0 or stop_premium < p.stop_premium):
            p.stop_premium = float(stop_premium)
    elif stop_premium > p.stop_premium:
        # long (option or long future): the stop sits BELOW price → ratchets UP.
        p.stop_premium = float(stop_premium)
    if gtt_id is not None:
        p.gtt_id = int(gtt_id)
    _persist(uid)
    return p

def update_health(uid: str, symbol: str, red_count: int, exit_mode: Optional[str] = None) -> Optional[OpenPosition]:
    """Update live red count health for a position (from scan regime). Persisted for UI."""
    p = _load(uid).get(symbol)
    if p is None:
        return None
    p.current_red_count = max(0, int(red_count))
    if exit_mode:
        p.exit_mode = exit_mode
    _persist(uid)
    return p


def close(uid: str, symbol: str, reason: str = "") -> Optional[OpenPosition]:
    p = _load(uid).get(symbol)
    if p is None:
        return None
    p.status = CLOSED
    p.exit_reason = reason or "closed"
    p.closed_ms = int(time.time() * 1000)
    _persist(uid)
    return p


def reset(uid: str = "") -> None:
    """Test helper."""
    if uid:
        _positions.pop(uid, None)
    else:
        _positions.clear()
