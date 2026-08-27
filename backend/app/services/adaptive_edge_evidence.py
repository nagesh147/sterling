"""Persist the engine's live volatility readings, so the gate can learn from them.

The evidence gate needs a record that survives restarts: it opens on hundreds of
readings across dozens of sessions, which is weeks of running. Holding that in
memory would mean the engine forgets every time the process cycles and never
accumulates enough to decide anything.

Readings are appended per session and resolved later, exactly like the
observation recorder — an outcome is written back onto the reading it belongs
to, never appended as a second row, because a duplicated reading quietly doubles
its own weight in the interval the gate computes.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.adaptive_edge.evidence_gate import Reading, Verdict, assess

log = get_logger(__name__)

#: Cap per session. A runaway scan loop must not grow the row without bound.
_MAX_PER_SESSION = 2_000

#: Sessions kept. The gate looks at roughly twenty; keeping ninety leaves room to
#: notice a regime change without carrying the whole history forever.
_KEEP_SESSIONS = 90


@dataclass
class PendingReading:
    """A reading whose outcome is not known yet.

    `realised_move_bps` is None until the horizon passes. None is not zero — a
    zero move is a real and informative outcome, and collapsing the two would
    tell the gate that nothing happened when it means nothing is known.

    `credit_bps` and `max_loss_bps` are None when no tradeable structure existed
    at the moment of measurement — which, with a 30-bar hold and a weekly
    expiry, is nearly always. Such a row is still worth keeping: the
    implied-versus-realised ratio is the fact every offline study of this
    strategy lacked, and it is only observable live. It is NOT gate evidence,
    because expectancy cannot be computed from a trade that was never priced.
    `readings()` enforces that split.
    """

    session: str
    decided_ms: int
    underlying: str
    strike: float
    implied_ratio: float
    implied_vol: float
    realised_vol: float
    credit_bps: Optional[float]
    max_loss_bps: Optional[float]
    forecast_bps: float
    realised_move_bps: Optional[float] = None

    @property
    def key(self) -> str:
        return f"{self.underlying}:{self.strike:.0f}:{self.decided_ms}"


def _median(values: list[float]) -> float:
    ordered = sorted(v for v in values if v)
    if not ordered:
        return 0.0
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def _key(uid: str) -> str:
    return f"adaptive_edge_evidence:{uid}"


def _load(uid: str) -> dict[str, list[dict[str, Any]]]:
    try:
        from app.services import db
        raw = db.get_config(_key(uid))
        if not raw:
            return {}
        return dict(json.loads(raw) if isinstance(raw, str) else raw)
    except Exception as exc:                                       # noqa: BLE001
        log.error("adaptive_edge evidence store unreadable for %s (%s)", uid, exc)
        return {}


def _save(uid: str, data: dict[str, list[dict[str, Any]]]) -> None:
    # Trim oldest sessions first: the gate is about the recent record, and an
    # unbounded row eventually fails to write at all.
    for session in sorted(data)[:-_KEEP_SESSIONS]:
        data.pop(session, None)
    try:
        from app.services import db
        db.set_config(_key(uid), json.dumps(data, separators=(",", ":")))
    except Exception as exc:                                       # noqa: BLE001
        log.error("Could not persist adaptive_edge evidence for %s (%s)", uid, exc)


def record(uid: str, reading: PendingReading) -> bool:
    """Append one decision. Returns False if it was already recorded."""
    data = _load(uid)
    rows = data.setdefault(reading.session, [])
    if len(rows) >= _MAX_PER_SESSION:
        return False
    if any(r.get("decided_ms") == reading.decided_ms
           and r.get("underlying") == reading.underlying
           and float(r.get("strike") or 0) == reading.strike for r in rows):
        return False
    rows.append(asdict(reading))
    _save(uid, data)
    return True


def resolve(uid: str, session: str, key: str, realised_move_bps: float) -> bool:
    """Write the outcome back onto the reading it belongs to."""
    data = _load(uid)
    for row in data.get(session, []):
        if f"{row.get('underlying')}:{float(row.get('strike') or 0):.0f}:{row.get('decided_ms')}" != key:
            continue
        row["realised_move_bps"] = float(realised_move_bps)
        _save(uid, data)
        return True
    return False


def readings(uid: str) -> list[Reading]:
    """Resolved readings, in the shape the gate assesses."""
    out: list[Reading] = []
    for session, rows in _load(uid).items():
        for row in rows:
            move = row.get("realised_move_bps")
            # Gate evidence needs an outcome AND a priced structure. A bare
            # measurement is archived above but proves nothing about expectancy.
            if move is None or row.get("credit_bps") is None:
                continue
            try:
                out.append(Reading(
                    session=str(session),
                    implied_ratio=float(row.get("implied_ratio") or 0.0),
                    credit_bps=float(row.get("credit_bps") or 0.0),
                    max_loss_bps=float(row.get("max_loss_bps") or 0.0),
                    realised_move_bps=float(move)))
            except (TypeError, ValueError):
                continue
    return out


def pending(uid: str, session: str) -> list[dict[str, Any]]:
    return [r for r in _load(uid).get(session, []) if r.get("realised_move_bps") is None]


def verdict(uid: str) -> Verdict:
    """Does the live record support arming the strategy?"""
    return assess(readings(uid))


def summary(uid: str) -> dict[str, Any]:
    v = verdict(uid)
    data = _load(uid)
    return {
        "ready": v.ready,
        "observations": v.observations,
        "sessions": v.sessions,
        "mean_bps": round(v.mean_bps, 3),
        "lower_bound_bps": round(v.lower_bound_bps, 3),
        "median_implied_ratio": round(v.median_implied_ratio, 3),
        "win_rate": round(v.win_rate, 3),
        "reason": v.reason,
        "shortfall": v.shortfall,
        "pending": sum(1 for rows in data.values() for r in rows
                       if r.get("realised_move_bps") is None),
        # Every implied-versus-realised measurement, priced or not. This is the
        # number that grows every scan; `observations` only grows when a
        # structure was actually tradeable, which is far rarer.
        "measurements": sum(len(rows) for rows in data.values()),
        "median_measured_ratio": round(_median([
            float(r.get("implied_ratio") or 0.0)
            for rows in data.values() for r in rows
            if r.get("implied_ratio") is not None]), 3),
    }


def reset(uid: str = "") -> None:
    try:
        from app.services import db
        if uid:
            db.set_config(_key(uid), json.dumps({}))
    except Exception:                                              # noqa: BLE001
        pass
