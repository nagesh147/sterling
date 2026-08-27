"""Record what the engine saw, so a paper session becomes calibration data.

The engine cannot enter trades yet: §35 requires `DirectionalEdgeOK` and both
expected-value terms, and all three need the probability model that calibration
has to supply. Forcing entries on the non-predictive gates alone — data,
liquidity, slippage, risk — would mean entering on any liquid contract, which is
not a strategy and would produce noise rather than evidence.

Calibration does not need trades. It needs observations paired with what
happened next: features at time *t*, then the forward excursion over the horizon.
That is what this records, so tomorrow's paper session is worth something even
though nothing arms.

Storage is deliberately append-only and keyed by day. An observation whose
outcome is written back later must be the same row, not a second one, or the
forward-return distribution quietly doubles its own sample size.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

#: Cap per day. A runaway scan loop must not grow the config row without bound;
#: losing the tail of one pathological day is better than an unreadable store.
_MAX_PER_DAY = 5_000


@dataclass
class Observation:
    """One candidate, as it looked at one moment, plus its outcome once known."""

    observed_ms: int
    day: str
    underlying: str
    symbol: str
    token: int
    option_type: str
    strike: float
    dte: int
    spot: float
    premium: float
    oi: float
    volume: float
    bid: float = 0.0
    ask: float = 0.0
    #: Filled in later by `record_outcome`. None means "not yet resolved", which
    #: is different from zero and must stay distinguishable — a forward return of
    #: zero is a real observation.
    horizon_bars: Optional[int] = None
    forward_premium: Optional[float] = None
    forward_return_pct: Optional[float] = None
    max_favourable_pct: Optional[float] = None
    max_adverse_pct: Optional[float] = None

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.observed_ms}"


def _key(uid: str, day: str) -> str:
    return f"adaptive_edge_observations:{uid}:{day}"


def _load(uid: str, day: str) -> list[dict[str, Any]]:
    try:
        from app.services import db
        raw = db.get_config(_key(uid, day))
        if not raw:
            return []
        rows = json.loads(raw) if isinstance(raw, str) else raw
        return list(rows or [])
    except Exception as exc:                                       # noqa: BLE001
        log.error("adaptive_edge observation store unreadable for %s/%s (%s)", uid, day, exc)
        return []


def _save(uid: str, day: str, rows: list[dict[str, Any]]) -> None:
    try:
        from app.services import db
        db.set_config(_key(uid, day), json.dumps(rows, separators=(",", ":")))
    except Exception as exc:                                       # noqa: BLE001
        log.error("Could not persist adaptive_edge observations for %s/%s (%s)", uid, day, exc)


def record(uid: str, day: str, candidates: list[dict[str, Any]], *, observed_ms: int) -> int:
    """Append this scan's candidates. Returns how many were newly recorded.

    Scans repeat every 60s and will re-surface the same contract, so a candidate
    already recorded at this timestamp is skipped rather than duplicated.
    """
    if not candidates:
        return 0
    rows = _load(uid, day)
    if len(rows) >= _MAX_PER_DAY:
        return 0
    seen = {f"{r.get('symbol')}:{r.get('observed_ms')}" for r in rows}

    added = 0
    for candidate in candidates:
        observation = Observation(
            observed_ms=observed_ms,
            day=day,
            underlying=str(candidate.get("underlying") or ""),
            symbol=str(candidate.get("symbol") or ""),
            token=int(candidate.get("token") or 0),
            option_type=str(candidate.get("option_type") or ""),
            strike=float(candidate.get("strike") or 0.0),
            dte=int(candidate.get("dte") or 0),
            spot=float(candidate.get("spot") or 0.0),
            premium=float(candidate.get("last_price") or 0.0),
            oi=float(candidate.get("oi") or 0.0),
            volume=float(candidate.get("volume") or 0.0),
            bid=float(candidate.get("bid") or 0.0),
            ask=float(candidate.get("ask") or 0.0),
        )
        if observation.key in seen or not observation.symbol:
            continue
        rows.append(asdict(observation))
        seen.add(observation.key)
        added += 1
        if len(rows) >= _MAX_PER_DAY:
            log.warning("adaptive_edge: observation cap reached for %s/%s", uid, day)
            break

    if added:
        _save(uid, day, rows)
    return added


def record_outcome(uid: str, day: str, key: str, *, forward_premium: float,
                   horizon_bars: int, max_favourable_pct: Optional[float] = None,
                   max_adverse_pct: Optional[float] = None) -> bool:
    """Write the forward outcome back onto the observation it belongs to.

    Updates in place. Appending a second row instead would silently double the
    sample size of any distribution computed over this day.
    """
    rows = _load(uid, day)
    for row in rows:
        if f"{row.get('symbol')}:{row.get('observed_ms')}" != key:
            continue
        entry = float(row.get("premium") or 0.0)
        row["forward_premium"] = float(forward_premium)
        row["horizon_bars"] = int(horizon_bars)
        row["forward_return_pct"] = (
            ((float(forward_premium) - entry) / entry) * 100.0 if entry > 0 else None
        )
        row["max_favourable_pct"] = max_favourable_pct
        row["max_adverse_pct"] = max_adverse_pct
        _save(uid, day, rows)
        return True
    return False


def load(uid: str, day: str) -> list[dict[str, Any]]:
    return _load(uid, day)


def pending(uid: str, day: str) -> list[dict[str, Any]]:
    """Observations whose outcome has not been written yet."""
    return [r for r in _load(uid, day) if r.get("forward_return_pct") is None]


def summary(uid: str, day: str) -> dict[str, Any]:
    """What this day collected, for the operator and for the calibration run."""
    rows = _load(uid, day)
    resolved = [r for r in rows if r.get("forward_return_pct") is not None]
    return {
        "day": day,
        "observations": len(rows),
        "resolved": len(resolved),
        "pending": len(rows) - len(resolved),
        "underlyings": sorted({str(r.get("underlying") or "") for r in rows if r.get("underlying")}),
    }
