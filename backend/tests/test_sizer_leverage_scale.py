import pytest
from app.schemas.execution import TradeStructure, SizedTrade
from app.schemas.directional import Direction
from app.schemas.risk import RiskParams
from app.engines.directional.sizing_engine import size_trade, _nearest_lev_key, _LEV_SCALE


def _make_structure(rr: float = 2.0) -> TradeStructure:
    return TradeStructure(
        structure_type="futures",
        direction=Direction.LONG,
        legs=[],
        max_loss=1000.0,
        max_gain=rr * 1000.0,
        net_premium=1000.0,
        risk_reward=rr,
        score=90.0,
        score_breakdown={},
    )


def test_50x_leverage_scales_cap_to_15_pct():
    """50x leverage → per_trade cap scaled to 15% of base cap.
    With a cheap contract (max_loss=10), multiple contracts fit within the cap."""
    risk = RiskParams(capital=100_000.0, win_rate=0.6, max_contracts=500)
    structure = TradeStructure(
        structure_type="futures", direction=Direction.LONG,
        legs=[], max_loss=10.0, max_gain=20.0,
        net_premium=10.0, risk_reward=2.0, score=90.0, score_breakdown={},
    )
    # futures base cap = 2%. With 50x: 2% * 0.15 = 0.3% → $300 max
    result = size_trade(structure, risk, leverage=50)
    expected_max = 100_000.0 * 0.02 * 0.15
    assert result.max_risk_usd <= expected_max + 1.0  # +1 for float tolerance


def test_1x_leverage_uses_full_base_cap():
    """1x leverage → no scaling reduction.

    Uses a cheap contract (max_loss=10) so both 1x and 50x produce >1
    contracts naturally. With slippage now wired into max_loss_per_contract,
    the int(raw_contracts) at high leverage can collapse to 0 -> max(1,0)=1,
    which would invert the comparison.
    """
    risk = RiskParams(capital=100_000.0, win_rate=0.6, max_contracts=500)
    structure = TradeStructure(
        structure_type="futures", direction=Direction.LONG,
        legs=[], max_loss=10.0, max_gain=20.0,
        net_premium=10.0, risk_reward=2.0, score=90.0, score_breakdown={},
    )
    result_1x = size_trade(structure, risk, leverage=1)
    result_50x = size_trade(structure, risk, leverage=50)
    assert result_1x.capital_at_risk_pct > result_50x.capital_at_risk_pct


def test_nearest_lev_key():
    """Nearest leverage key lookup."""
    assert _nearest_lev_key(1) == 1
    assert _nearest_lev_key(5) == 5
    assert _nearest_lev_key(10) == 10
    assert _nearest_lev_key(25) == 25
    assert _nearest_lev_key(50) == 50
    assert _nearest_lev_key(7) in (5, 10)  # between 5 and 10


def test_lev_scale_keys():
    """LEV_SCALE should have 50x with value 0.15."""
    assert 50 in _LEV_SCALE
    assert _LEV_SCALE[50] == 0.15
    assert _LEV_SCALE[1] == 1.0
