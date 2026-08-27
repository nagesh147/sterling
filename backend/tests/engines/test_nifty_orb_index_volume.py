"""Indices carry no traded volume, and the engine must still be able to trade them.

NSE/BSE INDEX candles (NIFTY 50, NIFTY BANK, FINNIFTY, SENSEX) always report
``volume=0`` -- an index has no traded volume of its own. Two gates used to
collapse on that and made an index signal structurally impossible:

* ``vwap()`` divided by total volume and fell back to ``bars[-1].close``. That
  put VWAP exactly *on* the close, so ``close <= vwap`` and ``close >= vwap``
  were both true and every index breakout was rejected at the location gate.
* ``_volume_ratio()`` returns a neutral 1.0 with no baseline, which sits below
  the 1.15 default and failed the participation gate.

A replay over seven sessions of real Kite data confirmed the effect: 0 signals
on all four indices against 277 on the fourteen single stocks in the same
universe. These tests pin the repair, and pin the stock path so the volume gate
is not quietly weakened for instruments that do report volume.

The fallback matches ``app/engines/navigator/avwap.py``, which already resolved
the same problem the same way.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import (
    Bar,
    StrategyConfig,
    generate_signal,
    has_traded_volume,
    vwap,
)

IST = timezone(timedelta(hours=5, minutes=30))
SESSION_OPEN = datetime(2026, 8, 18, 9, 15, tzinfo=IST)
OR_HIGH, OR_LOW = 24012.0, 23988.0


def _ts(index: int) -> datetime:
    return SESSION_OPEN + timedelta(minutes=5 * index)


def _bar(index: int, open_: float, close: float, volume: float, *, pad: float = 4.0) -> Bar:
    return Bar(_ts(index), open_, max(open_, close) + pad, min(open_, close) - pad, close, volume)


def index_session(direction: str = "LONG", *, bars: int = 30) -> list[Bar]:
    """A clean ORB day on an *index*: identical shape, every volume zero.

    The drift leg sits below the opening range so the session's mean typical
    price stays under the breakout close -- the location gate has to be
    genuinely satisfied, not merely un-evaluated.
    """
    rows = [Bar(_ts(i), 24000.0, OR_HIGH, OR_LOW, 24000.0, 0.0) for i in range(3)]
    price = 24000.0
    for i in range(3, bars):
        if i < bars - 5:
            close = price + (2.0 if i % 2 else -2.0)
            rows.append(_bar(i, price, close, 0.0, pad=3.0))
        else:
            close = price + (18.0 if direction == "LONG" else -18.0)
            rows.append(_bar(i, price, close, 0.0))
        price = close
    return rows


# ── the VWAP line itself ──────────────────────────────────────────────────────

def test_zero_volume_vwap_is_the_mean_typical_price_not_the_last_close():
    """The old fallback returned ``bars[-1].close``, which pinned VWAP to price."""
    bars = [
        Bar(_ts(0), 100.0, 110.0, 90.0, 100.0, 0.0),   # typical 100
        Bar(_ts(1), 100.0, 130.0, 110.0, 120.0, 0.0),  # typical 120
        Bar(_ts(2), 120.0, 150.0, 130.0, 140.0, 0.0),  # typical 140
    ]
    assert vwap(bars) == pytest.approx(120.0)
    assert vwap(bars) != bars[-1].close


def test_zero_volume_vwap_equals_the_equal_weighted_volume_case():
    """Unweighted mean *is* the constant-volume case; the two must agree."""
    shape = [(100.0, 110.0, 90.0, 100.0), (100.0, 130.0, 110.0, 120.0), (120.0, 150.0, 130.0, 140.0)]
    zero = [Bar(_ts(i), o, h, l, c, 0.0) for i, (o, h, l, c) in enumerate(shape)]
    flat = [Bar(_ts(i), o, h, l, c, 500.0) for i, (o, h, l, c) in enumerate(shape)]
    assert vwap(zero) == pytest.approx(vwap(flat))


def test_volume_weighting_still_applies_when_the_feed_reports_volume():
    """The repair must not turn a real VWAP into a TWAP for stocks."""
    bars = [
        Bar(_ts(0), 100.0, 110.0, 90.0, 100.0, 1.0),     # typical 100, tiny weight
        Bar(_ts(1), 100.0, 130.0, 110.0, 120.0, 999.0),  # typical 120, dominates
    ]
    assert vwap(bars) == pytest.approx(120.0, abs=0.1)
    assert vwap(bars) != pytest.approx(110.0)  # the unweighted mean


def test_has_traded_volume_separates_an_index_from_a_stock():
    assert has_traded_volume(index_session()) is False
    assert has_traded_volume([_bar(0, 100.0, 101.0, 250.0)]) is True


# ── the gates that used to be unpassable ──────────────────────────────────────

def test_index_long_breakout_produces_a_signal():
    """The whole point: an index can now fire."""
    signal = generate_signal(index_session("LONG"), StrategyConfig(underlying="NIFTY"))
    assert signal.direction == "LONG", signal.reason
    assert signal.reason.endswith("(no volume feed)")


def test_index_short_breakout_produces_a_signal():
    signal = generate_signal(index_session("SHORT"), StrategyConfig(underlying="NIFTY"))
    assert signal.direction == "SHORT", signal.reason


def test_index_signal_is_not_rejected_on_the_vwap_location_gate():
    """The exact regression: VWAP sat on the close, so both sides were 'wrong'."""
    signal = generate_signal(index_session("LONG"), StrategyConfig(underlying="NIFTY"))
    assert "VWAP" not in signal.reason or signal.direction != "NONE"
    assert signal.vwap != pytest.approx(index_session("LONG")[-1].close)


def test_index_signal_reports_a_time_weighted_basis():
    """A TWAP line must never be labelled as a VWAP -- they are different lines."""
    signal = generate_signal(index_session("LONG"), StrategyConfig(underlying="NIFTY"))
    assert signal.vwap_basis == "time"
    assert signal.volume_confirmed is False
    assert signal.to_dict()["vwap_basis"] == "time"


# ── the volume gate stays real where volume is real ───────────────────────────

def test_stock_signal_still_requires_volume_confirmation():
    """Same bars, but the feed reports volume -- the gate must bite again."""
    from tests.engines.test_nifty_orb_options import orb_session

    thin = [Bar(b.timestamp, b.open, b.high, b.low, b.close, 1000.0) for b in orb_session("LONG")]
    signal = generate_signal(thin, StrategyConfig())
    assert signal.direction == "NONE"
    assert signal.reason == "volume below confirmation threshold"


def test_stock_signal_reports_a_volume_weighted_basis():
    from tests.engines.test_nifty_orb_options import orb_session

    signal = generate_signal(orb_session("LONG"), StrategyConfig())
    assert signal.direction == "LONG", signal.reason
    assert signal.vwap_basis == "volume"
    assert signal.volume_confirmed is True


def test_an_unconfirmed_index_signal_scores_below_its_volume_confirmed_twin():
    """Confidence must not award credit for a confirmation that never happened."""
    from tests.engines.test_nifty_orb_options import orb_session

    index = generate_signal(index_session("LONG"), StrategyConfig(underlying="NIFTY"))
    stock = generate_signal(orb_session("LONG"), StrategyConfig())
    assert index.direction == stock.direction == "LONG"
    assert index.confidence < stock.confidence
