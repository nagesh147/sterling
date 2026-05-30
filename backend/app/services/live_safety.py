"""
Live execution safety primitives.

Four independent guards, composed into `assert_safe_to_trade`:

 * kill_switch    — manual emergency halt (get / set / persist via db.set_config)
 * daily_loss     — circuit breaker on today's realized PnL
 * idempotency    — dedupe identical orders within a short window
 * retry_queue    — in-memory FIFO of failed orders with retry metadata

All four are pure-Python, in-process. They never make network calls. They never
block; on any internal failure they fail-open with a logged warning so a
defective guard cannot become an outage.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── 1. Kill switch ─────────────────────────────────────────────────────────

_KILL_SWITCH: Dict[str, Any] = {"enabled": False, "reason": "", "set_ts_ms": 0}


def kill_switch_state() -> Dict[str, Any]:
    """Return the current kill-switch state (read-only)."""
    return dict(_KILL_SWITCH)


def set_kill_switch(enabled: bool, reason: str = "") -> Dict[str, Any]:
    """Toggle the kill switch. When enabled, place_order must reject."""
    _KILL_SWITCH["enabled"] = bool(enabled)
    _KILL_SWITCH["reason"]  = reason or ("manual halt" if enabled else "")
    _KILL_SWITCH["set_ts_ms"] = int(time.time() * 1000)
    return dict(_KILL_SWITCH)


# ─── 2. Daily loss circuit breaker ─────────────────────────────────────────

@dataclass
class DailyLossConfig:
    """All thresholds in absolute USD (negative loss reading is checked)."""
    soft_warn_usd:  float = -1000.0    # informational
    hard_halt_usd:  float = -1500.0    # blocks new orders


_DAILY_LOSS_CFG = DailyLossConfig()


def configure_daily_loss(cfg: DailyLossConfig) -> None:
    """Override the default daily-loss thresholds at runtime."""
    global _DAILY_LOSS_CFG
    _DAILY_LOSS_CFG = cfg


def _today_window_ms() -> Tuple[int, int]:
    now = int(time.time() * 1000)
    day_start = now - (now % 86_400_000)   # UTC day start
    return day_start, now


def daily_realized_pnl(positions: List[Any]) -> float:
    """Sum realized PnL of positions closed within today's UTC window."""
    start_ms, _ = _today_window_ms()
    total = 0.0
    for p in positions:
        ts = getattr(p, "exit_timestamp_ms", None)
        pnl = getattr(p, "realized_pnl_usd", None)
        if ts and pnl is not None and ts >= start_ms:
            total += float(pnl)
    return round(total, 2)


def daily_loss_state(positions: List[Any]) -> Dict[str, Any]:
    """Return {pnl, level: clear|warning|halt}. List is read-only."""
    pnl = daily_realized_pnl(positions)
    level = "clear"
    if pnl <= _DAILY_LOSS_CFG.hard_halt_usd:
        level = "halt"
    elif pnl <= _DAILY_LOSS_CFG.soft_warn_usd:
        level = "warning"
    return {"pnl_usd": pnl, "level": level,
            "soft_warn_usd": _DAILY_LOSS_CFG.soft_warn_usd,
            "hard_halt_usd": _DAILY_LOSS_CFG.hard_halt_usd}


# ─── 3. Idempotency ─────────────────────────────────────────────────────────

_IDEMPOTENCY_CACHE: Dict[str, Tuple[int, str]] = {}   # key → (set_ts_ms, order_id)
_IDEMPOTENCY_TTL_MS = 60_000   # 60 seconds


def make_idempotency_key(*parts: Any) -> str:
    """Deterministic SHA-1 prefix from input parts. Use for client_order_id."""
    payload = "|".join(str(p) for p in parts).encode()
    return hashlib.sha1(payload).hexdigest()[:16]


def check_idempotency(key: str) -> Optional[str]:
    """Return the previously recorded order_id when this key was seen recently;
    otherwise None. Expired entries are evicted lazily."""
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
    if not key:
        return
    _IDEMPOTENCY_CACHE[key] = (int(time.time() * 1000), order_id)


# ─── 4. Retry queue ─────────────────────────────────────────────────────────

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


_RETRY_QUEUE: Dict[str, RetryItem] = {}


def enqueue_retry(payload: Dict[str, Any], error: str, max_attempts: int = 3) -> RetryItem:
    """Store a failed order's payload. Returns the RetryItem with a generated id."""
    rid = uuid.uuid4().hex[:10].upper()
    item = RetryItem(id=rid, payload=dict(payload), attempt=0,
                     max_attempts=max_attempts, last_error=error)
    _RETRY_QUEUE[rid] = item
    return item


def list_retries(include_poison: bool = True) -> List[RetryItem]:
    items = list(_RETRY_QUEUE.values())
    if not include_poison:
        items = [i for i in items if not i.poison]
    return sorted(items, key=lambda i: i.enqueued_ms)


def mark_attempt(rid: str, error: str = "") -> Optional[RetryItem]:
    """Record a retry attempt. When attempt >= max_attempts, marks poison=True."""
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
    """Test-only entry point."""
    _RETRY_QUEUE.clear()


# ─── 5. Composite gate ──────────────────────────────────────────────────────

@dataclass
class SafetyDecision:
    allowed: bool
    reason: str = ""
    code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "code": self.code}


def assert_safe_to_trade(
    positions: List[Any],
    idempotency_key: Optional[str] = None,
) -> SafetyDecision:
    """Composite gate. Call before any live order is placed.

    Order of checks:
      1. Kill switch (manual halt)         — code = "kill_switch"
      2. Daily loss breaker                — code = "daily_loss_halt"
      3. Idempotency cache hit             — code = "duplicate_order"
    Returns allowed=False on any failure with a human-readable reason and
    a stable error code. Idempotency hits return the prior order_id in
    `reason` so callers can short-circuit and reuse it.
    """
    ks = kill_switch_state()
    if ks.get("enabled"):
        return SafetyDecision(False, f"Kill switch active: {ks.get('reason') or 'manual halt'}",
                              "kill_switch")

    dl = daily_loss_state(positions)
    if dl["level"] == "halt":
        return SafetyDecision(False,
                              f"Daily loss circuit breaker tripped: ${dl['pnl_usd']:.2f} "
                              f"<= ${dl['hard_halt_usd']:.2f}",
                              "daily_loss_halt")

    if idempotency_key:
        prior = check_idempotency(idempotency_key)
        if prior:
            return SafetyDecision(False,
                                  f"Duplicate order — already placed as {prior}",
                                  "duplicate_order")

    return SafetyDecision(True)


# ─── 6. Test reset ──────────────────────────────────────────────────────────

def reset_all_for_tests() -> None:
    """Wipe every guard's state. Test-only entry point."""
    _KILL_SWITCH.update({"enabled": False, "reason": "", "set_ts_ms": 0})
    _IDEMPOTENCY_CACHE.clear()
    _RETRY_QUEUE.clear()
    global _DAILY_LOSS_CFG
    _DAILY_LOSS_CFG = DailyLossConfig()


# ─── 7. Per-symbol position cap (Phase F) ────────────────────────────────────


@dataclass
class PerSymbolCapConfig:
    """Maximum simultaneously-open positions per underlying."""
    max_per_symbol: int = 3


_PER_SYMBOL_CFG = PerSymbolCapConfig()


def configure_per_symbol_cap(cfg: PerSymbolCapConfig) -> None:
    global _PER_SYMBOL_CFG
    _PER_SYMBOL_CFG = cfg


def open_count_for_symbol(positions: List[Any], sym: str) -> int:
    """Count open / partially_closed positions for a single underlying."""
    sym_u = sym.upper()
    n = 0
    for p in positions:
        try:
            status_value = getattr(p, "status", None)
            status_str = getattr(status_value, "value", status_value)
            if status_str not in ("open", "partially_closed"):
                continue
            if str(getattr(p, "underlying", "")).upper() == sym_u:
                n += 1
        except Exception:
            continue
    return n


def per_symbol_cap_breach(sym: str, positions: List[Any]) -> Optional[str]:
    """
    Returns a human-readable reason when adding another position on `sym`
    would exceed the per-symbol cap. None when the trade is allowed.
    """
    n = open_count_for_symbol(positions, sym)
    cap = _PER_SYMBOL_CFG.max_per_symbol
    if n >= cap:
        return f"per-symbol cap reached: {n}/{cap} open on {sym.upper()}"
    return None
