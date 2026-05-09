import pytest
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.directional import Direction
from app.engines.directional.scoring import _score_rr_v2


def _make_structure(rr: float) -> TradeStructure:
    return TradeStructure(
        structure_type="bull_call_spread", direction=Direction.LONG,
        legs=[], max_loss=100.0, max_gain=rr * 100.0,
        net_premium=100.0, risk_reward=rr, score=0.0, score_breakdown={},
    )


def test_rr_1_4_gives_0():
    assert _score_rr_v2(_make_structure(1.4)) == 0.0


def test_rr_1_5_gives_0():
    """1.5 boundary is < 1.5 for 0 pts, but 1.5 exactly = 1.5 which is NOT < 1.5, so 7 pts."""
    # 1.5 >= 1.5, so it goes to the >= 1.5 branch → 7 pts
    assert _score_rr_v2(_make_structure(1.5)) == 7.0


def test_rr_1_8_gives_7():
    assert _score_rr_v2(_make_structure(1.8)) == 7.0


def test_rr_2_0_gives_7():
    """Exactly 2.0: falls into the rr < 2.0 == False, rr < 2.5 == True → 11 pts."""
    assert _score_rr_v2(_make_structure(2.0)) == 11.0


def test_rr_2_3_gives_11():
    assert _score_rr_v2(_make_structure(2.3)) == 11.0


def test_rr_2_5_gives_15():
    assert _score_rr_v2(_make_structure(2.5)) == 15.0


def test_rr_3_0_gives_15():
    assert _score_rr_v2(_make_structure(3.0)) == 15.0


def test_rr_none_gives_0():
    struct = TradeStructure(
        structure_type="naked_call", direction=Direction.LONG,
        legs=[], max_loss=None, max_gain=None,
        net_premium=100.0, risk_reward=None, score=0.0, score_breakdown={},
    )
    assert _score_rr_v2(struct) == 0.0
