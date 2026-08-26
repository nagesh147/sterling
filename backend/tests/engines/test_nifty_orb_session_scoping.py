"""Session scoping of the ORB indicators.

VWAP and the opening range were session-scoped from the start; ATR, the volume
baseline and the regime were not. Because the entry window opens at 09:30 and the
lookbacks are 14-20 bars, that meant for roughly the first eighty minutes of
*every* session the strategy's own filters were computed from yesterday's data --
and the result depended on how many bars the caller happened to fetch.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import (
    Bar,
    StrategyConfig,
    _regime,
    _volume_ratio,
    atr,
    generate_signal,
    vwap,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _session(day: int, base: float, *, volume: float, bars: int, span: float = 3.0) -> list[Bar]:
    rows, price = [], base
    for i in range(bars):
        ts = datetime(2026, 8, day, 9, 15, tzinfo=IST) + timedelta(minutes=5 * i)
        close = price + (2.0 if i % 2 else -2.0)
        rows.append(Bar(ts, price, max(price, close) + span, min(price, close) - span, close, volume))
        price = close
    return rows


# A full prior session, then a 500-point gap up and only four bars of today.
PRIOR = _session(17, 24000.0, volume=8000, bars=75)
TODAY = _session(18, 24500.0, volume=1000, bars=5)


# --------------------------------------------------------------------------
# ATR: the overnight gap is not an intraday range
# --------------------------------------------------------------------------

def test_the_overnight_gap_is_not_counted_as_an_intraday_range():
    """A 500-point gap once turned a real ATR of 8 into 43.5."""
    assert atr(TODAY, 14) == pytest.approx(8.0)
    assert atr(PRIOR + TODAY, 14) == pytest.approx(atr(TODAY, 14))


@pytest.mark.parametrize("fetched", [5, 20, 40, 80, 240])
def test_atr_does_not_depend_on_how_many_bars_the_caller_fetched(fetched):
    """Kite fetches 240, TrueData 200 -- the signal must not differ because of it."""
    assert atr((PRIOR + TODAY)[-fetched:], 14) == pytest.approx(8.0)


def test_the_breakout_threshold_is_therefore_stable():
    cfg = StrategyConfig()
    threshold = cfg.min_breakout_atr * atr(PRIOR + TODAY, cfg.atr_period)
    assert threshold == pytest.approx(1.2)          # not 6.5


def test_within_one_session_true_range_still_spans_the_previous_close():
    """The gap rule must not flatten intraday ranges into bare high-low."""
    gappy = [
        Bar(datetime(2026, 8, 18, 9, 15, tzinfo=IST), 100, 101, 99, 100, 1000),
        Bar(datetime(2026, 8, 18, 9, 20, tzinfo=IST), 120, 121, 119, 120, 1000),
    ]
    # high 121 vs previous close 100 -> 21, far wider than the 2-point bar range.
    assert atr(gappy, 14) == pytest.approx(21.0)


def test_atr_needs_at_least_two_bars():
    assert atr(TODAY[:1], 14) == 0.0
    assert atr([], 14) == 0.0


# --------------------------------------------------------------------------
# volume: the baseline belongs to today
# --------------------------------------------------------------------------

def test_volume_is_measured_against_todays_baseline_not_yesterdays():
    """Against a heavy prior session the ratio was 0.15 versus a 1.15 threshold."""
    assert _volume_ratio(PRIOR + TODAY) == pytest.approx(1.0)
    assert _volume_ratio(PRIOR + TODAY) == pytest.approx(_volume_ratio(TODAY))


def test_a_genuine_volume_expansion_is_still_detected():
    session = _session(18, 24000.0, volume=1000, bars=25)
    spike = session[:-1] + [Bar(session[-1].timestamp, session[-1].open, session[-1].high,
                                session[-1].low, session[-1].close, 3000)]
    assert _volume_ratio(spike) == pytest.approx(3.0)


def test_no_same_session_baseline_is_neutral_and_fails_the_gate():
    """Neutral 1.0 is below the 1.15 default, so the first bar cannot trade."""
    first_bar_only = [TODAY[0]]
    assert _volume_ratio(first_bar_only) == pytest.approx(1.0)
    assert _volume_ratio(first_bar_only) < StrategyConfig().volume_multiplier


# --------------------------------------------------------------------------
# regime: today's character, not yesterday's
# --------------------------------------------------------------------------

def test_regime_is_computed_from_the_current_session_only():
    cfg = StrategyConfig()
    combined = PRIOR + TODAY
    a = atr(combined, cfg.atr_period)
    assert _regime(TODAY, cfg, vwap(TODAY), a) == _regime(TODAY, cfg, vwap(TODAY), a)
    # Too few bars in today's session is UNKNOWN -- fail-closed, not yesterday's regime.
    assert _regime(TODAY, cfg, vwap(TODAY), a) == "UNKNOWN"


def test_a_thin_session_produces_no_signal_rather_than_a_stale_one():
    signal = generate_signal(PRIOR + TODAY, StrategyConfig(entry_start="09:15", entry_end="15:00"))
    assert signal.direction == "NONE"
    assert signal.regime == "UNKNOWN"


def test_the_opening_range_was_already_session_scoped_and_still_is():
    from app.engines.nifty_orb_options import opening_range
    assert opening_range(PRIOR + TODAY, 15) == opening_range(TODAY, 15)
