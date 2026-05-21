"""
Re-entry cooldown engine.

Prevents same-(underlying, mode, direction) re-entry for N minutes after exit.
Pure in-memory; no I/O. Orchestrator calls is_blocked() before evaluating
candidates; positions endpoint calls record_exit() on close.

Keying on (underlying, mode, direction) — not just underlying — fixes the
"scalp leak" symptom: a scalping exit must not block a swing entry, and
vice-versa.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

# Map of (underlying, mode, direction) → exit_timestamp_ms
_LAST_EXITS: Dict[Tuple[str, str, str], int] = {}


@dataclass(frozen=True)
class CooldownConfig:
    """
    Per-mode cooldown windows, in minutes. Pulled from MODES on the caller side.

    Scalping bumped from 5 -> 15 min: 5 min is shorter than a 5m candle so
    a fresh exit could be followed immediately by a re-entry on the same
    bar's noise, compounding cost drag.
    """
    scalping_min:    int = 15     # 15 min (was 5)
    intraday_min:    int = 30     # 30 min
    swing_min:       int = 240    # 4 hours
    positional_min:  int = 720    # 12 hours
    default_min:     int = 60     # safety fallback for unknown modes

    def for_mode(self, mode: str) -> int:
        """Returns the cooldown window in minutes for the given mode name."""
        return {
            "scalping":   self.scalping_min,
            "intraday":   self.intraday_min,
            "swing":      self.swing_min,
            "positional": self.positional_min,
        }.get(mode.lower(), self.default_min)


def _key(underlying: str, mode: str, direction: str) -> Tuple[str, str, str]:
    """Normalised composite key. Case-insensitive on all axes."""
    return (underlying.upper(), mode.lower(), direction.lower())


def record_exit(underlying: str, mode: str, direction: str, exit_ts_ms: int) -> None:
    """Record an exit timestamp to in-memory dict (primary) and Redis (cross-worker).

    Redis is non-critical — if it fails, in-memory remains the source of truth.
    """
    key = _key(underlying, mode, direction)
    _LAST_EXITS[key] = int(exit_ts_ms)
    # Persist to Redis for cross-worker dedup
    try:
        from app.engines.risk.cooldown_redis import redis_record
        cfg = CooldownConfig()
        ttl = cfg.for_mode(mode) * 60
        redis_record(underlying, mode, direction, exit_ts_ms, ttl)
    except Exception:
        pass


def is_blocked(
    underlying: str,
    mode: str,
    direction: str,
    now_ms: int,
    config: CooldownConfig | None = None,
) -> bool:
    """
    Returns True iff a recent exit on the same (underlying, mode, direction)
    falls inside the mode's cooldown window.

    Primary: in-memory dict. Fallback: Redis (for cross-worker dedup).
    Returns False when no prior exit is recorded.
    """
    cfg = config or CooldownConfig()
    key = _key(underlying, mode, direction)
    # Primary: in-memory check
    last = _LAST_EXITS.get(key)
    if last is not None:
        window_ms = cfg.for_mode(mode) * 60 * 1000
        if (now_ms - last) < window_ms:
            return True
    # Fallback: cross-worker Redis check
    try:
        from app.engines.risk.cooldown_redis import redis_is_blocked
        window_ms = cfg.for_mode(mode) * 60 * 1000
        if redis_is_blocked(underlying, mode, direction, now_ms, window_ms):
            return True
    except Exception:
        pass
    return False


def remaining_ms(
    underlying: str,
    mode: str,
    direction: str,
    now_ms: int,
    config: CooldownConfig | None = None,
) -> int:
    """Milliseconds left in the cooldown. Zero when not blocked."""
    cfg = config or CooldownConfig()
    last = _LAST_EXITS.get(_key(underlying, mode, direction))
    if last is None:
        return 0
    window_ms = cfg.for_mode(mode) * 60 * 1000
    elapsed = now_ms - last
    return max(0, window_ms - elapsed)


def clear() -> None:
    """Reset all cooldown state. Test-only entry point."""
    _LAST_EXITS.clear()


def is_blocked_cross_mode(
    underlying: str,
    direction: str,
    now_ms: int,
    config: CooldownConfig | None = None,
) -> bool:
    """
    Cross-mode dedup: True iff any mode for (underlying, direction) is still
    in its cooldown window. A scalp-long and a swing-long on the same symbol
    at the same time are not "two trades" — they are one correlated bigger
    trade, so any mode's recent exit blocks all modes from re-entering same
    direction until the longest applicable window elapses.

    Checks both in-memory (primary) and Redis (cross-worker).
    """
    cfg = config or CooldownConfig()
    u_key = underlying.upper()
    d_key = direction.lower()
    # Primary: in-memory scan
    for (u, m, d), last in _LAST_EXITS.items():
        if u != u_key or d != d_key:
            continue
        window_ms = cfg.for_mode(m) * 60 * 1000
        if (now_ms - last) < window_ms:
            return True
    # Fallback: cross-worker Redis check
    try:
        from app.engines.risk.cooldown_redis import redis_is_blocked_cross_mode as _redis_xmode
        mode_windows = {
            "scalping": cfg.scalping_min * 60 * 1000,
            "intraday": cfg.intraday_min * 60 * 1000,
            "swing": cfg.swing_min * 60 * 1000,
            "positional": cfg.positional_min * 60 * 1000,
        }
        if _redis_xmode(underlying, direction, now_ms, mode_windows):
            return True
    except Exception:
        pass
    return False
