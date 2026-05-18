"""
Issue 16 — deterministic dead-zone tests.

`scoring._resolve_now_utc` reads STERLING_SCORING_NOW from the environment
as a deterministic override. We use that instead of freezegun because the
scoring module reads the clock through that helper, not through a global
patcheable datetime.
"""
import os
import pytest
from app.engines.directional.scoring import score_structure
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult, PolicyResult,
    MacroRegime, ExecMode, IVRBand, Direction,
)


def _leg(oi=200.0, spread_pct=0.02, dte=30) -> CandidateContract:
    return CandidateContract(
        instrument_name="BTC-31MAY24-30000-C",
        underlying="BTC", strike=30000.0,
        expiry_date="2024-05-31", dte=dte, option_type="call",
        bid=100.0, ask=102.0, mark_price=101.0, mid_price=101.0,
        mark_iv=0.6, delta=0.5, open_interest=oi, volume_24h=50.0,
        spread_pct=spread_pct, health_score=90.0, healthy=True,
    )


def _structure() -> TradeStructure:
    return TradeStructure(
        structure_type="bull_call_spread", direction=Direction.LONG,
        legs=[_leg()], max_loss=200.0, max_gain=800.0,
        net_premium=200.0, risk_reward=4.0,
        score=0.0, score_breakdown={},
    )


def _regime() -> RegimeResult:
    return RegimeResult(
        macro_regime=MacroRegime.BULL_TREND,
        ema50=30000.0, close_4h=31000.0, score=15.0,
        atr_percentile=55.0, adx=30.0,
    )


def _signal() -> SignalResult:
    return SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=True, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[29000.0, 0.0, 0.0],
        close_1h=31000.0, score_long=100.0, score_short=0.0,
        signal_strength="STRONG", signal_score=16.0,
    )


def _exec() -> ExecTimingResult:
    return ExecTimingResult(mode=ExecMode.PULLBACK, confidence=0.9,
                            reason="test", exec_score=14.0)


def _policy() -> PolicyResult:
    return PolicyResult(
        allowed_structures=["bull_call_spread"], ivr=30.0,
        ivr_band=IVRBand.NORMAL,
        preferred_dte_min=10, preferred_dte_max=45,
        naked_allowed=True, debit_preferred=False, avoid_long_premium=False,
    )


@pytest.fixture(autouse=True)
def _cleanup_env():
    """Ensure env overrides don't leak between tests."""
    for k in ("STERLING_SCORING_NOW", "STERLING_FORCE_DEAD_ZONE_PASS"):
        os.environ.pop(k, None)
    yield
    for k in ("STERLING_SCORING_NOW", "STERLING_FORCE_DEAD_ZONE_PASS"):
        os.environ.pop(k, None)


def test_dead_zone_blocks_when_env_pinned_to_3am():
    os.environ["STERLING_SCORING_NOW"] = "03:00"
    result = score_structure(_structure(), _regime(), _signal(),
                             _exec(), _policy(), funding_rate=0.0)
    assert result.score == 0.0
    veto = result.score_breakdown.get("veto_reason", "")
    assert "dead zone" in veto.lower()


def test_dead_zone_does_not_block_when_caller_pins_safe_hour():
    """Even with env pinned to 03:00, caller-supplied bar_hour wins."""
    os.environ["STERLING_SCORING_NOW"] = "03:00"
    result = score_structure(_structure(), _regime(), _signal(),
                             _exec(), _policy(),
                             funding_rate=0.0,
                             bar_hour_utc=12, bar_minute_utc=30)
    assert result.score > 0.0


def test_force_pass_env_overrides_dead_zone():
    """STERLING_FORCE_DEAD_ZONE_PASS=1 makes the fallback land on 12:30 UTC."""
    os.environ["STERLING_FORCE_DEAD_ZONE_PASS"] = "1"
    result = score_structure(_structure(), _regime(), _signal(),
                             _exec(), _policy(), funding_rate=0.0)
    assert result.score > 0.0


def test_dead_zone_blocks_at_each_hour_in_band():
    for h in (2, 3, 4, 5):
        os.environ["STERLING_SCORING_NOW"] = f"{h:02d}:30"
        result = score_structure(_structure(), _regime(), _signal(),
                                 _exec(), _policy(), funding_rate=0.0)
        assert result.score == 0.0, f"dead-zone hour {h} should veto"
        assert "dead zone" in result.score_breakdown.get("veto_reason", "").lower()


def test_funding_window_blocks_at_boundaries():
    # 00:05 UTC is within ±15 min of the 00:00 funding boundary.
    os.environ["STERLING_SCORING_NOW"] = "00:05"
    # 00:00 falls in the dead-zone-adjacent area (hour 0 isn't in {2,3,4,5},
    # so funding-window is what should fire).
    result = score_structure(_structure(), _regime(), _signal(),
                             _exec(), _policy(), funding_rate=0.0)
    veto = result.score_breakdown.get("veto_reason", "")
    assert result.score == 0.0
    assert "funding window" in veto.lower() or "dead zone" in veto.lower()
