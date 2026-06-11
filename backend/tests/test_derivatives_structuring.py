"""Derivatives structuring revamp — futures stop sanitization + delta options."""
from __future__ import annotations

import pytest

from app.engines.derivatives.selector import _futures_candidate, _sane_futures_stop
from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import MarketContext, SignalContext


def test_sane_stop_keeps_valid_stop():
    assert _sane_futures_stop("long", entry=100.0, stop=95.0, atr=2.0) == 95.0
    assert _sane_futures_stop("short", entry=100.0, stop=105.0, atr=2.0) == 105.0


def test_sane_stop_atr_fallback_when_stop_equals_entry():
    s = _sane_futures_stop("long", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(97.0)
    s = _sane_futures_stop("short", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(103.0)


def test_sane_stop_atr_fallback_when_wrong_side_or_missing():
    assert _sane_futures_stop("long", entry=100.0, stop=110.0, atr=2.0, k=1.5) == pytest.approx(97.0)
    assert _sane_futures_stop("short", entry=100.0, stop=None, atr=2.0, k=1.5) == pytest.approx(103.0)


def test_sane_stop_none_when_no_atr_and_bad_stop():
    assert _sane_futures_stop("long", entry=100.0, stop=100.0, atr=0.0) is None
    assert _sane_futures_stop("long", entry=100.0, stop=None, atr=0.0) is None


def _mkt(spot=62000.0):
    return MarketContext(spot=spot, underlying="BTC", funding_8h_pct=0.0001,
                         portfolio_value=500.0)


def _sig(direction="short", entry=62000.0, stop=62000.0, atr=600.0, tp=None):
    # stop==entry reproduces the collector's zero-distance fallback that DEFERed.
    return SignalContext(strategy="directional", underlying="BTC",
                         direction=direction, entry=entry, stop_loss=stop,
                         take_profit=tp, atr=atr, rr_target=2.0, signal_score=70.0,
                         signal_strength="SIGNAL", presized=False)


def test_futures_candidate_built_despite_zero_distance_stop():
    cand = _futures_candidate(signal=_sig(), market=_mkt(), profile=get_profile("directional"))
    assert cand is not None
    assert cand.instrument_type == "futures"
    assert cand.direction == "short"
    assert cand.stop_loss is not None and cand.stop_loss > cand.entry_price  # short stop above
    assert cand.contracts > 0


def test_futures_candidate_none_when_no_atr_and_bad_stop():
    cand = _futures_candidate(signal=_sig(atr=0.0), market=_mkt(),
                              profile=get_profile("directional"))
    assert cand is None


from app.schemas.market import OptionSummary
from app.engines.derivatives_native.structures import build_delta_debit_vertical


def _opt(strike, otype, delta, dte=21, bid=100.0, ask=104.0, oi=50.0, vol=20.0):
    mid = (bid + ask) / 2
    return OptionSummary(
        instrument_name=f"BTC-{otype}-{int(strike)}", underlying="BTC",
        strike=strike, expiry_date="2026-07-01", dte=dte, option_type=otype,
        bid=bid, ask=ask, mark_price=mid, mid_price=mid, mark_iv=0.5,
        delta=delta, open_interest=oi, volume_24h=vol, last_updated_ms=0,
        gamma=0.0001, vega=10.0, theta=-5.0)


def _put_chain():
    return [_opt(60000, "put", -0.30), _opt(58000, "put", -0.55),
            _opt(56000, "put", -0.70), _opt(54000, "put", -0.20)]


def test_delta_debit_vertical_short_picks_target_delta_long_leg():
    s = build_delta_debit_vertical(
        chain=_put_chain(), spot=58000.0, direction="short",
        target_delta=0.55, width_delta=0.25, dte_min=7, dte_max=45,
        nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is not None
    assert s.structure_type == "debit_vertical"
    long_leg = next(l for l in s.legs if l.side == "buy")
    short_leg = next(l for l in s.legs if l.side == "sell")
    assert long_leg.strike == 58000
    assert abs(short_leg.delta) < abs(long_leg.delta)
    assert s.contracts > 0


def test_delta_debit_vertical_defers_on_wide_spread():
    wide = [_opt(58000, "put", -0.55, bid=50.0, ask=150.0),
            _opt(56000, "put", -0.30, bid=50.0, ask=150.0)]
    s = build_delta_debit_vertical(
        chain=wide, spot=58000.0, direction="short", target_delta=0.55,
        width_delta=0.25, dte_min=7, dte_max=45, nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is None


def test_delta_debit_vertical_defers_on_low_oi():
    thin = [_opt(58000, "put", -0.55, oi=0.0), _opt(56000, "put", -0.30, oi=0.0)]
    s = build_delta_debit_vertical(
        chain=thin, spot=58000.0, direction="short", target_delta=0.55,
        width_delta=0.25, dte_min=7, dte_max=45, nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is None


from app.engines.derivatives_native.engine import _defined_risk_candidate


def test_defined_risk_uses_delta_targeting_for_directional():
    prof = get_profile("directional")   # target_delta 0.60, dte 14-45
    cand = _defined_risk_candidate(
        signal=_sig(direction="short"), market=_mkt(spot=58000.0),
        profile=prof,
        chain=[_opt(58000, "put", -0.60, bid=300.0, ask=304.0),
               _opt(55000, "put", -0.35, bid=100.0, ask=104.0)],
        sources={"directional_options"})
    assert cand is not None
    assert cand.instrument_type == "options"
    assert cand.structure is not None and cand.structure.structure_type == "debit_vertical"
    assert cand.direction == "short"
