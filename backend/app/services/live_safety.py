"""Fail-closed live execution safety primitives.

These guards are deliberately conservative. Safety infrastructure must never fail-open:
if its own state cannot be read or evaluated, automated entry is denied.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


_KILL_SWITCH: Dict[str, Any] = {"enabled": False, "reason": "", "set_ts_ms": 0}
_IDEMPOTENCY_CACHE: Dict[str, Tuple[int, str]] = {}
_IDEMPOTENCY_TTL_MS = 60_000
_RETRY_QUEUE: Dict[str, "RetryItem"] = {}


def kill_switch_state() -> Dict[str, Any]:
    return dict(_KILL_SWITCH)


def set_kill_switch(enabled: bool, reason: str = "") -> Dict[str, Any]:
    _KILL_SWITCH["enabled"] = bool(enabled)
    _KILL_SWITCH["reason"] = reason or ("manual halt" if enabled else "")
    _KILL_SWITCH["set_ts_ms"] = int(time.time() * 1000)
    return dict(_KILL_SWITCH)


@dataclass
class DailyLossConfig:
    enabled: bool = True
    soft_warn_inr: float = -1000.0
    hard_halt_inr: float = -1500.0

_DAILY_LOSS_CFG = DailyLossConfig()


def configure_daily_loss(cfg: DailyLossConfig) -> None:
    global _DAILY_LOSS_CFG
    if cfg.hard_halt_inr >= 0 or cfg.soft_warn_inr >= 0 or cfg.soft_warn_inr < cfg.hard_halt_inr:
        raise ValueError("daily-loss thresholds must be negative and soft_warn >= hard_halt")
    _DAILY_LOSS_CFG = cfg


def _today_start_ms_ist() -> int:
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def daily_realized_pnl_inr(positions: List[Any]) -> Optional[float]:
    """Return today's realized INR P&L, or None when position state lacks it."""
    start_ms = _today_start_ms_ist()
    total = 0.0
    seen = False
    for p in positions:
        ts = getattr(p, "exit_timestamp_ms", None) or getattr(p, "closed_ms", None)
        pnl = getattr(p, "realized_pnl_inr", None)
        if pnl is None:
            pnl = getattr(p, "realized_pnl", None)
        if ts and pnl is not None and int(ts) >= start_ms:
            total += float(pnl)
            seen = True
    return round(total, 2) if seen else 0.0


def daily_loss_state(positions: List[Any]) -> Dict[str, Any]:
    pnl = daily_realized_pnl_inr(positions)
    level = "clear"
    if _DAILY_LOSS_CFG.enabled:
        if pnl is None:
            level = "unknown"
        elif pnl <= _DAILY_LOSS_CFG.hard_halt_inr:
            level = "halt"
        elif pnl <= _DAILY_LOSS_CFG.soft_warn_inr:
            level = "warning"
    return {"pnl_inr": pnl, "level": level, "enabled": _DAILY_LOSS_CFG.enabled,
            "soft_warn_inr": _DAILY_LOSS_CFG.soft_warn_inr,
            "hard_halt_inr": _DAILY_LOSS_CFG.hard_halt_inr}


def make_idempotency_key(*parts: Any) -> str:
    payload = "|".join(str(p) for p in parts).encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def check_idempotency(key: str) -> Optional[str]:
    if not key:
        return None
    now = int(time.time() * 1000)
    entry = _IDEMPOTENCY_CACHE.get(key)
    if entry is None:
        return None
    set_ts, order_id = entry
    if now - set_ts > _IDEMPOTENCY_TTL_MS:
        _IDEMPOTENCY_CACHE.pop(key, None)
        return None
    return order_id


def record_idempotency(key: str, order_id: str) -> None:
    if key:
        _IDEMPOTENCY_CACHE[key] = (int(time.time() * 1000), order_id)


@dataclass
class RetryItem:
    id: str
    payload: Dict[str, Any]
    attempt: int = 0
    max_attempts: int = 3
    last_error: str = ""
    enqueued_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    last_attempt_ms: int = 0
    poison: bool = False


def enqueue_retry(payload: Dict[str, Any], error: str, max_attempts: int = 3) -> RetryItem:
    rid = uuid.uuid4().hex[:10].upper()
    item = RetryItem(rid, dict(payload), 0, max_attempts, error)
    _RETRY_QUEUE[rid] = item
    return item


def list_retries(include_poison: bool = True) -> List[RetryItem]:
    items = list(_RETRY_QUEUE.values())
    return sorted(items if include_poison else [i for i in items if not i.poison], key=lambda i: i.enqueued_ms)


def mark_attempt(rid: str, error: str = "") -> Optional[RetryItem]:
    item = _RETRY_QUEUE.get(rid)
    if item is None:
        return None
    item.attempt += 1
    item.last_attempt_ms = int(time.time() * 1000)
    item.last_error = error
    if item.attempt >= item.max_attempts:
        item.poison = True
    return item


def remove_retry(rid: str) -> bool:
    return _RETRY_QUEUE.pop(rid, None) is not None


def clear_retries() -> None:
    _RETRY_QUEUE.clear()


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str = ""
    code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "code": self.code}


def assert_safe_to_trade(positions: List[Any], idempotency_key: Optional[str] = None, *, check_daily_loss: bool = True) -> SafetyDecision:
    try:
        ks = kill_switch_state()
        if ks.get("enabled"):
            return SafetyDecision(False, f"Kill switch active: {ks.get('reason') or 'manual halt'}", "kill_switch")
        if check_daily_loss:
            dl = daily_loss_state(positions)
            if dl["level"] == "unknown":
                return SafetyDecision(False, "Daily INR P&L cannot be established", "daily_loss_unknown")
            if dl["level"] == "halt":
                return SafetyDecision(False, f"Daily loss circuit breaker: INR {dl['pnl_inr']:.2f} <= INR {dl['hard_halt_inr']:.2f}", "daily_loss_halt")
        if idempotency_key:
            prior = check_idempotency(idempotency_key)
            if prior:
                return SafetyDecision(False, f"Duplicate order — already placed as {prior}", "duplicate_order")
        return SafetyDecision(True)
    except Exception as exc:
        # Never fail-open on a safety primitive failure.
        return SafetyDecision(False, f"Safety evaluation failed closed: {exc}", "safety_unknown")


@dataclass
class PerSymbolCapConfig:
    max_per_symbol: int = 3

_PER_SYMBOL_CFG = PerSymbolCapConfig()


def configure_per_symbol_cap(cfg: PerSymbolCapConfig) -> None:
    global _PER_SYMBOL_CFG
    _PER_SYMBOL_CFG = cfg


def open_count_for_symbol(positions: List[Any], sym: str) -> int:
    n = 0
    for p in positions:
        status = getattr(getattr(p, "status", None), "value", getattr(p, "status", None))
        if status in ("open", "partially_closed", "pending") and str(getattr(p, "underlying", "")).upper() == sym.upper():
            n += 1
    return n


def per_symbol_cap_breach(sym: str, positions: List[Any]) -> Optional[str]:
    n = open_count_for_symbol(positions, sym)
    if n >= _PER_SYMBOL_CFG.max_per_symbol:
        return f"per-symbol cap reached: {n}/{_PER_SYMBOL_CFG.max_per_symbol} open on {sym.upper()}"
    return None


def reset_all_for_tests() -> None:
    _KILL_SWITCH.update({"enabled": False, "reason": "", "set_ts_ms": 0})
    _IDEMPOTENCY_CACHE.clear()
    _RETRY_QUEUE.clear()
    global _DAILY_LOSS_CFG
    _DAILY_LOSS_CFG = DailyLossConfig()
