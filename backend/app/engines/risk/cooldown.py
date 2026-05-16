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
    """Per-mode cooldown windows, in minutes. Pulled from MODES on the caller side."""
    scalping_min:    int = 5      # 5 min
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
    """Record an exit timestamp. Called by positions endpoint on close."""
    _LAST_EXITS[_key(underlying, mode, direction)] = int(exit_ts_ms)


def is_blocked(
    underlying: str,
    mode: str,
    direction: str,
    now_ms: int,
    config: CooldownConfig | None = None,
) -> bool:
    """
    Returns True iff a recent exit on the same (underlying, mode, direction)
    falls inside the mode's cooldown window. Returns False when no prior exit
    is recorded.
    """
    cfg = config or CooldownConfig()
    last = _LAST_EXITS.get(_key(underlying, mode, direction))
    if last is None:
        return False
    window_ms = cfg.for_mode(mode) * 60 * 1000
    return (now_ms - last) < window_ms


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
