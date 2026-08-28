"""Durable open-position registry for OI Wall Flow.

Positions must survive a restart. Holding them only in memory means a crash
while long leaves an option position at the broker that nothing is watching and
nothing will ever exit -- and the process that comes back has no idea it exists.

**Why this is not ``kite_engine.positions``.** That registry is a single per-user
store that the SuperTrend engine's own monitor manages. Registering OI Wall Flow
positions there would put two engines in charge of one position.
"""
from __future__ import annotations

import json
from dataclasses import asdict, fields
from typing import Optional

from app.core.logging import get_logger
from app.engines.oi_wall_flow import InstrumentRef, PositionState

log = get_logger(__name__)

PENDING, OPEN, CLOSED, REJECTED = "pending", "open", "closed", "rejected"

_cache: dict[str, dict[str, PositionState]] = {}


def _key(uid: str) -> str:
    return f"oi_wall_flow_positions_{uid}"


def _to_dict(p: PositionState) -> dict:
    d = asdict(p)
    d["instrument"] = asdict(p.instrument) if p.instrument is not None else None
    return d


def _from_dict(d: dict) -> Optional[PositionState]:
    try:
        inst = None
        raw_inst = d.get("instrument") or None
        if raw_inst:
            inst_fields = {f.name for f in fields(InstrumentRef)}
            inst = InstrumentRef(**{k: v for k, v in raw_inst.items() if k in inst_fields})
        known = {f.name for f in fields(PositionState)} - {"instrument"}
        return PositionState(instrument=inst,
                             **{k: v for k, v in d.items() if k in known})
    except (TypeError, ValueError) as exc:
        log.error("oi_wall_flow: unreadable persisted position dropped (%s): %s", exc, d)
        return None


def load(uid: str) -> dict[str, PositionState]:
    if uid in _cache:
        return _cache[uid]
    out: dict[str, PositionState] = {}
    try:
        from app.services import db
        raw = db.get_config(_key(uid))
        for d in (json.loads(raw) if raw else []):
            p = _from_dict(d)
            if p is not None:
                out[p.tradingsymbol or (p.instrument.tradingsymbol if p.instrument else "")] = p
    except Exception as exc:                                       # noqa: BLE001
        log.error("oi_wall_flow: position registry unreadable for %s: %s", uid, exc)
    _cache[uid] = out
    return out


def persist(uid: str) -> None:
    try:
        from app.services import db
        db.set_config(_key(uid), json.dumps(
            [_to_dict(p) for p in _cache.get(uid, {}).values()], separators=(",", ":")))
    except Exception as exc:                                       # noqa: BLE001
        log.error("oi_wall_flow: FAILED to persist positions for %s: %s", uid, exc)


def put(uid: str, pos: PositionState) -> PositionState:
    symbol = pos.tradingsymbol or (pos.instrument.tradingsymbol if pos.instrument else "")
    load(uid)[symbol] = pos
    persist(uid)
    return pos


def get(uid: str, symbol: str) -> Optional[PositionState]:
    return load(uid).get(symbol)


def open_positions(uid: str) -> list[PositionState]:
    return [p for p in load(uid).values() if p.is_open]


def mark_filled(uid: str, symbol: str, fill_price: float, *,
                gtt_id: int = 0) -> Optional[PositionState]:
    """Record the real average fill and re-anchor the stop to it."""
    pos = get(uid, symbol)
    if pos is None:
        return None
    pos.status = OPEN
    if fill_price > 0:
        drift = fill_price - pos.entry
        pos.fill_price = fill_price
        if drift and pos.stop > 0:
            pos.stop = round(pos.stop + drift, 2)
        pos.high_water = max(pos.high_water, fill_price)
    if gtt_id:
        pos.gtt_id = int(gtt_id)
    persist(uid)
    return pos


def mark_rejected(uid: str, symbol: str, reason: str = "") -> Optional[PositionState]:
    pos = get(uid, symbol)
    if pos is None:
        return None
    pos.status = REJECTED
    persist(uid)
    return pos


def close(uid: str, symbol: str, reason: str = "") -> Optional[PositionState]:
    pos = get(uid, symbol)
    if pos is None:
        return None
    pos.status = CLOSED
    persist(uid)
    return pos


def forget_closed(uid: str) -> None:
    live = {k: v for k, v in load(uid).items() if v.is_open}
    _cache[uid] = live
    persist(uid)


def reset(uid: str = "") -> None:
    if uid:
        _cache.pop(uid, None)
    else:
        _cache.clear()
