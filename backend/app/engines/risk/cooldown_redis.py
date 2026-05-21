"""
Redis-backed cooldown persistence for multi-worker deployments.

Provides cross-worker re-entry cooldown tracking via Redis hash.
TTL = maximum cooldown window for any mode (12 hours = 43200 seconds).

When Redis is unavailable, the parent cooldown.py falls back to in-memory
only — this module is never a hard requirement.
"""
from __future__ import annotations

import os
from typing import Optional

_redis: Optional[object] = None  # Redis client, lazy init
_KEY_PREFIX = "sterling:cooldown"


def _get_redis():
    """Lazily initialize Redis connection. Returns None if unavailable."""
    global _redis
    if _redis is None:
        try:
            import redis as _redis_mod
            _redis = _redis_mod.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", 6379)),
                db=0,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            _redis.ping()
        except Exception:
            _redis = None
    return _redis


def redis_record(
    underlying: str,
    mode: str,
    direction: str,
    exit_ts_ms: int,
    ttl_seconds: int = 43200,
) -> None:
    """
    Persist an exit timestamp to Redis with TTL.

    Args:
        underlying: instrument symbol (e.g. "BTC")
        mode: trading mode (scalping, intraday, swing, positional)
        direction: LONG or SHORT
        exit_ts_ms: exit timestamp in milliseconds
        ttl_seconds: TTL for the key (default 12 hours = longest mode window)
    """
    r = _get_redis()
    if r is None:
        return  # fail-open: in-memory is primary, Redis is enhancement only
    key = f"{_KEY_PREFIX}:{underlying.upper()}:{mode.lower()}:{direction.lower()}"
    try:
        r.setex(key, ttl_seconds, str(int(exit_ts_ms)))
    except Exception:
        pass  # non-critical


def redis_is_blocked(
    underlying: str,
    mode: str,
    direction: str,
    now_ms: int,
    window_ms: int,
) -> bool:
    """
    Check if a cooldown entry exists and is within the window.

    Returns True if the key exists and (now_ms - stored_ts) < window_ms.
    Returns False if key is missing or expired.
    """
    r = _get_redis()
    if r is None:
        return False  # fail-open
    key = f"{_KEY_PREFIX}:{underlying.upper()}:{mode.lower()}:{direction.lower()}"
    try:
        val = r.get(key)
        if val is None:
            return False
        last = int(val)
        return (now_ms - last) < window_ms
    except Exception:
        return False


def redis_is_blocked_cross_mode(
    underlying: str,
    direction: str,
    now_ms: int,
    mode_windows: dict[str, int],
) -> bool:
    """
    Check if any mode for (underlying, direction) is still in cooldown.

    Args:
        underlying: instrument symbol
        direction: LONG or SHORT
        now_ms: current timestamp in milliseconds
        mode_windows: dict of mode -> window_ms for that mode

    Returns True if any mode's cooldown is active.
    """
    r = _get_redis()
    if r is None:
        return False
    u_key = underlying.upper()
    d_key = direction.lower()
    for mode, window_ms in mode_windows.items():
        key = f"{_KEY_PREFIX}:{u_key}:{mode.lower()}:{d_key}"
        try:
            val = r.get(key)
            if val is not None and (now_ms - int(val)) < window_ms:
                return True
        except Exception:
            continue
    return False