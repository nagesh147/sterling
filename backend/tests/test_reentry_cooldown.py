"""Re-entry cooldown — stop the algo from churning the same setup.

The May-30 loss cluster was 6 ETH "overbought" shorts at ~2020-2028 within ~2h:
the trail stop exits a trade near breakeven, then minutes later the SAME signal
re-fires (price still near the 4H level) and the algo re-enters — over and over,
each a small loss. The open-position idempotency guard only blocks SIMULTANEOUS
duplicates; nothing stopped rapid SEQUENTIAL re-entry. This cooldown does.
"""
from __future__ import annotations

import types

from app.api.v1.endpoints.sterling_engine import _reentry_cooldown_remaining_min

TAG = "[SCALP-MEAN_REVERSION]"
MIN = 60_000


def _pos(sym="ETHUSD", notes=TAG, paper=True, status="closed",
         direction="short", exit_ms=0):
    return types.SimpleNamespace(
        underlying=sym, notes=notes, is_paper=paper,
        status=types.SimpleNamespace(value=status),
        exit_timestamp_ms=exit_ms,
        sized_trade=types.SimpleNamespace(
            structure=types.SimpleNamespace(
                direction=types.SimpleNamespace(value=direction))),
    )


def _call(positions, now_ms, cooldown_min=45, direction="short"):
    return _reentry_cooldown_remaining_min(
        positions, sym="ETHUSD", strat_tag=TAG, want_paper=True,
        direction=direction, cooldown_min=cooldown_min, now_ms=now_ms)


def test_no_history_no_cooldown():
    assert _call([], now_ms=100 * MIN) == 0.0


def test_recent_same_setup_exit_blocks():
    now = 100 * MIN
    pos = _pos(exit_ms=now - 10 * MIN)            # closed 10 min ago, cooldown 45
    rem = _call([pos], now_ms=now)
    assert 34 < rem <= 35                          # ~35 min left


def test_exit_beyond_cooldown_clears():
    now = 100 * MIN
    pos = _pos(exit_ms=now - 50 * MIN)            # 50 > 45 → clear
    assert _call([pos], now_ms=now) == 0.0


def test_opposite_direction_not_blocked():
    now = 100 * MIN
    pos = _pos(direction="long", exit_ms=now - 5 * MIN)
    assert _call([pos], now_ms=now, direction="short") == 0.0


def test_other_symbol_or_strategy_not_blocked():
    now = 100 * MIN
    assert _call([_pos(sym="BTCUSD", exit_ms=now - 5 * MIN)], now_ms=now) == 0.0
    assert _call([_pos(notes="[SCALP-BREAKOUT]", exit_ms=now - 5 * MIN)], now_ms=now) == 0.0


def test_open_positions_ignored_only_closed_count():
    now = 100 * MIN
    assert _call([_pos(status="open", exit_ms=0)], now_ms=now) == 0.0


def test_zero_cooldown_disables():
    now = 100 * MIN
    assert _call([_pos(exit_ms=now - 1 * MIN)], now_ms=now, cooldown_min=0) == 0.0


def test_uses_most_recent_of_several_exits():
    now = 100 * MIN
    old = _pos(exit_ms=now - 50 * MIN)
    recent = _pos(exit_ms=now - 5 * MIN)
    rem = _call([old, recent], now_ms=now)
    assert 39 < rem <= 40                          # ~40 min left (from the recent one)
