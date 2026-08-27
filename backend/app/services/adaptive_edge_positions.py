"""Position registry for Adaptive Edge, persisted in its own namespace.

Deliberately not ``kite_engine.positions``. Two engines sharing one registry
means one engine's reconcile can close the other's position, and the symbol is
not enough to tell them apart when both hold the same strike.

The lifecycle state on each record is the one from
``app.engines.adaptive_edge.state_machine``, so a position's state can only
change through a transition that module allows. A broker event with no defined
transition raises rather than leaving the position somewhere nobody designed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.adaptive_edge.state_machine import Event, StrategyState, transition

log = get_logger(__name__)

_cache: dict[str, dict[str, "AdaptiveEdgePosition"]] = {}


@dataclass
class AdaptiveEdgePosition:
    """One option position this engine opened, and how it got here."""

    symbol: str
    token: int
    underlying: str
    direction: str                      # "CE" or "PE" — the contract bought
    quantity: int
    lot_size: int
    entry_price: float
    stop_price: float
    target_price: Optional[float]
    state: str = StrategyState.INTENT.value
    order_id: str = ""
    protection_order_id: str = ""
    opened_ms: int = 0
    closed_ms: int = 0
    exit_price: float = 0.0
    exit_reason: str = ""
    peak_price: float = 0.0
    authorized_risk: float = 0.0
    signal_id: str = ""
    idempotency_key: str = ""
    notes: tuple[str, ...] = ()
    exchange: str = "NFO"
    tick_size: float = 0.05
    stop_mode: str = "both"
    #: Broker-side trigger id, 0 when there is no broker stop. The difference
    #: between "protected" and "protected only while this process lives".
    gtt_id: int = 0
    #: The stop the broker trigger is actually sitting at. A ratcheted trail that
    #: is not pushed to the broker leaves the GTT at the original stop, so the
    #: ratchet is cosmetic; this is what makes that detectable.
    gtt_at: float = 0.0
    #: Claimed by _exit_position for the duration of an exit. Every exit path
    #: takes this claim, so the tick monitor and the square-off cannot both sell
    #: the same position.
    exiting: bool = False

    @property
    def is_open(self) -> bool:
        return self.state in (
            StrategyState.OPEN.value,
            StrategyState.PARTIALLY_FILLED.value,
            StrategyState.EXIT_INTENT.value,
            StrategyState.EXIT_ORDERED.value,
        )

    def apply(self, event: Event) -> "AdaptiveEdgePosition":
        """Move the position through the lifecycle, or refuse.

        Refusing is the point. An unhandled broker event that silently left the
        state alone would mean, for example, a rejected exit still reading as
        closed while the position is actually live at the broker.
        """
        result = transition(StrategyState(self.state), event)
        self.state = result.current.value
        return self


def _key(uid: str) -> str:
    return f"adaptive_edge_positions:{uid}"


def _to_dict(p: AdaptiveEdgePosition) -> dict[str, Any]:
    d = asdict(p)
    d["notes"] = list(p.notes)
    return d


def _from_dict(d: dict) -> Optional[AdaptiveEdgePosition]:
    try:
        known = {f for f in AdaptiveEdgePosition.__dataclass_fields__}
        clean = {k: v for k, v in dict(d).items() if k in known}
        if isinstance(clean.get("notes"), list):
            clean["notes"] = tuple(clean["notes"])
        return AdaptiveEdgePosition(**clean)
    except (TypeError, ValueError) as exc:
        log.error("Dropping unreadable adaptive_edge position row (%s)", exc)
        return None


def load(uid: str) -> dict[str, AdaptiveEdgePosition]:
    if uid in _cache:
        return _cache[uid]
    out: dict[str, AdaptiveEdgePosition] = {}
    try:
        from app.services import db
        raw = db.get_config(_key(uid))
        if raw:
            rows = json.loads(raw) if isinstance(raw, str) else raw
            for row in rows or []:
                pos = _from_dict(row)
                if pos is not None:
                    out[pos.symbol] = pos
    except Exception as exc:                                       # noqa: BLE001
        # An unreadable store must not look like "no positions": that would let
        # the engine open a duplicate of something it is already holding.
        log.error("adaptive_edge position store unavailable (%s); refusing to assume flat", exc)
        raise
    _cache[uid] = out
    return out


def persist(uid: str) -> None:
    rows = [_to_dict(p) for p in load(uid).values()]
    try:
        from app.services import db
        db.set_config(_key(uid), json.dumps(rows, separators=(",", ":")))
    except Exception as exc:                                       # noqa: BLE001
        log.error("Could not persist adaptive_edge positions for %s (%s)", uid, exc)


def put(uid: str, pos: AdaptiveEdgePosition) -> AdaptiveEdgePosition:
    load(uid)[pos.symbol] = pos
    persist(uid)
    return pos


def get(uid: str, symbol: str) -> Optional[AdaptiveEdgePosition]:
    return load(uid).get(symbol)


def open_positions(uid: str) -> list[AdaptiveEdgePosition]:
    return [p for p in load(uid).values() if p.is_open]


def mark_filled(uid: str, symbol: str, fill_price: float, *, partial: bool = False,
                order_id: str = "") -> Optional[AdaptiveEdgePosition]:
    pos = get(uid, symbol)
    if pos is None:
        return None
    pos.apply(Event.PARTIAL_FILL if partial else Event.FILL)
    pos.entry_price = float(fill_price)
    pos.peak_price = max(pos.peak_price, float(fill_price))
    if order_id:
        pos.order_id = order_id
    persist(uid)
    return pos


def mark_rejected(uid: str, symbol: str, reason: str = "") -> Optional[AdaptiveEdgePosition]:
    pos = get(uid, symbol)
    if pos is None:
        return None
    pos.apply(Event.REJECTED)
    if reason:
        pos.notes = pos.notes + (reason,)
    persist(uid)
    return pos


def close(uid: str, symbol: str, exit_price: float, reason: str = "",
          closed_ms: int = 0) -> Optional[AdaptiveEdgePosition]:
    pos = get(uid, symbol)
    if pos is None:
        return None
    if StrategyState(pos.state) is StrategyState.OPEN:
        pos.apply(Event.EXIT_INTENT)
    if StrategyState(pos.state) is StrategyState.EXIT_INTENT:
        pos.apply(Event.ORDER_SUBMITTED)
    pos.apply(Event.FILL)
    pos.exit_price = float(exit_price)
    pos.exit_reason = reason
    pos.closed_ms = int(closed_ms)
    persist(uid)
    return pos


def forget_closed(uid: str) -> None:
    positions = load(uid)
    for symbol in [s for s, p in positions.items() if not p.is_open]:
        positions.pop(symbol, None)
    persist(uid)


def reset(uid: str = "") -> None:
    if uid:
        _cache.pop(uid, None)
    else:
        _cache.clear()
