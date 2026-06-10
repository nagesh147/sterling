"""Paper-trader operational safety — drawdown kill-switch, book flattening,
exclusive run-lock, exactly-once-per-bar guard. All isolated from the live
engine; pure primitives the runner composes.

The load-bearing properties: a tripped breaker takes the account FLAT (no new
risk), the breaker LATCHES (hysteresis, no flapping), only ONE runner mutates
state at a time, and a re-run within the same bar does NO work."""
from __future__ import annotations

import pandas as pd
import pytest

from study.paper_safety import (
    update_kill_switch, apply_kill_switch, run_lock, should_run,
)


# --- drawdown kill-switch -------------------------------------------------
def test_kill_switch_trips_below_threshold():
    """Equity 28% below the high-water-mark trips a 25% breaker."""
    st = update_kill_switch({"peak": 500.0}, 360.0, threshold=0.25, recover=0.10)
    assert st["tripped"] is True
    assert st["drawdown"] == pytest.approx(-0.28)
    assert st["peak"] == 500.0


def test_kill_switch_not_tripped_within_threshold():
    st = update_kill_switch({"peak": 500.0}, 460.0, threshold=0.25, recover=0.10)
    assert st["tripped"] is False
    assert st["drawdown"] == pytest.approx(-0.08)


def test_kill_switch_latches_with_hysteresis():
    """Once tripped it stays tripped through a partial bounce (still inside the
    recover band) and only resets once equity recovers within `recover`."""
    a = update_kill_switch({"peak": 500.0}, 360.0)          # -28% → trip
    assert a["tripped"] is True
    b = update_kill_switch(a, 430.0)                         # -14%: in band → latched
    assert b["tripped"] is True
    c = update_kill_switch(b, 460.0)                         # -8% ≥ -10% → reset
    assert c["tripped"] is False


def test_kill_switch_tracks_high_water_mark():
    """Drawdown is measured from the running peak, not the seed capital."""
    up = update_kill_switch({"peak": 500.0}, 600.0)         # new high
    assert up["peak"] == 600.0 and up["drawdown"] == pytest.approx(0.0)
    down = update_kill_switch(up, 480.0)                     # -20% from 600, not -4% from 500
    assert down["drawdown"] == pytest.approx(-0.20)
    assert down["tripped"] is False                         # -20% > -25%


def test_kill_switch_new_high_resets_latch():
    tripped = update_kill_switch({"peak": 500.0}, 360.0)
    assert tripped["tripped"] is True
    recov = update_kill_switch(tripped, 520.0)              # new high → flat DD → reset
    assert recov["tripped"] is False and recov["peak"] == 520.0


# --- breaker effect on the book ------------------------------------------
def _book():
    return {"realized": {"end": 560.0}, "total_equity": 590.0,
            "open_positions": [{"symbol": "BTCUSD", "weight": 0.4}],
            "n_closed": 12}


def test_apply_kill_switch_flattens_when_tripped():
    """A tripped breaker drops open positions and marks equity realized-only —
    the account carries no new risk."""
    out = apply_kill_switch(_book(), {"tripped": True})
    assert out["open_positions"] == []
    assert out["total_equity"] == pytest.approx(560.0)      # realized only
    assert out["breaker"]["tripped"] is True


def test_apply_kill_switch_passthrough_when_armed():
    out = apply_kill_switch(_book(), {"tripped": False})
    assert len(out["open_positions"]) == 1
    assert out["total_equity"] == pytest.approx(590.0)
    assert out["breaker"]["tripped"] is False


# --- exclusive run-lock ---------------------------------------------------
def test_run_lock_is_exclusive(tmp_path):
    """Only one holder at a time; releasing lets the next acquire."""
    p = str(tmp_path / "run.lock")
    with run_lock(p) as first:
        assert first is True
        with run_lock(p) as second:                         # already held
            assert second is False
    with run_lock(p) as again:                              # released → free
        assert again is True


# --- exactly-once per bar -------------------------------------------------
def test_should_run_only_on_new_closed_bar():
    asof = pd.Timestamp("2026-06-10 08:00")
    assert should_run(None, asof) is True                   # first ever run
    assert should_run({"asof": "2026-06-10 04:00"}, asof) is True   # bar advanced
    assert should_run({"asof": "2026-06-10 08:00"}, asof) is False  # same bar → skip
    assert should_run({"asof": "2026-06-10 08:00"}, asof, force=True) is True
