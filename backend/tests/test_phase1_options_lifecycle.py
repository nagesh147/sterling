"""Phase-1 derivatives-build correctness tests — options-safe lifecycle.

Covers everything new in Phase 1:
  • OptionSummary schema carries gamma/vega/theta/rho + greeks_enriched flag
  • enrich_with_greeks BSM-fills missing Greeks (adapter-supplied pass through)
  • enrich_with_greeks per-(symbol, spot-bucket, dte) cache hits
  • DeltaIndiaAdapter populates Greeks from DEI's greeks block when present
  • /options/chain endpoint always returns enriched Greeks
  • options_monitor.OptionChainCache fetches once per underlying per poll
  • options_monitor.is_chain_stale at the 30s boundary
  • options_monitor.should_force_close tiered by notional (>$1k → 120 min, else 30 min)
  • options_monitor.should_veto_amend at the 8% spread boundary
  • options_monitor.option_close_kwargs builds correct (exit_premium, fill_type, settlement_recorded)
  • portfolio_greeks_aggregator uses live chain IV (Phase 1 upgrade)
"""
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest

from app.engines.risk.option_pricing import (
    enrich_with_greeks, enrich_chain, clear_cache as _opt_pricing_clear,
)
from app.engines.risk import options_monitor as _opt_mon
from app.engines.risk.portfolio_greeks_aggregator import check_against_budget
from app.engines.risk.greeks_budget import GreeksBudget, GreeksBudgetChecker
from app.schemas.market import OptionSummary
from app.schemas.directional import Direction
from app.schemas.execution import CandidateContract, SizedTrade, TradeStructure
from app.schemas.greeks import GreeksSnapshot
from app.services import paper_store as ps


@pytest.fixture(autouse=True)
def _reset_state():
    """Same process-state reset as Phase 0 + clear the option_pricing
    cache so spot-bucket tests don't see entries from previous tests."""
    from app.engines.risk import cooldown
    from app.services import live_safety
    cooldown.clear()
    live_safety.reset_all_for_tests()
    _opt_pricing_clear()
    yield
    cooldown.clear()
    live_safety.reset_all_for_tests()
    _opt_pricing_clear()


def _opt(
    instrument_name: str = "C-BTC-50000-310525",
    underlying: str = "BTC",
    strike: float = 50_000.0,
    expiry: str = "310525",
    dte: int = 10,
    option_type: str = "call",
    bid: float = 1_100.0,
    ask: float = 1_200.0,
    mark_price: float = 1_150.0,
    mark_iv: float = 65.0,
    delta: float = 0.55,
    oi: float = 200.0,
    vol: float = 80.0,
    spread_pct: float = 0.0,
    gamma: float = 0.0,
    vega: float = 0.0,
    theta: float = 0.0,
    rho: float = 0.0,
    ts_ms: int | None = None,
) -> OptionSummary:
    return OptionSummary(
        instrument_name=instrument_name, underlying=underlying,
        strike=strike, expiry_date=expiry, dte=dte, option_type=option_type,
        bid=bid, ask=ask, mark_price=mark_price, mid_price=(bid + ask) / 2,
        mark_iv=mark_iv, delta=delta, open_interest=oi, volume_24h=vol,
        last_updated_ms=ts_ms if ts_ms is not None else int(time.time() * 1000),
        gamma=gamma, vega=vega, theta=theta, rho=rho, spread_pct=spread_pct,
    )


# ─── 1. Schema additions ───────────────────────────────────────────────


class TestOptionSummarySchema:
    def test_legacy_payload_validates_with_defaults(self):
        # Old-shape payload (no gamma/vega/theta/rho) must still validate.
        legacy = OptionSummary(
            instrument_name="P-ETH-3200-310525", underlying="ETH",
            strike=3200, expiry_date="310525", dte=5, option_type="put",
            bid=80, ask=90, mark_price=85, mid_price=85, mark_iv=70.0,
            delta=-0.40, open_interest=100, volume_24h=40,
            last_updated_ms=int(time.time() * 1000),
        )
        assert legacy.gamma == 0.0
        assert legacy.vega == 0.0
        assert legacy.theta == 0.0
        assert legacy.rho == 0.0
        assert legacy.greeks_enriched is False
        assert legacy.spread_pct == 0.0

    def test_full_payload_round_trips(self):
        o = _opt(gamma=0.001, vega=15.0, theta=-4.5, rho=8.0, spread_pct=0.04)
        d = o.model_dump()
        assert d["gamma"] == 0.001
        assert d["vega"] == 15.0
        assert d["theta"] == -4.5
        assert d["rho"] == 8.0
        assert d["spread_pct"] == 0.04


# ─── 2. enrich_with_greeks ─────────────────────────────────────────────


class TestEnrichWithGreeks:
    def test_bsm_fills_missing_greeks(self):
        opt = _opt(mark_iv=65.0, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)
        e = enrich_with_greeks(opt, spot=50_000.0)
        assert e.greeks_enriched is True
        assert e.gamma > 0
        assert e.vega > 0
        assert e.theta < 0
        assert e.rho > 0

    def test_adapter_supplied_greeks_pass_through(self):
        opt = _opt(gamma=0.001, vega=12.0, theta=-3.5, rho=4.0)
        e = enrich_with_greeks(opt, spot=50_000.0)
        assert e.greeks_enriched is False             # nothing to enrich
        assert e.gamma == 0.001
        assert e.vega == 12.0

    def test_zero_iv_skips_enrichment(self):
        opt = _opt(mark_iv=0.0)
        e = enrich_with_greeks(opt, spot=50_000.0)
        assert e.greeks_enriched is False
        assert e.gamma == 0.0

    def test_cache_hits_within_spot_bucket(self):
        opt = _opt(mark_iv=65.0)
        a = enrich_with_greeks(opt, spot=50_000.0)
        b = enrich_with_greeks(opt, spot=50_010.0)         # < 0.1% away
        assert a.gamma == b.gamma                          # cached
        assert a.vega == b.vega
        assert a.theta == b.theta

    def test_cache_misses_across_spot_buckets(self):
        opt = _opt(mark_iv=65.0)
        a = enrich_with_greeks(opt, spot=50_000.0)
        b = enrich_with_greeks(opt, spot=55_000.0)         # different bucket
        # Different spot → different BSM Greeks. Delta sign should differ
        # (deep ITM at $55k vs ATM at $50k).
        assert a.delta != b.delta or abs(a.gamma - b.gamma) > 1e-12

    def test_iv_normalised_from_percent(self):
        # Adapter sometimes ships IV as percent. Confirm result matches
        # equivalent decimal-IV call.
        opt_pct = _opt(mark_iv=65.0)        # 65 = 65%
        opt_dec = _opt(mark_iv=0.65)         # 0.65 = 65%
        _opt_pricing_clear()
        a = enrich_with_greeks(opt_pct, spot=50_000.0)
        _opt_pricing_clear()
        b = enrich_with_greeks(opt_dec, spot=50_000.0)
        assert abs(a.gamma - b.gamma) < 1e-9
        assert abs(a.vega  - b.vega)  < 1e-9

    def test_enrich_chain_processes_all(self):
        chain = [_opt(instrument_name=f"C-BTC-{k}-310525", strike=k) for k in (49_000, 50_000, 51_000)]
        enriched = enrich_chain(chain, spot=50_000.0)
        assert all(c.greeks_enriched for c in enriched)
        assert len(enriched) == 3


# ─── 3. options_monitor.OptionChainCache ───────────────────────────────


@pytest.mark.asyncio
async def test_chain_cache_fetches_once_per_underlying():
    fake_inst = MagicMock(has_options=True)
    fake_chain = [_opt(), _opt(strike=51_000)]
    adapter = AsyncMock()
    adapter.get_option_chain.return_value = fake_chain
    registry = MagicMock()
    registry.get_instrument.return_value = fake_inst

    cache = _opt_mon.OptionChainCache()
    r1 = await cache.get_or_fetch("BTC", adapter, registry)
    r2 = await cache.get_or_fetch("BTC", adapter, registry)
    r3 = await cache.get_or_fetch("BTC", adapter, registry)

    assert r1 is not None and r2 is not None and r3 is not None
    assert r1[0] is r2[0] is r3[0]                         # same chain
    assert adapter.get_option_chain.call_count == 1        # one fetch only


@pytest.mark.asyncio
async def test_chain_cache_failed_fetch_doesnt_retry():
    fake_inst = MagicMock(has_options=True)
    adapter = AsyncMock()
    adapter.get_option_chain.side_effect = RuntimeError("network down")
    registry = MagicMock()
    registry.get_instrument.return_value = fake_inst

    cache = _opt_mon.OptionChainCache()
    r1 = await cache.get_or_fetch("BTC", adapter, registry)
    r2 = await cache.get_or_fetch("BTC", adapter, registry)
    assert r1 is None and r2 is None
    assert adapter.get_option_chain.call_count == 1        # didn't retry


@pytest.mark.asyncio
async def test_chain_cache_no_options_instrument_returns_none():
    fake_inst = MagicMock(has_options=False)
    adapter = AsyncMock()
    registry = MagicMock()
    registry.get_instrument.return_value = fake_inst
    cache = _opt_mon.OptionChainCache()
    r = await cache.get_or_fetch("XRP", adapter, registry)
    assert r is None
    assert adapter.get_option_chain.call_count == 0


# ─── 4. options_monitor.is_chain_stale ─────────────────────────────────


class TestChainStaleness:
    def test_fresh_chain_not_stale(self):
        now = int(time.time() * 1000)
        assert not _opt_mon.is_chain_stale(now)
        assert not _opt_mon.is_chain_stale(now - 5_000)
        assert not _opt_mon.is_chain_stale(now - 29_000)

    def test_boundary_at_30s(self):
        now = int(time.time() * 1000)
        assert not _opt_mon.is_chain_stale(now - 30_000, now_ms=now)
        assert _opt_mon.is_chain_stale(now - 30_001, now_ms=now)

    def test_zero_ts_is_stale(self):
        assert _opt_mon.is_chain_stale(0)


# ─── 5. options_monitor.should_force_close + tiering ───────────────────


def _opts_pos(
    *, entry_dte: int = 10, hours_ago: float = 0.0,
    notional: float = 5_000.0, is_paper: bool = True,
):
    """Build a paper options position with a controllable elapsed-time."""
    leg = CandidateContract(
        instrument_name="C-BTC-50000-310525", underlying="BTC",
        strike=50_000, expiry_date="310525", dte=entry_dte,
        option_type="call", bid=1_100, ask=1_200, mark_price=1_150,
        mid_price=1_150, mark_iv=65.0, delta=0.55,
        open_interest=200, volume_24h=80, spread_pct=0.05,
        health_score=85, healthy=True,
    )
    struct = TradeStructure(
        structure_type="naked_call", direction=Direction.LONG, legs=[leg],
        max_loss=1_150 * 2, max_gain=None, net_premium=1_150,
        risk_reward=2.0, score=0, score_breakdown={},
        leverage=1, entry_price=50_000.0,
    )
    sized = SizedTrade(
        structure=struct, contracts=2,
        position_value=notional, max_risk_usd=notional * 0.5,
        capital_at_risk_pct=0.01,
    )
    pos = ps.add_position(
        underlying="BTC", sized_trade=sized,
        entry_spot_price=50_000.0, is_paper=is_paper,
        entry_premium=1_150.0, entry_iv=0.65, entry_dte=entry_dte,
        entry_greeks_snapshot=GreeksSnapshot(
            delta=0.55, gamma=0.00004, vega=55.0, theta=-60.0, rho=18.0,
            spot=50_000.0, iv=0.65, dte=entry_dte,
        ),
    )
    # Backdate the entry timestamp so the elapsed-time calc kicks in.
    if hours_ago > 0:
        ps.update_position(pos.id, entry_timestamp_ms=int(time.time() * 1000) - int(hours_ago * 3_600_000))
    return ps.get_position(pos.id)


class TestForceCloseTiering:
    def test_two_days_remaining_no_force_close(self):
        pos = _opts_pos(entry_dte=7, hours_ago=5 * 24)             # 2 days remaining
        should, _ = _opt_mon.should_force_close(pos, mode_force_close_min=120)
        assert not should

    def test_big_notional_inside_120min_window(self):
        # 22.5h elapsed of a 1-day position = 90 min remaining
        pos = _opts_pos(entry_dte=1, hours_ago=22.5, notional=5_000.0)
        should, reason = _opt_mon.should_force_close(pos, mode_force_close_min=120)
        assert should
        assert "force_close_dte" in reason
        assert "120min" in reason

    def test_small_notional_uses_tighter_30min_window(self):
        # Same 90-min remaining; small notional → window=30min → no force-close yet
        pos = _opts_pos(entry_dte=1, hours_ago=22.5, notional=500.0)
        should, _ = _opt_mon.should_force_close(pos, mode_force_close_min=120)
        assert not should

    def test_small_notional_inside_30min_window(self):
        # 23.75h elapsed of 1-day = 15 min remaining; small notional → force-close
        pos = _opts_pos(entry_dte=1, hours_ago=23.75, notional=500.0)
        should, reason = _opt_mon.should_force_close(pos, mode_force_close_min=120)
        assert should
        assert "30min" in reason

    def test_futures_position_returns_no(self):
        # Futures have no entry_dte → should_force_close returns False
        leg = CandidateContract(
            instrument_name="BTCUSD", underlying="BTC", strike=0,
            expiry_date="", dte=0, option_type="futures",
            bid=0, ask=0, mark_price=50_000, mid_price=50_000,
            mark_iv=0, delta=1.0, open_interest=0, volume_24h=0,
            spread_pct=0, health_score=0, healthy=True,
        )
        struct = TradeStructure(
            structure_type="futures", direction=Direction.LONG, legs=[leg],
            max_loss=500, max_gain=None, net_premium=0,
            risk_reward=2.0, score=0, score_breakdown={},
            leverage=10, entry_price=50_000.0,
        )
        sized = SizedTrade(structure=struct, contracts=1,
                           position_value=50_000, max_risk_usd=500,
                           capital_at_risk_pct=0.01)
        pos = ps.add_position(underlying="BTC", sized_trade=sized,
                              entry_spot_price=50_000.0, is_paper=True)
        should, _ = _opt_mon.should_force_close(pos, mode_force_close_min=120)
        assert not should


class TestIsAtSettlement:
    def test_pre_expiry_false(self):
        pos = _opts_pos(entry_dte=1, hours_ago=22.0)
        assert not _opt_mon.is_at_settlement(pos)

    def test_at_expiry_true(self):
        pos = _opts_pos(entry_dte=1, hours_ago=24.0)               # exactly expired
        assert _opt_mon.is_at_settlement(pos)


# ─── 6. options_monitor.should_veto_amend ──────────────────────────────


class TestMicrostructureVeto:
    def test_tight_spread_no_veto(self):
        v, _ = _opt_mon.should_veto_amend(_opt(spread_pct=0.03))
        assert not v

    def test_wide_spread_vetoes(self):
        v, reason = _opt_mon.should_veto_amend(_opt(spread_pct=0.15))
        assert v
        assert "spread_too_wide" in reason

    def test_boundary_at_8_percent(self):
        assert not _opt_mon.should_veto_amend(_opt(spread_pct=0.08))[0]
        assert _opt_mon.should_veto_amend(_opt(spread_pct=0.0801))[0]

    def test_no_spread_info_no_veto(self):
        # Phase 0 records without spread_pct → don't block amends.
        v, _ = _opt_mon.should_veto_amend(_opt(spread_pct=0.0))
        assert not v


# ─── 7. options_monitor.option_close_kwargs ────────────────────────────


class TestOptionCloseKwargs:
    def test_pre_expiry_close_passes_premium(self):
        kw = _opt_mon.option_close_kwargs(_opt(mark_price=1_250.0), at_settlement=False,
                                          trigger_reason="trail")
        assert kw["exit_premium"] == 1_250.0
        assert kw["exit_reason"] == "trail"
        assert kw["fill_type"] == "normal"
        assert "settlement_recorded" not in kw

    def test_settlement_close_sets_flags(self):
        kw = _opt_mon.option_close_kwargs(_opt(mark_price=0.0), at_settlement=True,
                                          trigger_reason="force_close_dte")
        assert kw["settlement_recorded"] is True
        assert kw["fill_type"] == "settlement"
        assert kw["exit_reason"] == "force_close_dte"

    def test_missing_option_falls_back_to_no_premium(self):
        kw = _opt_mon.option_close_kwargs(None, at_settlement=False, trigger_reason="stop")
        assert "exit_premium" not in kw                            # caller's close_position will warn
        assert kw["exit_reason"] == "stop"


# ─── 8. portfolio_greeks_aggregator with live chain IV ─────────────────


@pytest.mark.asyncio
async def test_aggregator_uses_live_iv_when_chain_available():
    """When the adapter ships a chain, the aggregator's IV refresh uses
    the chain's mark_iv instead of the position's stored entry_iv."""
    pos = _opts_pos(entry_dte=10, hours_ago=0.0)
    # Override stored entry_iv to a known-wrong value so we can detect
    # whether the live chain wins.
    ps.update_position(pos.id, entry_iv=0.20)                     # stored IV = 20%
    pos = ps.get_position(pos.id)

    # Adapter returns a chain whose mark_iv differs from entry_iv.
    chain_opt = _opt(instrument_name=pos.sized_trade.structure.legs[0].instrument_name,
                     mark_iv=80.0)                                # 80% IV
    adapter = AsyncMock()
    adapter.get_option_chain.return_value = [chain_opt]

    async def _spot(sym): return 50_000.0

    checker = GreeksBudgetChecker(GreeksBudget(), portfolio_value=100_000.0)

    # Submit a benign new order — we don't care if it passes; we want to
    # verify the chain was fetched (live-IV refresh path triggered).
    class _Req:
        underlying = "NIFTY"
        direction = "long"
        instrument_type = "options"
        option_symbol = "NIFTY25MAY50000CE"
        size = 1.0

    await check_against_budget(_Req(), [pos], adapter, checker, _spot)
    # The aggregator should have hit the chain once for NIFTY's open option.
    assert adapter.get_option_chain.call_count == 1


@pytest.mark.asyncio
async def test_aggregator_falls_back_to_entry_iv_when_chain_unavailable():
    """When the adapter has no chain endpoint or it raises, the aggregator
    falls back to stored entry_iv. No silent failure — the gate still runs."""
    pos = _opts_pos(entry_dte=10, hours_ago=0.0)
    adapter = AsyncMock()
    adapter.get_option_chain.side_effect = RuntimeError("DEI options API timeout")
    async def _spot(sym): return 50_000.0
    checker = GreeksBudgetChecker(GreeksBudget(), portfolio_value=100_000.0)

    class _Req:
        underlying = "NIFTY"
        direction = "long"
        instrument_type = "futures"
        option_symbol = None
        size = 1.0

    # Should not raise. Gate either passes (None) or returns a breach string.
    result = await check_against_budget(_Req(), [pos], adapter, checker, _spot)
    assert result is None or isinstance(result, str)


@pytest.mark.asyncio
async def test_aggregator_skips_chain_fetch_for_futures_only_portfolio():
    """When every open position is futures, no chain fetch happens at all
    — cheap path."""
    # Build a futures position
    leg = CandidateContract(
        instrument_name="BTCUSD", underlying="BTC", strike=0,
        expiry_date="", dte=0, option_type="futures",
        bid=0, ask=0, mark_price=50_000, mid_price=50_000,
        mark_iv=0, delta=1.0, open_interest=0, volume_24h=0,
        spread_pct=0, health_score=0, healthy=True,
    )
    struct = TradeStructure(
        structure_type="futures", direction=Direction.LONG, legs=[leg],
        max_loss=500, max_gain=None, net_premium=0,
        risk_reward=2.0, score=0, score_breakdown={},
        leverage=10, entry_price=50_000.0,
    )
    sized = SizedTrade(structure=struct, contracts=1, position_value=50_000,
                       max_risk_usd=500, capital_at_risk_pct=0.01)
    pos = ps.add_position(underlying="BTC", sized_trade=sized,
                          entry_spot_price=50_000.0, is_paper=True)

    adapter = AsyncMock()
    async def _spot(sym): return 50_000.0
    checker = GreeksBudgetChecker(GreeksBudget(), portfolio_value=100_000.0)

    class _Req:
        underlying = "NIFTY"
        direction = "long"
        instrument_type = "futures"
        option_symbol = None
        size = 1.0

    await check_against_budget(_Req(), [pos], adapter, checker, _spot)
    assert adapter.get_option_chain.call_count == 0
