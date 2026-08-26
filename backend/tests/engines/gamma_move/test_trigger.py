"""The entry rule, and the two data hazards that would silently break it."""
from __future__ import annotations

import pytest

from app.engines.gamma_move import GammaMoveConfig, evaluate, evaluate_bar, slice_session
from tests.engines.gamma_move.conftest import bar, quiet_session

CFG = GammaMoveConfig()


def triggering_session():
    """24 quiet bars, then one where all three conditions hold."""
    return quiet_session() + [bar(0, 24, oi=96_000, volume=5_000, close=53.0)]


def test_all_three_conditions_fire():
    m = evaluate(triggering_session(), CFG)
    assert m is not None and m.triggered
    assert m.oi_drop_pct == pytest.approx(4.0)
    assert m.volume_ratio == pytest.approx(5.0)
    assert m.price_gain_pct == pytest.approx(6.0)


@pytest.mark.parametrize("kw,missing", [
    (dict(oi=100_000), "open interest is not unwinding"),   # OI flat
    (dict(volume=1_000), "volume is not abnormal"),         # volume normal
    (dict(close=50.0), "premium is not rising"),            # price flat
])
def test_each_condition_failing_alone_blocks_and_says_which(kw, missing):
    """Three ways to not have a setup, and the row must distinguish them."""
    last = dict(oi=96_000, volume=5_000, close=53.0)
    last.update(kw)
    m = evaluate(quiet_session() + [bar(0, 24, **last)], CFG)
    assert m is not None and not m.triggered
    assert missing in (m.shortfall() or "")


def test_phantom_unwind_across_a_session_boundary_is_refused():
    """The same numbers, straddling midnight, must NOT fire.

    Measured on the calibration sample: >=20% "unwinds" appear at 0.57% of
    session boundaries against 0.11% within a session. Without this guard the
    engine fires at the first bar of every single trading day.
    """
    across = quiet_session(0, 25) + [bar(1, 0, oi=96_000, volume=5_000, close=53.0)]
    assert evaluate(across, CFG) is None


def test_slice_session_keeps_one_day():
    series = quiet_session(0, 25) + quiet_session(1, 10)
    assert len(slice_session(series)) == 10


def test_zero_prior_open_interest_is_refused_not_infinite():
    series = quiet_session(0, 24, oi=0) + [bar(0, 24, oi=0, volume=5_000, close=53.0)]
    assert evaluate_bar(series, len(series) - 1, CFG) is None


def test_too_little_history_returns_none_not_a_clean_miss():
    """None means unjudgeable. A caller must be able to tell a quiet contract
    from a broken feed, so this may not come back as metrics-all-false."""
    assert evaluate(quiet_session(0, 3), CFG) is None


def test_volume_baseline_reaches_across_sessions():
    """A within-session-only baseline is undefined until 13:15, which is after
    most of the session this strategy cares about."""
    series = quiet_session(0, 25) + [bar(1, i) for i in range(1)] \
        + [bar(1, 1, oi=96_000, volume=5_000, close=53.0)]
    m = evaluate(series, CFG)
    assert m is not None and m.triggered


def test_confirm_bars_requires_consecutive_qualifying_bars():
    cfg = GammaMoveConfig(confirm_bars=2)
    one = quiet_session() + [bar(0, 24, oi=96_000, volume=5_000, close=53.0)]
    m = evaluate(one, cfg)
    assert m is not None and not m.triggered and m.bars_confirmed == 1

    two = quiet_session(0, 23) + [
        bar(0, 23, oi=96_000, volume=5_000, close=53.0),
        bar(0, 24, oi=92_000, volume=6_000, close=56.5),
    ]
    m2 = evaluate(two, cfg)
    assert m2 is not None and m2.triggered and m2.bars_confirmed == 2
