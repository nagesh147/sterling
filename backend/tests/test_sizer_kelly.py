import pytest
from app.schemas.execution import TradeStructure, CandidateContract, SizedTrade
from app.schemas.directional import Direction
from app.schemas.risk import RiskParams
from app.engines.directional.sizing_engine import size_trade, _fractional_kelly


def _make_structure(rr: float = 2.0) -> TradeStructure:
    return TradeStructure(
        structure_type="bull_call_spread",
        direction=Direction.LONG,
        legs=[],
        max_loss=100.0,
        max_gain=rr * 100.0,
        net_premium=100.0,
        risk_reward=rr,
        score=80.0,
        score_breakdown={},
    )


def _make_risk(win_rate: float = 0.52, capital: float = 100_000.0) -> RiskParams:
    return RiskParams(capital=capital, max_position_pct=0.05, max_contracts=20, win_rate=win_rate)


def test_lower_win_rate_gives_smaller_size():
    """win_rate=0.3 → smaller fractional Kelly than 0.6 at same RR."""
    kelly_low = _fractional_kelly(0.3, 2.0)
    kelly_high = _fractional_kelly(0.6, 2.0)
    assert kelly_low < kelly_high


def test_kelly_positive_for_positive_edge():
    kelly = _fractional_kelly(0.55, 2.0)
    assert kelly > 0.0


def test_kelly_zero_for_negative_edge():
    """win_rate < breakeven → kelly <= 0 → clamped to 0."""
    kelly = _fractional_kelly(0.3, 2.0)
    # With rr=2.0, breakeven = 1/3 ≈ 0.333. win_rate=0.3 < 0.333 → negative kelly
    assert kelly == 0.0


def test_size_trade_respects_max_position_pct():
    risk = _make_risk(win_rate=0.6, capital=100_000.0)
    risk.max_position_pct = 0.02
    structure = _make_structure(rr=2.0)
    result = size_trade(structure, risk)
    # Position risk should not exceed max_position_pct * capital
    assert result.max_risk_usd <= risk.capital * risk.max_position_pct * 1.01  # small float tolerance


def test_size_trade_returns_sized_trade():
    risk = _make_risk(win_rate=0.52)
    structure = _make_structure()
    result = size_trade(structure, risk)
    assert isinstance(result, SizedTrade)
    assert result.contracts >= 1


def test_win_rate_field_in_risk_params():
    """RiskParams should include win_rate field with default 0.52."""
    risk = RiskParams()
    assert hasattr(risk, "win_rate")
    assert risk.win_rate == 0.52
