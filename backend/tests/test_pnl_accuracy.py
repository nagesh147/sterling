"""
Tests for P&L accuracy with multi-leg spread positions.
Verifies net-delta computation (bull_call_spread, bear_put_spread,
bull_put_spread, bear_call_spread) against naked options.
"""
import pytest
from app.schemas.execution import SizedTrade, TradeStructure
from app.schemas.directional import Direction


def _cc(strike: float, delta: float, bid=400.0, ask=420.0, dte=12) -> dict:
    """Minimal CandidateContract dict for testing."""
    from app.schemas.execution import CandidateContract
    return CandidateContract(
        instrument_name=f"BTC-{int(strike)}-C",
        underlying="BTC", strike=strike, expiry_date="12JAN25", dte=dte,
        option_type="call", bid=bid, ask=ask,
        mark_price=(bid + ask) / 2, mid_price=(bid + ask) / 2,
        mark_iv=55.0, delta=delta,
        open_interest=500.0, volume_24h=50.0,
        spread_pct=0.05, health_score=80.0, healthy=True,
    )


def _cp(strike: float, delta: float, bid=300.0, ask=320.0, dte=12) -> dict:
    from app.schemas.execution import CandidateContract
    return CandidateContract(
        instrument_name=f"BTC-{int(strike)}-P",
        underlying="BTC", strike=strike, expiry_date="12JAN25", dte=dte,
        option_type="put", bid=bid, ask=ask,
        mark_price=(bid + ask) / 2, mid_price=(bid + ask) / 2,
        mark_iv=58.0, delta=delta,
        open_interest=300.0, volume_24h=30.0,
        spread_pct=0.06, health_score=75.0, healthy=True,
    )


def _make_sized(structure_type: str, direction: Direction, legs, max_loss, max_gain=None) -> SizedTrade:
    return SizedTrade(
        structure=TradeStructure(
            structure_type=structure_type,
            direction=direction,
            legs=legs,
            max_loss=max_loss,
            max_gain=max_gain,
            net_premium=max_loss,
            risk_reward=None if max_gain is None else max_gain / max_loss,
            score=70.0,
            score_breakdown={},
        ),
        contracts=1,
        position_value=max_loss,
        max_risk_usd=max_loss,
        capital_at_risk_pct=1.0,
    )


# Import the function under test
from app.api.v1.endpoints.positions import _net_delta, _estimate_pnl


class TestNetDelta:
    def test_naked_call_uses_abs_delta(self):
        """Naked call: net_delta = abs(legs[0].delta)."""
        leg = _cc(95000, delta=0.45)
        trade = _make_sized("naked_call", Direction.LONG, [leg], max_loss=420.0)
        assert _net_delta(trade) == pytest.approx(0.45)

    def test_naked_put_uses_abs_delta(self):
        """Naked put: delta is negative, abs taken."""
        leg = _cp(90000, delta=-0.40)
        trade = _make_sized("naked_put", Direction.SHORT, [leg], max_loss=310.0)
        assert _net_delta(trade) == pytest.approx(0.40)

    def test_bull_call_spread_net_delta(self):
        """Debit: legs[0]=long(0.45), legs[1]=short(0.30) → net=0.15."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        trade = _make_sized("bull_call_spread", Direction.LONG,
                            [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        assert _net_delta(trade) == pytest.approx(0.15)

    def test_bear_put_spread_net_delta(self):
        """Debit: legs[0]=long put(-0.45), legs[1]=short put(-0.25) → net=0.20."""
        long_leg = _cp(95000, delta=-0.45)
        short_leg = _cp(90000, delta=-0.25)
        trade = _make_sized("bear_put_spread", Direction.SHORT,
                            [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        assert _net_delta(trade) == pytest.approx(0.20)

    def test_bull_put_spread_net_delta_credit(self):
        """Credit: legs[0]=short put(-0.40), legs[1]=long put(-0.20) → net=0.20."""
        short_leg = _cp(94000, delta=-0.40)
        long_leg = _cp(92000, delta=-0.20)
        trade = _make_sized("bull_put_spread", Direction.LONG,
                            [short_leg, long_leg], max_loss=100.0, max_gain=900.0)
        assert _net_delta(trade) == pytest.approx(0.20)

    def test_bear_call_spread_net_delta_credit(self):
        """Credit: legs[0]=short call(0.40), legs[1]=long call(0.20) → net=0.20."""
        short_leg = _cc(95000, delta=0.40)
        long_leg = _cc(97000, delta=0.20)
        trade = _make_sized("bear_call_spread", Direction.SHORT,
                            [short_leg, long_leg], max_loss=200.0, max_gain=800.0)
        assert _net_delta(trade) == pytest.approx(0.20)

    def test_empty_legs_returns_zero(self):
        trade = _make_sized("naked_call", Direction.LONG, [], max_loss=100.0)
        assert _net_delta(trade) == 0.0

    def test_degenerate_spread_clamps_to_zero(self):
        """If somehow short_delta > long_delta, clamp to 0."""
        long_leg = _cc(95000, delta=0.20)
        short_leg = _cc(96000, delta=0.40)  # unusual, but clamp
        trade = _make_sized("bull_call_spread", Direction.LONG,
                            [long_leg, short_leg], max_loss=100.0, max_gain=100.0)
        assert _net_delta(trade) == 0.0


class TestEstimatePnL:
    def test_naked_call_pnl_spot_up(self):
        """Naked call long: spot +1000, delta 0.45 → 450 (no ceiling cap; only floor at -max_risk)."""
        leg = _cc(95000, delta=0.45)
        trade = _make_sized("naked_call", Direction.LONG, [leg], max_loss=420.0)
        pnl = _estimate_pnl(trade, 1000.0, 1, 420.0, None)
        assert pnl == pytest.approx(450.0)

    def test_spread_pnl_smaller_than_naked(self):
        """bull_call_spread net_delta(0.15) < naked_call delta(0.45)."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        spread = _make_sized("bull_call_spread", Direction.LONG,
                             [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        naked = _make_sized("naked_call", Direction.LONG, [long_leg], max_loss=420.0)

        pnl_spread = _estimate_pnl(spread, 1000.0, 1, 200.0, 800.0)
        pnl_naked = _estimate_pnl(naked, 1000.0, 1, 420.0, None)
        # Spread P&L (net_delta 0.15×1000=150) < naked (0.45×1000=450 but capped at 420)
        assert pnl_spread < pnl_naked

    def test_spread_pnl_capped_at_max_gain(self):
        """Spread P&L can't exceed max_gain × contracts."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        trade = _make_sized("bull_call_spread", Direction.LONG,
                            [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        # Very large spot move: net_delta 0.15 × 10000 = 1500, but max_gain = 800
        pnl = _estimate_pnl(trade, 10000.0, 1, 200.0, 800.0)
        assert pnl == pytest.approx(800.0)

    def test_spread_pnl_capped_at_max_loss(self):
        """Spread P&L floor is -max_risk."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        trade = _make_sized("bull_call_spread", Direction.LONG,
                            [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        # Spot down 5000: net_delta 0.15 × -5000 × 1 = -750, capped at -200
        pnl = _estimate_pnl(trade, -5000.0, 1, 200.0, 800.0)
        assert pnl == pytest.approx(-200.0)

    def test_short_direction_pnl(self):
        """Short position: spot down 1000, naked put delta -0.40 → +400 (no ceiling cap)."""
        leg = _cp(90000, delta=-0.40)
        trade = _make_sized("naked_put", Direction.SHORT, [leg], max_loss=310.0)
        # direction_sign=-1, spot_move=-1000: (-1) × (-1000) × 0.40 = 400
        pnl = _estimate_pnl(trade, -1000.0, -1, 310.0, None)
        assert pnl == pytest.approx(400.0)

    def test_multi_contract_scaling(self):
        """P&L scales linearly with contracts."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        trade_1 = _make_sized("bull_call_spread", Direction.LONG,
                              [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        # Create 2-contract version
        trade_2 = SizedTrade(
            structure=trade_1.structure,
            contracts=2,
            position_value=400.0,
            max_risk_usd=400.0,
            capital_at_risk_pct=2.0,
        )
        pnl_1 = _estimate_pnl(trade_1, 500.0, 1, 200.0, 800.0)  # net: 0.15×500×1=75
        pnl_2 = _estimate_pnl(trade_2, 500.0, 1, 400.0, 800.0)  # net: 0.15×500×2=150
        assert pnl_2 == pytest.approx(pnl_1 * 2)


class TestFuturesPnL:
    """Regression tests for the v4 bug where futures positions always
    reported open P/L = 0 because `_net_delta` returned 0 for empty
    `legs`. The widget on the dashboard was permanently stuck at zero.
    Fix: futures structures now return leverage as the effective delta."""

    def _futures_sized(self, contracts: int = 1, leverage: int = 5,
                       max_risk: float = 200.0):
        return SizedTrade(
            structure=TradeStructure(
                structure_type="futures",
                direction=Direction.LONG,
                legs=[],                     # ← empty by construction
                max_loss=max_risk,
                max_gain=None,               # futures: unbounded gain
                net_premium=0.0,
                risk_reward=2.0,
                score=80.0,
                score_breakdown={},
                leverage=leverage,
                entry_price=100.0,
            ),
            contracts=contracts,
            position_value=max_risk,
            max_risk_usd=max_risk,
            capital_at_risk_pct=1.0,
        )

    def test_futures_net_delta_is_leverage(self):
        """Futures with empty legs returns the leverage as effective delta."""
        trade = self._futures_sized(contracts=1, leverage=5)
        assert _net_delta(trade) == pytest.approx(5.0)
        trade = self._futures_sized(contracts=1, leverage=10)
        assert _net_delta(trade) == pytest.approx(10.0)
        trade = self._futures_sized(contracts=1, leverage=1)
        assert _net_delta(trade) == pytest.approx(1.0)

    def test_futures_long_positive_spot_move_returns_nonzero_pnl(self):
        """+100 spot move on 1 contract @ 5x leverage → +500 raw, uncapped."""
        trade = self._futures_sized(contracts=1, leverage=5, max_risk=200.0)
        pnl = _estimate_pnl(
            trade, spot_move=100.0, direction_sign=1,
            max_risk_usd=200.0, max_gain_usd=None,
        )
        assert pnl == pytest.approx(500.0)
        # The legacy bug returned 0.0 here.
        assert pnl != 0.0

    def test_futures_long_negative_spot_move_capped_at_max_risk(self):
        """-100 spot move on 1 contract @ 5x → raw -500, capped at -max_risk."""
        trade = self._futures_sized(contracts=1, leverage=5, max_risk=200.0)
        pnl = _estimate_pnl(
            trade, spot_move=-100.0, direction_sign=1,
            max_risk_usd=200.0, max_gain_usd=None,
        )
        assert pnl == pytest.approx(-200.0)

    def test_futures_short_pnl_inverts(self):
        """Short futures + price up = loss; capped at -max_risk."""
        trade = self._futures_sized(contracts=1, leverage=5, max_risk=200.0)
        pnl = _estimate_pnl(
            trade, spot_move=100.0, direction_sign=-1,
            max_risk_usd=200.0, max_gain_usd=None,
        )
        assert pnl == pytest.approx(-200.0)

    def test_futures_contracts_scale_pnl(self):
        """Doubling contracts doubles the un-capped P&L."""
        trade1 = self._futures_sized(contracts=1, leverage=5, max_risk=2000.0)
        trade2 = self._futures_sized(contracts=2, leverage=5, max_risk=4000.0)
        pnl1 = _estimate_pnl(trade1, 50.0, 1, 2000.0, None)
        pnl2 = _estimate_pnl(trade2, 50.0, 1, 4000.0, None)
        assert pnl2 == pytest.approx(pnl1 * 2)

    def test_options_still_unchanged(self):
        """Options with non-empty legs unaffected by the futures fallback."""
        long_leg = _cc(95000, delta=0.45)
        short_leg = _cc(96000, delta=0.30)
        trade = _make_sized("bull_call_spread", Direction.LONG,
                            [long_leg, short_leg], max_loss=200.0, max_gain=800.0)
        # Net delta 0.15 unchanged by the futures-fallback branch.
        assert _net_delta(trade) == pytest.approx(0.15)


class TestPaperStoreFuturesPnl:
    """paper_store.close_position and partial_close_position must use leverage
    as net_delta for futures (not 0.0)."""

    @staticmethod
    def _futures_pos(entry=100000.0, direction=Direction.SHORT, leverage=3,
                     contracts=1, max_risk=600.0, max_gain=600.0):
        from app.schemas.execution import CandidateContract, SizedTrade, TradeStructure
        from app.services import paper_store as ps
        leg = CandidateContract(
            instrument_name="BTC-PERP", underlying="BTC", strike=0, expiry_date="",
            dte=0, option_type="futures", bid=0, ask=0, mark_price=entry,
            mid_price=entry, mark_iv=0, delta=1.0 if direction == Direction.LONG else -1.0,
            open_interest=0, volume_24h=0, spread_pct=0, health_score=0, healthy=True,
        )
        struct = TradeStructure(
            structure_type="futures", direction=direction, legs=[leg],
            max_loss=max_risk / contracts / leverage, max_gain=max_gain / contracts / leverage,
            net_premium=0, risk_reward=1.0, score=0, score_breakdown={},
            leverage=leverage, entry_price=entry,
        )
        sized = SizedTrade(
            structure=struct, contracts=contracts,
            position_value=entry * contracts * leverage,
            max_risk_usd=max_risk, capital_at_risk_pct=0.01,
        )
        pos = ps.add_position(
            underlying="BTC", sized_trade=sized,
            entry_spot_price=entry, notes="test",
        )
        return pos

    def test_close_futures_short_pnl_positive_when_in_profit(self):
        """Short + price drops → P&L must be positive (not stuck at 0)."""
        pos = self._futures_pos(entry=100000.0, direction=Direction.SHORT, leverage=3)
        from app.services import paper_store as ps
        result = ps.close_position(pos.id, exit_spot_price=99000.0)
        assert result is not None
        assert result.realized_pnl_usd > 0, f"Expected positive P&L for short in profit, got {result.realized_pnl_usd}"

    def test_close_futures_long_pnl_positive_when_in_profit(self):
        """Long + price rises → P&L must be positive (not stuck at 0)."""
        pos = self._futures_pos(entry=100000.0, direction=Direction.LONG, leverage=3)
        from app.services import paper_store as ps
        result = ps.close_position(pos.id, exit_spot_price=101000.0)
        assert result is not None
        assert result.realized_pnl_usd > 0, f"Expected positive P&L for long in profit, got {result.realized_pnl_usd}"

    def test_close_futures_short_capped_at_max_risk(self):
        """Short + price rises → P&L capped at -max_risk."""
        pos = self._futures_pos(entry=100000.0, direction=Direction.SHORT, leverage=3, max_risk=600.0)
        from app.services import paper_store as ps
        result = ps.close_position(pos.id, exit_spot_price=110000.0)
        assert result is not None
        assert result.realized_pnl_usd >= -600.0

    def test_partial_close_futures_short_pnl(self):
        """partial_close_position for futures SHORT also uses leverage as net_delta."""
        pos = self._futures_pos(entry=100000.0, direction=Direction.SHORT, leverage=3, max_risk=600.0)
        from app.services import paper_store as ps
        result = ps.partial_close_position(pos.id, exit_spot_price=99000.0, partial_ratio=0.5)
        assert result is not None
        assert result.realized_pnl_usd is not None and result.realized_pnl_usd > 0
