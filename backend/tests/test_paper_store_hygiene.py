"""
Issue 17 — paper_store guards against entry_spot_price <= 0.
"""
import pytest
from app.services import paper_store
from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
from app.schemas.directional import Direction


def _make_sized_trade() -> SizedTrade:
    leg = CandidateContract(
        instrument_name="BTC-31MAY24-30000-C",
        underlying="BTC", strike=30000.0,
        expiry_date="2024-05-31", dte=30, option_type="call",
        bid=100.0, ask=102.0, mark_price=101.0, mid_price=101.0,
        mark_iv=0.6, delta=0.5, open_interest=200.0, volume_24h=50.0,
        spread_pct=0.02, health_score=90.0, healthy=True,
    )
    structure = TradeStructure(
        structure_type="bull_call_spread",
        direction=Direction.LONG,
        legs=[leg],
        max_loss=200.0, max_gain=800.0,
        net_premium=200.0, risk_reward=4.0,
        score=80.0, score_breakdown={},
    )
    return SizedTrade(
        structure=structure, contracts=1,
        position_value=200.0, max_risk_usd=200.0,
        capital_at_risk_pct=0.2,
    )


def test_add_position_rejects_zero_entry_spot():
    """Issue 17: entry_spot_price=0 must raise — prevents pre-TTACE seed-row mistake."""
    sized = _make_sized_trade()
    with pytest.raises(ValueError, match="entry_spot_price"):
        paper_store.add_position(
            underlying="BTC", sized_trade=sized,
            entry_spot_price=0.0,
        )


def test_add_position_rejects_negative_entry_spot():
    sized = _make_sized_trade()
    with pytest.raises(ValueError, match="entry_spot_price"):
        paper_store.add_position(
            underlying="BTC", sized_trade=sized,
            entry_spot_price=-1.0,
        )


def test_add_position_accepts_valid_entry_spot():
    sized = _make_sized_trade()
    pos = paper_store.add_position(
        underlying="BTC", sized_trade=sized,
        entry_spot_price=65000.0,
    )
    assert pos is not None
    assert pos.entry_spot_price == 65000.0
    # cleanup so we don't poison the in-memory store for later tests
    paper_store.delete_position(pos.id)
