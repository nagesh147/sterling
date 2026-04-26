"""
Tests for structure_selector, scoring, paper_store, and positions API.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.schemas.execution import CandidateContract, TradeStructure
from app.schemas.directional import Direction, PolicyResult, IVRBand
from app.schemas.instruments import InstrumentMeta
from app.engines.directional.structure_selector import build_structures
from app.engines.directional.policy_engine import apply_policy
from app.schemas.market import Candle
from main import create_app


_INST = InstrumentMeta(
    underlying="BTC", tick_size=0.5, strike_step=1000.0,
    exchange="deribit", exchange_currency="BTC",
    perp_symbol="BTC-PERPETUAL", index_name="btc_usd",
    dvol_symbol="BTC-DVOL",
)

_NOW = int(time.time() * 1000)


def _call(strike: float, bid: float = 400.0, ask: float = 420.0, dte: int = 12) -> CandidateContract:
    return CandidateContract(
        instrument_name=f"BTC-12JAN25-{int(strike)}-C",
        underlying="BTC", strike=strike, expiry_date="12JAN25", dte=dte,
        option_type="call", bid=bid, ask=ask,
        mark_price=(bid + ask) / 2, mid_price=(bid + ask) / 2,
        mark_iv=55.0, delta=0.45, open_interest=500.0, volume_24h=50.0,
        spread_pct=(ask - bid) / ((bid + ask) / 2),
        health_score=80.0, healthy=True,
    )


def _put(strike: float, bid: float = 300.0, ask: float = 320.0, dte: int = 12) -> CandidateContract:
    return CandidateContract(
        instrument_name=f"BTC-12JAN25-{int(strike)}-P",
        underlying="BTC", strike=strike, expiry_date="12JAN25", dte=dte,
        option_type="put", bid=bid, ask=ask,
        mark_price=(bid + ask) / 2, mid_price=(bid + ask) / 2,
        mark_iv=58.0, delta=-0.40, open_interest=300.0, volume_24h=30.0,
        spread_pct=(ask - bid) / ((bid + ask) / 2),
        health_score=75.0, healthy=True,
    )


_POLICY_LOW_IVR = apply_policy(Direction.LONG, _INST, ivr=30.0)
_POLICY_HIGH_IVR = apply_policy(Direction.LONG, _INST, ivr=85.0)
_SHORT_POLICY = apply_policy(Direction.SHORT, _INST, ivr=30.0)


class TestStructureSelectorLong:
    def test_naked_call_built(self):
        calls = [_call(95000), _call(96000)]
        puts: list = []
        structures = build_structures(calls, puts, Direction.LONG, _POLICY_LOW_IVR)
        types = [s.structure_type for s in structures]
        assert "naked_call" in types

    def test_bull_call_spread_built(self):
        calls = [_call(95000), _call(96000)]
        structures = build_structures(calls, [], Direction.LONG, _POLICY_LOW_IVR)
        types = [s.structure_type for s in structures]
        assert "bull_call_spread" in types

    def test_bull_put_spread_built(self):
        # Sell higher-strike put (higher premium), buy lower-strike put (lower premium) → credit
        lower_put = _put(93000, bid=100, ask=110)
        higher_put = _put(94000, bid=260, ask=275)
        structures = build_structures([], [lower_put, higher_put], Direction.LONG, _POLICY_LOW_IVR)
        types = [s.structure_type for s in structures]
        assert "bull_put_spread" in types

    def test_bull_call_spread_max_loss_debit(self):
        low_call = _call(95000, bid=400, ask=420)
        high_call = _call(96000, bid=200, ask=220)
        structures = build_structures([low_call, high_call], [], Direction.LONG, _POLICY_LOW_IVR)
        spreads = [s for s in structures if s.structure_type == "bull_call_spread"]
        assert spreads
        s = spreads[0]
        expected_debit = low_call.ask - high_call.bid
        assert s.max_loss == pytest.approx(expected_debit)

    def test_bull_put_spread_max_gain_credit(self):
        lower_put = _put(92000, bid=100, ask=110)  # buy (protection)
        higher_put = _put(94000, bid=250, ask=265)  # sell
        structures = build_structures([], [lower_put, higher_put], Direction.LONG, _POLICY_LOW_IVR)
        spreads = [s for s in structures if s.structure_type == "bull_put_spread"]
        assert spreads
        s = spreads[0]
        expected_credit = higher_put.bid - lower_put.ask
        assert s.max_gain == pytest.approx(expected_credit)

    def test_high_ivr_excludes_naked(self):
        calls = [_call(95000), _call(96000)]
        structures = build_structures(calls, [], Direction.LONG, _POLICY_HIGH_IVR)
        types = [s.structure_type for s in structures]
        assert "naked_call" not in types

    def test_no_structures_for_empty_candidates(self):
        structures = build_structures([], [], Direction.LONG, _POLICY_LOW_IVR)
        assert structures == []

    def test_rr_positive_for_debit_spreads(self):
        calls = [_call(95000, bid=400, ask=420), _call(96000, bid=200, ask=220)]
        structures = build_structures(calls, [], Direction.LONG, _POLICY_LOW_IVR)
        spreads = [s for s in structures if "spread" in s.structure_type and s.risk_reward]
        for s in spreads:
            assert s.risk_reward > 0


class TestStructureSelectorShort:
    def test_naked_put_built(self):
        puts = [_put(94000), _put(93000)]
        structures = build_structures([], puts, Direction.SHORT, _SHORT_POLICY)
        types = [s.structure_type for s in structures]
        assert "naked_put" in types

    def test_bear_put_spread_built(self):
        puts = [_put(93000), _put(94000)]
        structures = build_structures([], puts, Direction.SHORT, _SHORT_POLICY)
        types = [s.structure_type for s in structures]
        assert "bear_put_spread" in types

    def test_bear_call_spread_built(self):
        # Sell lower-strike call (higher premium), buy higher-strike call (lower premium) → credit
        low_call = _call(96000, bid=230, ask=250)
        high_call = _call(97000, bid=80, ask=100)
        structures = build_structures([low_call, high_call], [], Direction.SHORT, _SHORT_POLICY)
        types = [s.structure_type for s in structures]
        assert "bear_call_spread" in types

    def test_bear_call_spread_is_credit(self):
        low_call = _call(96000, bid=220, ask=240)  # sell
        high_call = _call(97000, bid=100, ask=120)  # buy
        structures = build_structures([low_call, high_call], [], Direction.SHORT, _SHORT_POLICY)
        bear_spreads = [s for s in structures if s.structure_type == "bear_call_spread"]
        assert bear_spreads
        s = bear_spreads[0]
        # Credit = sell bid - buy ask
        expected_credit = low_call.bid - high_call.ask
        assert s.max_gain == pytest.approx(expected_credit)

    def test_neutral_produces_nothing(self):
        structures = build_structures([], [], Direction.NEUTRAL, _SHORT_POLICY)
        assert structures == []


class TestPaperStore:
    def setup_method(self):
        from app.services import paper_store
        paper_store._positions.clear()

    def test_add_and_retrieve(self):
        from app.services import paper_store
        from app.schemas.execution import SizedTrade
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[_call(95000)], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=70.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        pos = paper_store.add_position("BTC", sized, entry_spot_price=95000.0)
        assert pos.id
        assert pos.underlying == "BTC"
        retrieved = paper_store.get_position(pos.id)
        assert retrieved is not None
        assert retrieved.id == pos.id

    def test_close_position(self):
        from app.services import paper_store
        from app.schemas.execution import SizedTrade
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[_call(95000)], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=70.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        pos = paper_store.add_position("BTC", sized, entry_spot_price=95000.0)
        closed = paper_store.close_position(pos.id, exit_spot_price=96000.0)
        assert closed is not None
        assert closed.status.value == "closed"
        assert closed.exit_spot_price == 96000.0

    def test_counts(self):
        from app.services import paper_store
        from app.schemas.execution import SizedTrade
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[_call(95000)], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=70.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        paper_store.add_position("BTC", sized, 95000.0)
        paper_store.add_position("ETH", sized, 3500.0)
        assert paper_store.open_count() == 2
        assert paper_store.closed_count() == 0


def _make_candles(n=100, base=40000.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * 10, high=base + i * 10 + 50,
            low=base + i * 10 - 50, close=base + i * 10 + 5, volume=100.0,
        )
        for i in range(n)
    ]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42050.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=55.0)
    a.get_dvol_history = AsyncMock(return_value=[40.0, 50.0, 60.0])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    from app.services import paper_store
    paper_store._positions.clear()
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app, raise_server_exceptions=True) as c:
        c.app.state.adapter = adapter
        yield c


class TestPositionsAPI:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/positions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positions"] == []
        assert data["open_count"] == 0

    def test_enter_no_trade_raises_409(self, client):
        # Mock returns empty option chain → no_trade recommendation
        resp = client.post("/api/v1/positions/enter", json={"underlying": "BTC"})
        assert resp.status_code == 409

    def test_enter_unknown_underlying_404(self, client):
        resp = client.post("/api/v1/positions/enter", json={"underlying": "DOGE"})
        assert resp.status_code == 404

    def test_get_nonexistent_404(self, client):
        resp = client.get("/api/v1/positions/DEADBEEF")
        assert resp.status_code == 404

    def test_close_nonexistent_404(self, client):
        resp = client.post(
            "/api/v1/positions/DEADBEEF/close",
            json={"exit_spot_price": 42000.0},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_404(self, client):
        resp = client.delete("/api/v1/positions/DEADBEEF")
        assert resp.status_code == 404
