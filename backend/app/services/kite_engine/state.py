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
# Underlyings with an auto-executed position open (one position per underlying).
_auto_open: Dict[str, Set[str]] = {}
# Per-user portfolio drawdown breaker (directional mode, opt-in). Persists its
# peak across scans so the drawdown is measured against the real high-water mark.
_breakers: Dict[str, DrawdownCircuitBreaker] = {}
# Per-user EWM correlation tracker (directional mode, opt-in). Fed each scanned
# underlying's latest 1H close so a new entry that's highly correlated with an
# already-open position is downsized (don't stack 3 full-size correlated longs).
_correlation: Dict[str, CorrelationTracker] = {}
# Per-user realized PnL for the current IST trading day → INR daily-loss breaker.
# Value is (day_iso, cumulative_pnl); resets when the day rolls over.
_daily_pnl: Dict[str, tuple] = {}


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
    cfg = _config[uid]
    # One-time migration: flip stale engine_enabled=False → True so existing users
    # land in the active engine state after the default changed to True.
    if not cfg.engine_enabled:
        _config[uid] = cfg.model_copy(update={"engine_enabled": True})
        try:
            db.set_config(f"kite_engine_config_{uid}", _config[uid].model_dump_json())
        except Exception:
            pass
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


# ── portfolio drawdown breaker (directional mode, opt-in & fail-safe) ────────
def drawdown_multiplier(uid: str, portfolio_value: float) -> tuple:
    """Feed the per-user breaker the latest portfolio value and return
    ``(size_multiplier, state_label)``. CLEAR→1.0, WARNING→0.5, HALT/RESET→0.0.
    The breaker only ever REDUCES size or blocks new entries (fail-safe). A
    non-positive value is treated as 'unknown' → no throttle."""
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


def record_realized_pnl(uid: str, pnl: float, *, day_iso: str | None = None) -> float:
    """Accumulate a closed trade's realized PnL (INR) into the running total for the
    current IST trading day. Resets automatically when the day rolls over. Returns the
    new day total. Feeds the INR daily-loss breaker (there is no USD/crypto breaker on
    Kite). ``day_iso`` is injectable for deterministic tests."""
    day = day_iso or _ist_today_iso()
    cur = _daily_pnl.get(uid)
    total = (cur[1] + float(pnl)) if (cur and cur[0] == day) else float(pnl)
    _daily_pnl[uid] = (day, total)
    return total


def daily_realized_pnl(uid: str, *, day_iso: str | None = None) -> float:
    """Realized PnL (INR) accumulated so far in the current IST trading day (0 if none
    or the stored total is from a previous day)."""
    day = day_iso or _ist_today_iso()
    cur = _daily_pnl.get(uid)
    return cur[1] if (cur and cur[0] == day) else 0.0


def feed_correlation(uid: str, asset: str, close: float) -> None:
    """Feed the per-user correlation tracker one 1H close for ``asset``."""
    if close <= 0:
        return
    trk = _correlation.get(uid)
    if trk is None:
        trk = CorrelationTracker(assets=[])
        _correlation[uid] = trk
    trk.update(asset, float(close))


def correlation_penalty(uid: str, new_asset: str, open_assets: list) -> float:
    """Size multiplier (1.0 / 0.7 / 0.4) for a new entry given the underlyings of
    already-open positions. 1.0 when the tracker is cold or nothing is open."""
    trk = _correlation.get(uid)
    if trk is None or not open_assets:
        return 1.0
    try:
        return float(trk.portfolio_correlation_penalty(new_asset, list(open_assets)))
    except Exception:
        return 1.0


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
        _breakers.pop(uid, None); _correlation.pop(uid, None)
        _daily_pnl.pop(uid, None)
    else:
        _config.clear(); _activity.clear(); _status.clear(); _auto_open.clear()
        _breakers.clear(); _correlation.clear(); _daily_pnl.clear()


def load_signal_cache(uid: str):
    raw = db.get_config(f"kite_engine_signals_{uid}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data["rows"], data["generated_ms"]
    except Exception:
        return None
