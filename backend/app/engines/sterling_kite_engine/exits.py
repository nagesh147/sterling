"""When a Sterling Kite Engine entry dies, and why. Pure — no I/O, no broker types.

Two independent rules, whichever fires FIRST:

* the RED COUNTER — ``exit_mode`` many SuperTrend lines have flipped against the
  position (plus a fresh counter-arrow for ``three_red_signal``);
* the TRAILING STOP — price traded through the trail.

This lives in the engine package, not in the scanner, because the live scanner and the
backtest replay must answer this question identically. They previously each carried
their own copy of the red-count loop (the backtest's was documented as "identical to
the live ``scanner.is_active`` loop"), which is exactly the kind of duplication that
silently desyncs the moment one side gains a rule the other lacks.
"""
from __future__ import annotations

from typing import Optional, Tuple

from app.engines.common.exit_counter import exit_needs_counter_signal, get_exit_threshold
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig, TrailTarget


def trail_level(r, direction: str, entry_i: int, at_i: int,
                cfg: SterlingKiteEngineConfig) -> float:
    """The trail level to show/enforce for an entry at ``entry_i``, as of bar ``at_i``.

    Default: the tightest still-aligned line (the validated fast trail). With
    ``exit_aligned_trail`` on: the line whose flip is the ``exit_mode``-th red, so the
    stop breach coincides with the red count instead of the tightest line pre-empting
    it. Falls back to the entry bar's ``trail_target`` line when no aligned line remains.
    """
    if getattr(cfg, "exit_aligned_trail", False):
        value = r.trail_value_for_threshold(at_i, get_exit_threshold(cfg.exit_mode))
    else:
        value = r.best_trail_line_value(direction, at_i)
    if value > 0:
        return float(value)
    target: TrailTarget = cfg.trail_target
    return float(r.line(target)[entry_i])


def trail_exit_index(r, direction: str, entry_i: int, last_idx: int,
                     cfg: SterlingKiteEngineConfig) -> Optional[int]:
    """First bar after entry whose price traded through the trail, or None.

    The level tested at bar ``j`` is the one that stood at the CLOSE OF ``j-1`` — the
    only level a live stop could actually have been resting at when bar ``j`` opened.
    Testing bar ``j`` against bar ``j``'s own trail would be lookahead: the SuperTrend
    at ``j`` is computed from ``j``'s own high/low, so the bar that breaks the stop
    would also be the bar that moved it.

    Compares against ``basis_high``/``basis_low`` rather than the raw candle: the ST
    lines are computed on the configured basis (Heikin-Ashi by default), and a raw low
    is not on the same series as ``l_fast``.
    """
    if not getattr(cfg, "price_stop_exit", True):
        return None
    if r.basis_low.size <= last_idx or r.basis_high.size <= last_idx:
        return None  # basis not carried — cannot compare honestly, so do not guess
    for j in range(entry_i + 1, last_idx + 1):
        level = trail_level(r, direction, entry_i, j - 1, cfg)
        if level <= 0:
            continue
        if direction == "long":
            if float(r.basis_low[j]) <= level:
                return j
        elif float(r.basis_high[j]) >= level:
            return j
    return None


def red_count_exit_index(r, direction: str, entry_i: int, last_idx: int,
                         cfg: SterlingKiteEngineConfig, longs, shorts) -> Optional[int]:
    """First bar at/after entry where the red counter satisfies ``exit_mode``, or None."""
    threshold = get_exit_threshold(cfg.exit_mode)
    needs_counter = exit_needs_counter_signal(cfg.exit_mode)
    for j in range(entry_i, last_idx + 1):
        if r.red_line_count(direction, j) < threshold:
            continue
        if not needs_counter:
            return j
        # Reds hit the threshold but a fresh counter-entry arrow is also required.
        if (direction == "long" and shorts[j]) or (direction == "short" and longs[j]):
            return j
    return None


def resolve_exit(r, direction: str, entry_i: int, last_idx: int,
                 cfg: SterlingKiteEngineConfig, longs, shorts) -> Tuple[Optional[int], str]:
    """``(exit_bar_index, reason)`` for an entry at ``entry_i``, or ``(None, "")`` if it
    is still running at ``last_idx``.

    Before the trail was enforced, a position under ``two_red``/``three_red`` could sit
    indefinitely below its own stop while the board reported it running at "0/3 red",
    because the trail was a display value that nothing acted on.
    """
    red_j = red_count_exit_index(r, direction, entry_i, last_idx, cfg, longs, shorts)
    trail_j = trail_exit_index(r, direction, entry_i, last_idx, cfg)
    if red_j is None and trail_j is None:
        return None, ""
    if trail_j is not None and (red_j is None or trail_j <= red_j):
        level = trail_level(r, direction, entry_i, trail_j - 1, cfg)
        side = "≤" if direction == "long" else "≥"
        return trail_j, f"trail breach ({side} {level:.2f})"
    threshold = get_exit_threshold(cfg.exit_mode)
    return red_j, f"red count exit {threshold}/{threshold} ({cfg.exit_mode})"
