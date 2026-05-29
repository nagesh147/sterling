"""Phase-0 derivatives-build correctness tests.

These tests lock in the bug fixes and new gates introduced in Phase 0 of
the derivatives selector plan:

  • paper_store.close_position futures PnL no longer multiplies by leverage
  • paper_store.close_position options PnL uses premium delta (not delta-linear
    in spot)
  • PaperPosition carries entry_premium/iv/dte/greeks_snapshot/exit_reason/
    fill_type/tds_withheld_usd/settlement_recorded
  • bsm_greeks_full returns all 5 Greeks; bsm_greeks back-compat preserved
  • GreeksBudgetChecker enforces a gamma cap in addition to delta/vega/theta
  • portfolio_greeks_aggregator.refresh_position_greeks delivers ±1 delta
    for futures and BSM-derived Greeks for options
  • OrderRouter rejects with code=greeks_budget_breach when the gate trips
  • OrderRouter calls set_margin_mode("isolated") before set_leverage for
    futures live orders
  • OrderRouter correlation_penalty preserves fractional contracts (no
    silent 1-contract floor for 0.7-scaled requests)

If any of these regress, a real-money order will mis-price on settlement
or escape the Greeks budget. Treat failures here as build-blocking.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, List, Optional
from unittest.mock import AsyncMock

import pytest


def _coid() -> str:
    """Unique client_order_id per submit — bypasses live_safety's process-
    wide idempotency cache so tests that all submit (BTC, long, futures, 1.0)
    within the same minute bucket don't shortcircuit each other with
    status=duplicate."""
    return f"phase0-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _reset_process_state():
    """Clear cross-test process-wide state polluted by close_position calls
    (cooldown engine) and OrderRouter live_safety records (idempotency /
    daily-loss / kill-switch / retry queue). Without this, the dozens of
    close_position calls in TestPaperStoreFuturesPnL etc. saturate the
    cooldown table for BTC and subsequent test files reject every BTC
    order with code=cooldown_active. See plan Phase 0."""
    from app.engines.risk import cooldown
    from app.services import live_safety
    cooldown.clear()
    live_safety.reset_all_for_tests()
    yield
    cooldown.clear()
    live_safety.reset_all_for_tests()

from app.engines.risk.greeks_budget import (
    bsm_greeks, bsm_greeks_full, GreeksBudget, GreeksBudgetChecker, PositionGreeks,
)
from app.engines.risk.portfolio_greeks_aggregator import (
    refresh_position_greeks, _parse_option_symbol, _GreeksAndNotional,
)
from app.schemas.directional import Direction
from app.schemas.execution import CandidateContract, SizedTrade, TradeStructure
from app.schemas.greeks import GreeksSnapshot
from app.services import paper_store as ps
from app.services.execution.order_router import (
    OrderRouter, OrderRouterRequest, RouterDeps, RouterMode,
)


# ─── helpers ───────────────────────────────────────────────────────────────


def _futures_pos(
    entry: float = 100_000.0,
    direction: Direction = Direction.LONG,
    leverage: int = 10,
    contracts: int = 1,
    max_risk: float = 5_000.0,
):
    leg = CandidateContract(
        instrument_name="BTC-PERP", underlying="BTC", strike=0,
        expiry_date="", dte=0, option_type="futures", bid=0, ask=0,
        mark_price=entry, mid_price=entry, mark_iv=0,
        delta=1.0 if direction == Direction.LONG else -1.0,
        open_interest=0, volume_24h=0, spread_pct=0,
        health_score=0, healthy=True,
    )
    struct = TradeStructure(
        structure_type="futures", direction=direction, legs=[leg],
        max_loss=max_risk / contracts, max_gain=None,
        net_premium=0, risk_reward=1.0, score=0, score_breakdown={},
        leverage=leverage, entry_price=entry,
    )
    sized = SizedTrade(
        structure=struct, contracts=contracts,
        position_value=entry * contracts,
        max_risk_usd=max_risk, capital_at_risk_pct=0.01,
    )
    return ps.add_position(
        underlying="BTC", sized_trade=sized,
        entry_spot_price=entry, notes="phase0-test", is_paper=True,
    )


def _options_pos(
    spot: float = 50_000.0,
    strike: float = 50_000.0,
    entry_premium: float = 1_200.0,
    contracts: int = 2,
    direction: Direction = Direction.LONG,
    iv: float = 0.65,
    dte: int = 10,
    is_paper: bool = True,
):
    leg = CandidateContract(
        instrument_name=f"C-BTC-{int(strike)}-310525",
        underlying="BTC", strike=strike, expiry_date="310525", dte=dte,
        option_type="call", bid=entry_premium - 5, ask=entry_premium + 5,
        mark_price=entry_premium, mid_price=entry_premium,
        mark_iv=iv * 100.0,                  # adapter returns percent
        delta=0.55, open_interest=200, volume_24h=80,
        spread_pct=0.01, health_score=85, healthy=True,
    )
    struct = TradeStructure(
        structure_type="naked_call", direction=direction, legs=[leg],
        max_loss=entry_premium, max_gain=None,
        net_premium=entry_premium, risk_reward=2.0,
        score=0, score_breakdown={}, leverage=1, entry_price=spot,
    )
    sized = SizedTrade(
        structure=struct, contracts=contracts,
        position_value=entry_premium * contracts,
        max_risk_usd=entry_premium * contracts, capital_at_risk_pct=0.01,
    )
    return ps.add_position(
        underlying="BTC", sized_trade=sized, entry_spot_price=spot,
        notes="phase0-test-opt", is_paper=is_paper,
        entry_premium=entry_premium, entry_iv=iv, entry_dte=dte,
        entry_greeks_snapshot=GreeksSnapshot(
            delta=0.55, gamma=0.00004, vega=55.0, theta=-60.0, rho=18.0,
            spot=spot, iv=iv, dte=dte,
        ),
    )


# ─── 1. paper_store futures PnL — no leverage multiplier ────────────────


class TestPaperStoreFuturesPnL:
    """Futures PnL must be (exit_price − entry_price) × contracts × dir.
    Pre-Phase-0 code multiplied by leverage, over-stating PnL by 10× on a
    10× leveraged trade. Real-money bug. Lock the correct math here."""

    def test_long_profit_exact_spot_move(self):
        pos = _futures_pos(entry=100_000.0, leverage=10, contracts=1, max_risk=10_000.0)
        closed = ps.close_position(pos.id, exit_spot_price=101_000.0, exit_reason="manual")
        assert closed is not None
        # Spot moved +$1000, 1 contract long → PnL = +$1000, NOT $10,000.
        assert closed.realized_pnl_usd == pytest.approx(1_000.0)

    def test_short_profit_exact_spot_move(self):
        pos = _futures_pos(entry=100_000.0, direction=Direction.SHORT,
                           leverage=10, contracts=1, max_risk=10_000.0)
        closed = ps.close_position(pos.id, exit_spot_price=99_500.0, exit_reason="manual")
        assert closed is not None
        # Spot −$500, short → PnL = +$500.
        assert closed.realized_pnl_usd == pytest.approx(500.0)

    def test_loss_floored_at_max_risk(self):
        pos = _futures_pos(entry=100_000.0, leverage=10, contracts=1, max_risk=600.0)
        closed = ps.close_position(pos.id, exit_spot_price=80_000.0, exit_reason="stop")
        assert closed is not None
        # Raw loss −$20k, floored at −max_risk.
        assert closed.realized_pnl_usd == pytest.approx(-600.0)

    def test_contracts_scale_pnl_linearly(self):
        p1 = _futures_pos(entry=100_000.0, contracts=1, max_risk=2_000.0)
        p2 = _futures_pos(entry=100_000.0, contracts=2, max_risk=4_000.0)
        c1 = ps.close_position(p1.id, exit_spot_price=100_500.0)
        c2 = ps.close_position(p2.id, exit_spot_price=100_500.0)
        # 2× contracts = 2× PnL: +$500 vs +$1000.
        assert c1.realized_pnl_usd == pytest.approx(500.0)
        assert c2.realized_pnl_usd == pytest.approx(1_000.0)

    def test_leverage_does_not_multiply_pnl(self):
        """Same trade with 1× vs 25× leverage produces same realised PnL.
        Leverage only affects margin posted, not PnL realised."""
        p1 = _futures_pos(entry=100_000.0, leverage=1, contracts=1, max_risk=10_000.0)
        p25 = _futures_pos(entry=100_000.0, leverage=25, contracts=1, max_risk=10_000.0)
        c1 = ps.close_position(p1.id, exit_spot_price=100_400.0)
        c25 = ps.close_position(p25.id, exit_spot_price=100_400.0)
        assert c1.realized_pnl_usd == pytest.approx(c25.realized_pnl_usd)
        assert c1.realized_pnl_usd == pytest.approx(400.0)


# ─── 2. paper_store options PnL — premium-based ─────────────────────────


class TestPaperStoreOptionsPnL:
    """Options PnL = (exit_premium − entry_premium) × contracts. Pre-Phase-0
    code used delta-linear spot move which silently mispriced gamma/vega
    moves."""

    def test_options_pnl_with_supplied_exit_premium(self):
        pos = _options_pos(spot=50_000.0, entry_premium=1_200.0, contracts=2)
        closed = ps.close_position(
            pos.id, exit_spot_price=51_000.0,
            exit_premium=1_750.0, exit_reason="tp",
        )
        assert closed is not None
        # (1750 − 1200) × 2 = 1100.
        assert closed.realized_pnl_usd == pytest.approx(1_100.0)
        assert closed.exit_premium == pytest.approx(1_750.0)

    def test_options_pnl_loss_floored_at_max_risk(self):
        pos = _options_pos(entry_premium=1_200.0, contracts=2)
        # max_risk = 1200×2 = 2400; a deeply unfavourable close still floors
        # at −max_risk (option premiums can't go negative anyway).
        closed = ps.close_position(pos.id, exit_spot_price=40_000.0, exit_premium=0.0)
        assert closed is not None
        assert closed.realized_pnl_usd == pytest.approx(-2_400.0)

    def test_options_pnl_fallback_to_delta_linear_on_missing_premium(self, caplog):
        pos = _options_pos(entry_premium=1_200.0, contracts=1)
        with caplog.at_level("WARNING"):
            closed = ps.close_position(pos.id, exit_spot_price=51_000.0)
        # Delta-linear: entry_prem + spot_move×delta = 1200 + 1000×0.55 = 1750.
        # PnL = (1750 − 1200) × 1 = 550.
        assert closed is not None
        assert closed.realized_pnl_usd == pytest.approx(550.0)
        assert any("delta-linear estimate" in rec.message for rec in caplog.records)

    def test_close_records_exit_reason_and_fill_type(self):
        pos = _options_pos()
        closed = ps.close_position(
            pos.id, exit_spot_price=51_000.0, exit_premium=1_750.0,
            exit_reason="trail", fill_type="normal",
        )
        assert closed.exit_reason == "trail"
        assert closed.fill_type == "normal"

    def test_settlement_flag_records_on_expiry_close(self):
        pos = _options_pos()
        closed = ps.close_position(
            pos.id, exit_spot_price=51_000.0, exit_premium=1_750.0,
            exit_reason="settlement", fill_type="settlement",
            settlement_recorded=True,
        )
        assert closed.settlement_recorded is True
        assert closed.fill_type == "settlement"


# ─── 3. PaperPosition new fields populate ──────────────────────────────


class TestPaperPositionOptionsSnapshot:
    def test_options_entry_snapshot_persists(self):
        pos = _options_pos(entry_premium=900.0, iv=0.7, dte=14)
        assert pos.entry_premium == pytest.approx(900.0)
        assert pos.entry_iv == pytest.approx(0.7)
        assert pos.entry_dte == 14
        assert pos.entry_greeks_snapshot is not None
        assert pos.entry_greeks_snapshot.delta == pytest.approx(0.55)

    def test_futures_no_options_snapshot(self):
        pos = _futures_pos()
        assert pos.entry_premium is None
        assert pos.entry_iv is None
        assert pos.entry_dte is None

    def test_tds_zero_on_paper_close(self):
        pos = _options_pos(is_paper=True)
        closed = ps.close_position(
            pos.id, exit_spot_price=51_000.0, exit_premium=1_750.0,
        )
        assert closed.tds_withheld_usd == pytest.approx(0.0)


# ─── 4. Greeks math ────────────────────────────────────────────────────


class TestGreeksMath:
    def test_bsm_greeks_full_returns_five_greeks(self):
        g = bsm_greeks_full(
            S=50_000, K=50_000, T=30/365.0, r=0.0, sigma=0.65, is_call=True,
        )
        # All five non-zero for an ATM 30-DTE call.
        assert g.delta == pytest.approx(0.5371, abs=0.01)
        assert g.gamma > 0
        assert g.vega > 0
        assert g.theta < 0
        assert g.rho > 0

    def test_bsm_greeks_backcompat(self):
        """bsm_greeks must return the same delta/vega/theta as bsm_greeks_full."""
        a = bsm_greeks(S=50_000, K=50_000, T=30/365, r=0, sigma=0.65, is_call=True)
        b = bsm_greeks_full(S=50_000, K=50_000, T=30/365, r=0, sigma=0.65, is_call=True)
        assert a.delta == b.delta
        assert a.vega == b.vega
        assert a.theta == b.theta

    def test_bsm_greeks_degenerate_inputs_return_zeros(self):
        # T=0 → expired option
        g = bsm_greeks_full(50_000, 50_000, 0.0, 0.0, 0.65, True)
        assert g.delta == 0.0 and g.gamma == 0.0
        # sigma=0
        g = bsm_greeks_full(50_000, 50_000, 30/365, 0.0, 0.0, True)
        assert g.delta == 0.0


# ─── 5. GreeksBudgetChecker with gamma cap ─────────────────────────────


class TestGreeksBudgetChecker:
    def _checker(self, pv: float = 100_000.0):
        return GreeksBudgetChecker(GreeksBudget(), portfolio_value=pv)

    def test_delta_breach_rejects(self):
        c = self._checker()
        new_g = PositionGreeks(delta=1.0, vega=0.01, theta=-0.001, gamma=0.001)
        ok, reason = c.check([], new_g, new_position_notional=50_000.0)
        assert not ok
        assert "delta_breach" in reason

    def test_gamma_breach_rejects(self):
        """New cap added in Phase 0 — gamma was previously unbounded."""
        c = self._checker()
        new_g = PositionGreeks(delta=0.1, vega=0.01, theta=-0.001, gamma=0.5)
        ok, reason = c.check([], new_g, new_position_notional=20_000.0)
        assert not ok
        assert "gamma_breach" in reason

    def test_vega_breach_rejects(self):
        c = self._checker()
        new_g = PositionGreeks(delta=0.05, vega=1.0, theta=-0.001, gamma=0.0001)
        ok, reason = c.check([], new_g, new_position_notional=30_000.0)
        assert not ok
        assert "vega_breach" in reason

    def test_small_order_within_budget_passes(self):
        c = self._checker()
        new_g = PositionGreeks(delta=0.5, vega=0.01, theta=-0.0005, gamma=0.00005)
        ok, reason = c.check([], new_g, new_position_notional=5_000.0)
        assert ok and reason == "ok"

    def test_legacy_positions_without_gamma_default_zero(self):
        c = self._checker()
        legacy = _GreeksAndNotional(
            greeks=PositionGreeks(delta=0.3, vega=0.01, theta=-0.001),  # no gamma
            notional=10_000.0,
        )
        new_g = PositionGreeks(delta=0.2, vega=0.01, theta=-0.0005, gamma=0.0001)
        ok, _ = c.check([legacy], new_g, new_position_notional=20_000.0)
        assert ok                                  # legacy gamma defaults to 0


# ─── 6. portfolio_greeks_aggregator ────────────────────────────────────


class TestPortfolioGreeksAggregator:
    def test_refresh_futures_long_returns_delta_one(self):
        pos = _futures_pos(direction=Direction.LONG)
        g = refresh_position_greeks(pos, current_spot=100_000.0)
        assert g.delta == pytest.approx(1.0)
        assert g.gamma == 0.0 and g.vega == 0.0 and g.theta == 0.0

    def test_refresh_futures_short_returns_delta_minus_one(self):
        pos = _futures_pos(direction=Direction.SHORT)
        g = refresh_position_greeks(pos, current_spot=100_000.0)
        assert g.delta == pytest.approx(-1.0)

    def test_refresh_option_bsm_at_current_spot(self):
        pos = _options_pos(spot=50_000.0, strike=50_000.0, iv=0.65, dte=10)
        # When spot is higher than strike, delta should rise above the entry's 0.55.
        g = refresh_position_greeks(pos, current_spot=52_000.0, iv_override=0.65)
        assert g.delta > 0.55

    def test_refresh_option_no_iv_falls_back_to_snapshot(self):
        pos = _options_pos()
        # Force entry_iv to 0 — should hit the snapshot fallback.
        pos.entry_iv = 0.0
        g = refresh_position_greeks(pos, current_spot=50_000.0)
        # Snapshot delta was 0.55.
        assert g.delta == pytest.approx(0.55)

    def test_parse_option_symbol_valid(self):
        parsed = _parse_option_symbol("C-BTC-50000-310525")
        assert parsed is not None
        assert parsed["option_type"] == "call"
        assert parsed["strike"] == 50_000.0
        assert parsed["expiry"] == "310525"
        assert parsed["is_call"] is True

    def test_parse_option_symbol_put(self):
        parsed = _parse_option_symbol("P-ETH-3200-280625")
        assert parsed is not None
        assert parsed["is_call"] is False

    def test_parse_option_symbol_bad_returns_none(self):
        assert _parse_option_symbol("not-a-symbol") is None
        assert _parse_option_symbol("X-BTC-50000-310525") is None
        assert _parse_option_symbol("") is None


# ─── 7. OrderRouter — greeks_budget_gate hard reject ───────────────────


@dataclass
class _FakeInst:
    underlying: str = "BTC"
    delta_perp_symbol: str = "BTCUSD"


def _resolve(_sym: str) -> _FakeInst:
    return _FakeInst()


def _adapter(idx_price: float = 50_000.0) -> AsyncMock:
    m = AsyncMock()
    m.get_index_price.return_value = idx_price
    m.get_product_id.return_value = 27
    m.set_leverage.return_value = None
    m.set_margin_mode.return_value = None
    m.place_order.return_value = {"id": "ORD123", "average_fill_price": 50_001.5}
    return m


@pytest.mark.asyncio
async def test_router_rejects_on_greeks_budget_breach():
    async def gate(_req, _positions):
        return "delta_breach:35%>30%"
    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
        greeks_budget_gate=gate,
    )
    r = OrderRouter(mode=RouterMode.LIVE, adapter=_adapter(), deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert not resp.accepted
    assert resp.code == "greeks_budget_breach"
    assert "delta_breach:35%>30%" in resp.reason


@pytest.mark.asyncio
async def test_router_proceeds_when_gate_returns_none():
    async def gate(_req, _positions):
        return None
    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
        greeks_budget_gate=gate,
    )
    ad = _adapter()
    r = OrderRouter(mode=RouterMode.LIVE, adapter=ad, deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert resp.accepted and resp.status == "filled"


@pytest.mark.asyncio
async def test_paper_mode_skips_greeks_gate():
    """Paper mode must NOT consult the gate — paper is for learning."""
    calls = []
    async def gate(_req, _positions):
        calls.append("called")
        return "delta_breach:99%>30%"
    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
        greeks_budget_gate=gate,
    )
    r = OrderRouter(mode=RouterMode.PAPER, adapter=_adapter(), deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert resp.accepted                            # paper accepts unconditionally
    assert calls == []                              # gate never called in paper


# ─── 8. OrderRouter — set_margin_mode("isolated") before set_leverage ──


@pytest.mark.asyncio
async def test_isolated_margin_set_before_leverage():
    ad = AsyncMock()
    ad.get_index_price.return_value = 50_000.0
    ad.get_product_id.return_value = 27
    ad.set_margin_mode.return_value = None
    ad.set_leverage.return_value = None
    ad.place_order.return_value = {"id": "OID", "average_fill_price": 50_000.0}

    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
    )
    r = OrderRouter(mode=RouterMode.LIVE, adapter=ad, deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0, leverage=5.0,
                             client_order_id=_coid())
    await r.submit(req)
    # mock_calls records every method invocation in chronological order;
    # filter to just the two we care about to verify the call sequence.
    sequence = [c[0] for c in ad.mock_calls if c[0] in ("set_margin_mode", "set_leverage")]
    assert sequence == ["set_margin_mode", "set_leverage"]
    # And both must have been called exactly once.
    ad.set_margin_mode.assert_called_once_with(27, "isolated")
    ad.set_leverage.assert_called_once()


@pytest.mark.asyncio
async def test_margin_mode_failure_does_not_block_order():
    """If the exchange doesn't support isolated margin for this product,
    the order must still proceed (fall through to cross). Non-fatal."""
    ad = AsyncMock()
    ad.get_index_price.return_value = 50_000.0
    ad.get_product_id.return_value = 27
    ad.set_margin_mode.side_effect = RuntimeError("isolated not supported")
    ad.set_leverage.return_value = None
    ad.place_order.return_value = {"id": "OID", "average_fill_price": 50_000.0}

    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
    )
    r = OrderRouter(mode=RouterMode.LIVE, adapter=ad, deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert resp.accepted


# ─── 9. OrderRouter — correlation_penalty preserves fractional ─────────


@pytest.mark.asyncio
async def test_correlation_penalty_preserves_fractional_size():
    """Pre-Phase-0 a 0.7 penalty on a 1-contract request silently rounded
    to 1.0 (the integer floor) — a 43% size error on high-notional
    options. The fix preserves fractional sizes; only sub-0.01 contract
    sizes reject."""
    captured: dict = {}
    ad = AsyncMock()
    ad.get_index_price.return_value = 50_000.0
    ad.get_product_id.return_value = 27
    ad.set_leverage.return_value = None
    ad.set_margin_mode.return_value = None
    async def _po(**kwargs):
        captured["size"] = kwargs.get("size")
        return {"id": "OID", "average_fill_price": 50_000.0}
    ad.place_order.side_effect = _po

    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
        correlation_penalty=lambda *a, **k: 0.7,    # 30% size haircut
    )
    r = OrderRouter(mode=RouterMode.LIVE, adapter=ad, deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert resp.accepted
    assert captured["size"] == pytest.approx(0.7, abs=0.01)


@pytest.mark.asyncio
async def test_correlation_penalty_rejects_below_floor():
    """A penalty that drives size below 0.01 contracts still rejects."""
    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *a, **k: "PP",
        correlation_penalty=lambda *a, **k: 0.001,   # crushes size to 0.001
    )
    r = OrderRouter(mode=RouterMode.LIVE, adapter=_adapter(), deps=deps,
                    instrument_resolver=_resolve)
    req = OrderRouterRequest(underlying="BTC", direction="long",
                             instrument_type="futures", size=1.0,
                             client_order_id=_coid())
    resp = await r.submit(req)
    assert not resp.accepted
    assert resp.code == "correlation_size_zero"


# ─── 10. TradingModeConfig — new force_close field present ─────────────


def test_trading_mode_force_close_minutes_field_present():
    from app.core.trading_mode import MODES
    for name, mode in MODES.items():
        assert hasattr(mode, "force_close_minutes_before_expiry"), (
            f"mode {name} missing force_close_minutes_before_expiry"
        )
        assert mode.force_close_minutes_before_expiry == 120
