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
    symbol: str                 # option tradingsymbol
    exchange: str               # NFO / BFO
    token: int = 0              # instrument token (for tick subscription)
    qty: int = 0                # total quantity (lots × lot_size)
    lot_size: int = 0
    entry_premium: float = 0.0  # intended entry (scan-time premium)
    stop_premium: float = 0.0   # current trail level (premium ST trail)
    order_id: str = ""
    fill_price: float = 0.0     # actual avg fill (from WS order update)
    status: str = PENDING
    gtt_id: int = 0             # broker-side protective stop id (0 = none)
    stop_mode: str = "both"     # broker | monitor | both
    guard_key: str = ""         # the state.auto_open slot this position guards
    opened_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    closed_ms: int = 0
    exit_reason: str = ""


_positions: Dict[str, Dict[str, OpenPosition]] = {}   # uid → {symbol → OpenPosition}


# ── pure exit predicate ──────────────────────────────────────────────────────
def should_exit(stop_premium: float, ltp: float) -> bool:
    """True when a long option's live premium has breached (≤) its trail.

    Auto-exec only ever BUYS options, so protection is a downside stop: exit when
    the last traded premium falls to or below the trail. A non-positive stop means
    'no stop set' → never auto-exit on it. A non-positive ltp is treated as a stale
    tick and ignored (don't exit on a bad print).
    """
    if stop_premium <= 0 or ltp <= 0:
        return False
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


def mark_filled(uid: str, symbol: str, fill_price: float) -> Optional[OpenPosition]:
    p = _load(uid).get(symbol)
    if p is None:
        return None
    p.status = OPEN
    if fill_price > 0:
        p.fill_price = float(fill_price)
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
    """Raise (trail-up) or set the stop for a held position. Stops only ratchet
    UP for a long option — a lower new trail (looser stop) is ignored so the
    monitor never relaxes protection mid-trade."""
    p = _load(uid).get(symbol)
    if p is None:
        return None
    if stop_premium > p.stop_premium:
        p.stop_premium = float(stop_premium)
    if gtt_id is not None:
        p.gtt_id = int(gtt_id)
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
