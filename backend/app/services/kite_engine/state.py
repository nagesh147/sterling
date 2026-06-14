"""Shared in-memory state for the Kite engine: per-user config, activity log and
scan status. Used by both the HTTP endpoints and the background auto-scan loop.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Set

from app.engines.triple_supertrend.schemas import ActivityEvent, EngineConfigModel

_ACTIVITY_MAX = 300


@dataclass
class _Status:
    scanning: bool = False
    last_scan_ms: int = 0
    next_scan_ms: int = 0
    signal_count: int = 0


_config: Dict[str, EngineConfigModel] = {}
_activity: Dict[str, Deque[ActivityEvent]] = {}
_status: Dict[str, _Status] = {}
# Underlyings with an auto-executed position open (one position per underlying).
_auto_open: Dict[str, Set[str]] = {}


# ── config ──────────────────────────────────────────────────────────────────
def get_config(uid: str) -> EngineConfigModel:
    return _config.setdefault(uid, EngineConfigModel())


def set_config(uid: str, cfg: EngineConfigModel) -> EngineConfigModel:
    _config[uid] = cfg
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


# ── auto-exec open positions (one per underlying) ───────────────────────────
def is_auto_open(uid: str, underlying: str) -> bool:
    return underlying in _auto_open.get(uid, set())


def mark_auto_open(uid: str, underlying: str) -> None:
    _auto_open.setdefault(uid, set()).add(underlying)


def clear_auto_open(uid: str, underlying: str) -> None:
    _auto_open.get(uid, set()).discard(underlying)


def auto_open_underlyings(uid: str) -> Set[str]:
    return set(_auto_open.get(uid, set()))


def reset(uid: str = "") -> None:
    """Test helper."""
    if uid:
        _config.pop(uid, None); _activity.pop(uid, None)
        _status.pop(uid, None); _auto_open.pop(uid, None)
    else:
        _config.clear(); _activity.clear(); _status.clear(); _auto_open.clear()
