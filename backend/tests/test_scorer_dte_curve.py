import pytest
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.directional import Direction
from app.engines.directional.scoring import _score_dte_v2


def _make_structure(dte: int) -> TradeStructure:
    leg = CandidateContract(
        instrument_name="BTC-31MAY24-30000-C", underlying="BTC",
        strike=30000.0, expiry_date="2024-05-31", dte=dte, option_type="call",
        bid=100.0, ask=102.0, mark_price=101.0, mid_price=101.0,
        mark_iv=0.6, delta=0.5, open_interest=200.0, volume_24h=50.0,
        spread_pct=0.02, health_score=90.0, healthy=True,
    )
    return TradeStructure(
        structure_type="bull_call_spread", direction=Direction.LONG,
        legs=[leg], max_loss=200.0, max_gain=800.0,
        net_premium=200.0, risk_reward=4.0, score=0.0, score_breakdown={},
    )


def test_dte_less_than_7_gives_0():
    assert _score_dte_v2(_make_structure(6)) == 0.0


def test_dte_less_than_14_gives_3():
    assert _score_dte_v2(_make_structure(10)) == 3.0


def test_dte_30_gives_10():
    assert _score_dte_v2(_make_structure(30)) == 10.0


def test_dte_45_gives_10():
    assert _score_dte_v2(_make_structure(45)) == 10.0


def test_dte_50_gives_7():
    assert _score_dte_v2(_make_structure(50)) == 7.0


def test_dte_70_gives_5():
    assert _score_dte_v2(_make_structure(70)) == 5.0


def test_futures_gets_full_dte_credit():
    """Futures structure always gets full DTE credit (10 pts)."""
    leg = CandidateContract(
        instrument_name="BTC-PERP", underlying="BTC",
        strike=0.0, expiry_date="perpetual", dte=0, option_type="call",
        bid=100.0, ask=101.0, mark_price=100.5, mid_price=100.5,
        mark_iv=0.0, delta=1.0, open_interest=1000.0, volume_24h=500.0,
        spread_pct=0.01, health_score=100.0, healthy=True,
    )
    struct = TradeStructure(
        structure_type="futures", direction=Direction.LONG,
        legs=[leg], max_loss=None, max_gain=None,
        net_premium=100.0, risk_reward=None, score=0.0, score_breakdown={},
    )
    assert _score_dte_v2(struct) == 10.0
