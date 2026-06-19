"""Shared in-memory state for the Kite engine: per-user config, activity log and
scan status. Used by both the HTTP endpoints and the background auto-scan loop.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Set
import json

from app.engines.triple_supertrend.schemas import ActivityEvent, EngineConfigModel
from app.services import db

_ACTIVITY_MAX = 2000


@dataclass
class _Status:
    scanning: bool = False
    last_scan_ms: int = 0
    next_scan_ms: int = 0
    signal_count: int = 0
    cancel_cooldown_ms: int = 0


_config: Dict[str, EngineConfigModel] = {}
_activity: Dict[str, Deque[ActivityEvent]] = {}
_status: Dict[str, _Status] = {}
# Underlyings with an auto-executed position open (one position per underlying).
_auto_open: Dict[str, Set[str]] = {}


# ── config ──────────────────────────────────────────────────────────────────
def get_config(uid: str) -> EngineConfigModel:
    if uid not in _config:
        try:
            saved = db.get_config(f"kite_engine_config_{uid}")
            if saved:
                _config[uid] = EngineConfigModel.model_validate_json(saved)
            else:
                _config[uid] = EngineConfigModel()
        except Exception:
            _config[uid] = EngineConfigModel()
    return _config[uid]


def set_config(uid: str, cfg: EngineConfigModel) -> EngineConfigModel:
    _config[uid] = cfg
    try:
        db.set_config(f"kite_engine_config_{uid}", cfg.model_dump_json())
    except Exception:
        pass
    return cfg


# ── activity log ────────────────────────────────────────────────────────────
def log(uid: str, kind: str, message: str) -> None:
    buf = _activity.setdefault(uid, deque(maxlen=_ACTIVITY_MAX))
    buf.append(ActivityEvent(ts_ms=int(time.time() * 1000), kind=kind, message=message))


def activity(uid: str, limit: int = 200) -> List[ActivityEvent]:
    buf = _activity.get(uid)
    if not buf:
        return []
    return list(buf)[-limit:]


# ── scan status ─────────────────────────────────────────────────────────────
def status(uid: str) -> _Status:
    return _status.setdefault(uid, _Status())


def set_scanning(uid: str, scanning: bool) -> None:
    status(uid).scanning = scanning


def mark_scan_done(uid: str, *, signal_count: int, next_in_s: float) -> None:
    s = status(uid)
    now = int(time.time() * 1000)
    s.scanning = False
    s.last_scan_ms = now
    s.next_scan_ms = now + int(next_in_s * 1000)
    s.signal_count = signal_count


_COOLDOWN_S = 60


def clear_cooldown(uid: str) -> bool:
    """Returns True if the user is in a cancel cooldown (scan should not start)."""
    s = status(uid)
    if s.cancel_cooldown_ms and time.time() * 1000 < s.cancel_cooldown_ms:
        return True
    return False


def set_cooldown(uid: str) -> None:
    s = status(uid)
    s.cancel_cooldown_ms = int(time.time() * 1000 + _COOLDOWN_S * 1000)


# ── auto-exec open positions (one per slot) ─────────────────────────────────
# A "slot" is the per-underlying key for spot signals and the per-contract option
# symbol for derivatives. The guard prevents the 5-min scan from re-buying a slot
# it already holds. It is DB-persisted (key ``kite_engine_auto_open_{uid}``) and
# reconciled against the broker's real positions on startup so a server restart
# can't drop the guard and double-enter — see ``reconcile_auto_open``.
def _load_auto_open(uid: str) -> Set[str]:
    """Hydrate the in-memory slot set for ``uid`` from DB on first access."""
    if uid not in _auto_open:
        try:
            raw = db.get_config(f"kite_engine_auto_open_{uid}")
            _auto_open[uid] = set(json.loads(raw)) if raw else set()
        except Exception:
            _auto_open[uid] = set()
    return _auto_open[uid]


def _persist_auto_open(uid: str) -> None:
    try:
        db.set_config(f"kite_engine_auto_open_{uid}", json.dumps(sorted(_auto_open.get(uid, set()))))
    except Exception:
        pass


def is_auto_open(uid: str, underlying: str) -> bool:
    return underlying in _load_auto_open(uid)


def mark_auto_open(uid: str, underlying: str) -> None:
    _load_auto_open(uid).add(underlying)
    _persist_auto_open(uid)


def clear_auto_open(uid: str, underlying: str) -> None:
    _load_auto_open(uid).discard(underlying)
    _persist_auto_open(uid)


def auto_open_underlyings(uid: str) -> Set[str]:
    return set(_load_auto_open(uid))


def reconcile_auto_open(uid: str, broker_slots: Set[str]) -> Set[str]:
    """Sync the auto-open guard to ground truth: keep only slots the broker
    confirms are still open, drop the rest. Called on startup after fetching
    ``GET /positions`` so a restart can't leave a stale guard (blocking re-entry
    forever) or a dropped guard (allowing a double-entry). Returns the new set.

    ``broker_slots`` should contain BOTH the per-contract option symbols (for
    derivatives slots) and the underlyings (for spot slots) of every open
    position, since the guard keys can be either. Persists the result.
    """
    current = _load_auto_open(uid)
    reconciled = current & set(broker_slots)
    _auto_open[uid] = reconciled
    _persist_auto_open(uid)
    return reconciled


# ── signal cache (DB-persisted for restarts / market-closed hours) ────────
def save_signal_cache(uid: str, rows: list, generated_ms: int) -> None:
    """Persist the latest scan rows. ``rows`` is a list of plain dicts
    (``model_dump`` output) — encoded once here, not parsed-then-reencoded."""
    try:
        data = json.dumps({"rows": rows, "generated_ms": generated_ms})
        db.set_config(f"kite_engine_signals_{uid}", data)
    except Exception:
        pass


def load_signal_cache(uid: str):
    raw = db.get_config(f"kite_engine_signals_{uid}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data["rows"], data["generated_ms"]
    except Exception:
        return None


def reset(uid: str = "") -> None:
    """Test helper."""
    if uid:
        _config.pop(uid, None); _activity.pop(uid, None)
        _status.pop(uid, None); _auto_open.pop(uid, None)
    else:
        _config.clear(); _activity.clear(); _status.clear(); _auto_open.clear()


def load_signal_cache(uid: str):
    raw = db.get_config(f"kite_engine_signals_{uid}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data["rows"], data["generated_ms"]
    except Exception:
        return None
