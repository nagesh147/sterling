import pytest
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult, PolicyResult,
    MacroRegime, ExecMode, IVRBand, Direction,
)
from app.engines.directional.scoring import score_structure


def _make_leg(oi=200.0, spread_pct=0.02, dte=30) -> CandidateContract:
    return CandidateContract(
        instrument_name="BTC-31MAY24-30000-C",
        underlying="BTC",
        strike=30000.0,
        expiry_date="2024-05-31",
        dte=dte,
        option_type="call",
        bid=100.0,
        ask=102.0,
        mark_price=101.0,
        mid_price=101.0,
        mark_iv=0.6,
        delta=0.5,
        open_interest=oi,
        volume_24h=50.0,
        spread_pct=spread_pct,
        health_score=90.0,
        healthy=True,
    )


def _make_structure(oi=200.0, spread_pct=0.02, dte=30) -> TradeStructure:
    leg = _make_leg(oi=oi, spread_pct=spread_pct, dte=dte)
    return TradeStructure(
        structure_type="bull_call_spread",
        direction=Direction.LONG,
        legs=[leg],
        max_loss=200.0,
        max_gain=800.0,
        net_premium=200.0,
        risk_reward=4.0,
        score=0.0,
        score_breakdown={},
    )


def _make_regime() -> RegimeResult:
    return RegimeResult(
        macro_regime=MacroRegime.BULL_TREND,
        ema50=30000.0, close_4h=31000.0, score=15.0,
        atr_percentile=55.0, adx=30.0,
    )


def _make_signal() -> SignalResult:
    return SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=True, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[29000.0, 0.0, 0.0],
        close_1h=31000.0, score_long=100.0, score_short=0.0,
        signal_strength="STRONG", signal_score=16.0,
    )


def _make_exec() -> ExecTimingResult:
    return ExecTimingResult(mode=ExecMode.PULLBACK, confidence=0.9, reason="test", exec_score=14.0)


def _make_policy() -> PolicyResult:
    return PolicyResult(
        allowed_structures=["bull_call_spread"],
        ivr=30.0, ivr_band=IVRBand.NORMAL,
        preferred_dte_min=10, preferred_dte_max=45,
        naked_allowed=True, debit_preferred=False, avoid_long_premium=False,
    )


def test_funding_rate_veto_returns_score_zero():
    """funding_rate=0.03 (> 0.025 threshold) → score=0 with veto_reason.

    Pin bar_hour_utc to 12:00 so the dead-zone and funding-window vetoes
    don't fire ahead of the funding-rate veto we're trying to exercise.
    """
    structure = _make_structure()
    regime = _make_regime()
    signal = _make_signal()
    exec_t = _make_exec()
    policy = _make_policy()

    result = score_structure(
        structure, regime, signal, exec_t, policy, funding_rate=0.03,
        bar_hour_utc=12, bar_minute_utc=30,
    )
    assert result.score == 0.0
    assert "funding" in result.score_breakdown.get("veto_reason", "").lower()


def test_funding_rate_veto_includes_funding_in_reason():
    """Veto reason for funding should mention 'funding'.

    Pin bar_hour_utc to 12:00 to side-step dead-zone / funding-window
    vetoes that would otherwise pre-empt the funding-rate veto.
    """
    structure = _make_structure()
    result = score_structure(
        structure, _make_regime(), _make_signal(), _make_exec(), _make_policy(),
        funding_rate=0.03,
        bar_hour_utc=12, bar_minute_utc=30,
    )
    assert result.score == 0.0
    veto = result.score_breakdown.get("veto_reason", "")
    assert "funding" in veto.lower()


def test_normal_funding_rate_does_not_veto():
    """funding_rate=0.01 (< 0.025) should not trigger veto."""
    structure = _make_structure()
    result = score_structure(
        structure, _make_regime(), _make_signal(), _make_exec(), _make_policy(),
        funding_rate=0.01,
        # Pin to 12:00 UTC — outside dead zone, outside any funding window
        bar_hour_utc=12, bar_minute_utc=30,
    )
    assert result.score > 0.0


def test_no_funding_rate_does_not_veto():
    """No funding_rate (None) should not trigger funding veto."""
    structure = _make_structure()
    result = score_structure(
        structure, _make_regime(), _make_signal(), _make_exec(), _make_policy(),
        funding_rate=None,
        bar_hour_utc=12, bar_minute_utc=30,
    )
    assert result.score > 0.0
