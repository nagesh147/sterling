"""Operational safety for the paper trader — isolated, pure primitives.

Four concerns the live-data runner needs but the backtest never did:

  * `update_kill_switch` — a drawdown breaker with hysteresis. Trips when equity
    falls `threshold` below the high-water-mark; auto-resets only after it
    recovers within `recover` of the peak. Latching prevents flap.
  * `apply_kill_switch` — a tripped breaker takes the book FLAT (open positions
    dropped, equity realized-only): no new risk while in drawdown.
  * `run_lock` — an exclusive non-blocking file lock so exactly one runner
    mutates the persisted account at a time.
  * `should_run` — exactly-once-per-bar: skip work unless a new bar has closed
    since the last persisted run (cron may fire far more often than 4h).

None of this touches the live SterlingEngine; it guards the research/paper book.
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager

import pandas as pd


def update_kill_switch(state: dict, equity: float, *, threshold: float = 0.25,
                       recover: float = 0.10, capital: float = 500.0) -> dict:
    """Advance the drawdown kill-switch by one observation.

    `state` is the prior breaker dict (or {} on first run). Returns the new
    breaker state {peak, drawdown, tripped, threshold, recover}:

      * peak     — high-water-mark equity (monotonic across runs)
      * drawdown — (equity - peak) / peak  (≤ 0)
      * tripped  — True once drawdown ≤ -threshold; stays True (latched) until
                   drawdown recovers to ≥ -recover (hysteresis band prevents
                   flapping on a partial bounce).

    While tripped the runner must open no new positions (see apply_kill_switch).
    """
    peak = max(float(state.get("peak", capital)), float(equity))
    drawdown = (equity - peak) / peak if peak > 0 else 0.0
    prior = bool(state.get("tripped", False))
    if drawdown <= -threshold:
        tripped = True
    elif prior and drawdown >= -recover:
        tripped = False                 # recovered within the band → reset
    else:
        tripped = prior                 # latch the prior decision inside the band
    return {"peak": peak, "drawdown": drawdown, "tripped": tripped,
            "threshold": threshold, "recover": recover}


def apply_kill_switch(book: dict, breaker: dict) -> dict:
    """Project the breaker onto the paper book. Armed → passthrough (records the
    breaker). Tripped → the account goes flat: open positions dropped and total
    equity collapses to realized-only (no live MTM exposure)."""
    if not breaker.get("tripped"):
        return {**book, "breaker": breaker}
    return {**book, "open_positions": [], "breaker": breaker,
            "total_equity": float(book["realized"]["end"])}


@contextmanager
def run_lock(path: str):
    """Exclusive, non-blocking file lock. Yields True if acquired, False if
    another runner already holds it — so a scheduler can never run two copies
    mutating the same persisted state concurrently."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    f = open(path, "w")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


def should_run(prior_state, asof, *, force: bool = False) -> bool:
    """Exactly-once-per-bar guard: True only when a new bar has closed since the
    last persisted run. `asof` is the latest CLOSED-bar timestamp. `force`
    overrides (manual re-run)."""
    if force or prior_state is None:
        return True
    last = prior_state.get("asof")
    return last is None or pd.Timestamp(asof) > pd.Timestamp(last)
