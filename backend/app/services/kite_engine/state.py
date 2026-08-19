"""Shared in-memory state for the Kite engine: per-user config, activity log and
scan status. Used by both the HTTP endpoints and the background auto-scan loop.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Set
import json

from app.engines.analytics.correlation import CorrelationTracker
from app.engines.risk.circuit_breaker import CircuitBreakerConfig, DrawdownCircuitBreaker
from app.engines.sterling_kite_engine.schemas import ActivityEvent, EngineConfigModel
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
_auto_open: Dict[str, Set[str]] = {}
_breakers: Dict[str, DrawdownCircuitBreaker] = {}
_correlation: Dict[str, CorrelationTracker] = {}
_daily_pnl: Dict[str, tuple] = {}


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


def log(uid: str, kind: str, message: str) -> None:
    buf = _activity.setdefault(uid, deque(maxlen=_ACTIVITY_MAX))
    buf.append(ActivityEvent(ts_ms=int(time.time() * 1000), kind=kind, message=message))


def activity(uid: str, limit: int = 200) -> List[ActivityEvent]:
    buf = _activity.get(uid)
    if not buf:
        return []
    return list(buf)[-limit:]


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
    s = status(uid)
    if s.cancel_cooldown_ms and time.time() * 1000 < s.cancel_cooldown_ms:
        return True
    return False


def set_cooldown(uid: str) -> None:
    s = status(uid)
    s.cancel_cooldown_ms = int(time.time() * 1000 + _COOLDOWN_S * 1000)


def _load_auto_open(uid: str) -> Set[str]:
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
    current = _load_auto_open(uid)
    reconciled = current & set(broker_slots)
    _auto_open[uid] = reconciled
    _persist_auto_open(uid)
    return reconciled


def drawdown_multiplier(uid: str, portfolio_value: float) -> tuple:
    if portfolio_value <= 0:
        return 1.0, "clear"
    brk = _breakers.get(uid)
    if brk is None:
        brk = DrawdownCircuitBreaker(CircuitBreakerConfig(), portfolio_value)
        _breakers[uid] = brk
    st = brk.update(portfolio_value)
    return brk.size_multiplier(), st.value


def _ist_today_iso() -> str:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()


def _load_daily_pnl(uid: str) -> tuple | None:
    if uid not in _daily_pnl:
        try:
            raw = db.get_config(f"kite_engine_daily_pnl_{uid}")
            if raw:
                d = json.loads(raw)
                _daily_pnl[uid] = (str(d[0]), float(d[1]))
        except Exception:
            # Normal read APIs historically fail open here. The strict broker-risk
            # accessor below does not: it re-reads through the same DB boundary and
            # propagates failures so entry is blocked rather than resetting PnL to 0.
            pass
    return _daily_pnl.get(uid)


def _persist_daily_pnl(uid: str) -> None:
    cur = _daily_pnl.get(uid)
    db.set_config(f"kite_engine_daily_pnl_{uid}",
                  json.dumps([cur[0], cur[1]]) if cur else "")


def record_realized_pnl(uid: str, pnl: float, *, day_iso: str | None = None) -> float:
    day = day_iso or _ist_today_iso()
    cur = _load_daily_pnl(uid)
    total = (cur[1] + float(pnl)) if (cur and cur[0] == day) else float(pnl)
    _daily_pnl[uid] = (day, total)
    _persist_daily_pnl(uid)
    return total


def daily_realized_pnl(uid: str, *, day_iso: str | None = None) -> float:
    day = day_iso or _ist_today_iso()
    cur = _load_daily_pnl(uid)
    return cur[1] if (cur and cur[0] == day) else 0.0


def daily_realized_pnl_strict(uid: str, *, day_iso: str | None = None) -> float:
    """Risk-path read: DB/serialization failures propagate instead of becoming zero."""
    day = day_iso or _ist_today_iso()
    if uid not in _daily_pnl:
        raw = db.get_config(f"kite_engine_daily_pnl_{uid}")
        if raw:
            d = json.loads(raw)
            _daily_pnl[uid] = (str(d[0]), float(d[1]))
    cur = _daily_pnl.get(uid)
    return cur[1] if (cur and cur[0] == day) else 0.0


def feed_correlation(uid: str, asset: str, close: float) -> None:
    if close <= 0:
        return
    trk = _correlation.get(uid)
    if trk is None:
        trk = CorrelationTracker(assets=[])
        _correlation[uid] = trk
    trk.update(asset, float(close))


def correlation_penalty(uid: str, new_asset: str, open_assets: list) -> float:
    trk = _correlation.get(uid)
    if trk is None or not open_assets:
        return 1.0
    try:
        return float(trk.portfolio_correlation_penalty(new_asset, list(open_assets)))
    except Exception:
        return 1.0


def save_signal_cache(uid: str, rows: list, generated_ms: int) -> None:
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
    if uid:
        _config.pop(uid, None); _activity.pop(uid, None)
        _status.pop(uid, None); _auto_open.pop(uid, None)
        _breakers.pop(uid, None); _correlation.pop(uid, None)
        _daily_pnl.pop(uid, None)
        try:
            db.set_config(f"kite_engine_daily_pnl_{uid}", "")
        except Exception:
            pass
    else:
        _config.clear(); _activity.clear(); _status.clear(); _auto_open.clear()
        _breakers.clear(); _correlation.clear(); _daily_pnl.clear()
