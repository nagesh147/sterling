"""
Sterling v4 Phase 4 — Cross-track risk budgeting.

When more than one Track fires on the same instrument simultaneously the
naive policy would size each at the full per-trade cap, doubling exposure.
This module is the chokepoint that prevents that: it tracks per-instrument
"track slots used" and applies a sizing multiplier when a second track
fires while the first is still in-trade.

Rules:
  * Single track active → 1.0× sizing (no change).
  * Second track fires on the same instrument while a first track's
    position is still open → 0.5× sizing on the second entry.
  * Third concurrent track → 0.25× (defensive; in practice we run at most
    2 tracks per (asset, profile) so this only matters if the router is
    misconfigured).
  * When a track's position closes, its slot frees and subsequent entries
    return to 1.0× sizing.

State is in-process — no persistence. Multi-process / restart resets the
slot table; the caller is expected to re-derive slot occupancy from the
open-positions table (paper_store / live broker) on startup.

The OrderRouter (`services/execution/order_router.py`) is where this hooks
in for live trading; backtests can call `record_open` / `record_close`
directly from `_replay_profile` if and when they evaluate multiple tracks
in parallel on the same instrument (Phase 4 leaves this opt-in).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional, Set, Tuple


# Module-level state. Wrapped behind functions so tests can reset it.
_LOCK = Lock()
# Map: (asset, profile_key) → set of active track names with open positions.
_ACTIVE_SLOTS: Dict[Tuple[str, str], Set[str]] = {}


def _key(asset: str, profile_key: str) -> Tuple[str, str]:
    return (asset.upper(), profile_key)


def record_open(asset: str, profile_key: str, track: str) -> None:
    """Mark a track as having an open position on this (asset, profile)."""
    with _LOCK:
        _ACTIVE_SLOTS.setdefault(_key(asset, profile_key), set()).add(track)


def record_close(asset: str, profile_key: str, track: str) -> None:
    """Release a track slot. Idempotent — releasing a non-active track is a no-op."""
    with _LOCK:
        k = _key(asset, profile_key)
        s = _ACTIVE_SLOTS.get(k)
        if s and track in s:
            s.discard(track)
            if not s:
                _ACTIVE_SLOTS.pop(k, None)


def active_tracks(asset: str, profile_key: str) -> Set[str]:
    """Snapshot of currently-active tracks on (asset, profile)."""
    with _LOCK:
        return set(_ACTIVE_SLOTS.get(_key(asset, profile_key), set()))


def size_multiplier(asset: str, profile_key: str, track: str) -> float:
    """Return the size multiplier this new track entry should receive.

    Implementation matches the docstring rules:
      0 already-active → 1.0×
      1 already-active (other track) → 0.5×
      2 already-active → 0.25×
      ≥3 already-active → 0.125×
    Always ≤ 1.0; never negative.
    """
    with _LOCK:
        s = _ACTIVE_SLOTS.get(_key(asset, profile_key), set())
        others = {t for t in s if t != track}
    n_others = len(others)
    if n_others <= 0:
        return 1.0
    return max(0.125, 0.5 ** n_others)


def reset() -> None:
    """Wipe the slot table. Test fixtures only."""
    with _LOCK:
        _ACTIVE_SLOTS.clear()


def snapshot() -> Dict[str, List[str]]:
    """Serialisable snapshot for /healthz, logging, or debug UI."""
    with _LOCK:
        return {f"{a}/{p}": sorted(tracks) for (a, p), tracks in _ACTIVE_SLOTS.items()}
