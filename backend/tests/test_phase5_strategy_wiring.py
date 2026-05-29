"""Phase-5 derivatives-build correctness tests — strategy execute wiring.

Locks in the per-strategy feature-flag rollout:
  • paper_store.close_position records exit PnL on the derivatives_audit
    entry when the position's notes carry a [DERIV-aid=...] tag.
  • Scalping and triple_st execute paths fall back to the legacy futures
    path when no selector profile is enabled (default).
"""
from __future__ import annotations

import time

import pytest

from app.engines.derivatives.freeze_token import get_store as get_freeze_store
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesCandidate, DerivativesDecision, MarketContext, SignalContext,
)
from app.schemas.directional import Direction
from app.schemas.execution import CandidateContract, SizedTrade, TradeStructure
from app.services import derivatives_audit
from app.services import paper_store as ps


@pytest.fixture(autouse=True)
def _reset():
    from app.engines.risk import cooldown
    from app.services import live_safety
    cooldown.clear()
    live_safety.reset_all_for_tests()
    get_freeze_store().clear()
    derivatives_audit.clear_for_tests()
    yield
    cooldown.clear()
    live_safety.reset_all_for_tests()
    get_freeze_store().clear()
    derivatives_audit.clear_for_tests()


# ─── close_position audit feedback loop ────────────────────────────────


class TestCloseFillsAudit:
    def _futures_position(self, notes: str):
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
            leverage=5, entry_price=50_000.0,
        )
        sized = SizedTrade(structure=struct, contracts=1,
                           position_value=50_000, max_risk_usd=500,
                           capital_at_risk_pct=0.01)
        return ps.add_position(
            underlying="BTC", sized_trade=sized,
            entry_spot_price=50_000.0, is_paper=True, notes=notes,
        )

    def test_audit_exit_pnl_recorded_on_close_with_tag(self):
        # Pre-seed an audit entry whose short id (first 8 chars) gets stamped
        # in the position notes — mimics what the scalping/strategy wiring does.
        sig = SignalContext(strategy="triple_st", underlying="BTC", direction="long",
                            entry=50_000, stop_loss=49_000, take_profit=52_000)
        mkt = MarketContext(spot=50_000, underlying="BTC", portfolio_value=100_000)
        class _Dec:
            class status:
                value = "ok"
            chosen = None
        aid = derivatives_audit.record(decision=_Dec(), signal=sig, market=mkt)
        short = aid[:8]
        notes = f"[RSI2-MEANREV] long [DERIV-aid={short}]"

        pos = self._futures_position(notes)
        closed = ps.close_position(pos.id, exit_spot_price=50_500.0)
        assert closed is not None
        # Confirm the audit row got record_exit
        rows = derivatives_audit.list_recent()
        match = [r for r in rows if r["audit_id"] == aid]
        assert len(match) == 1
        assert match[0]["exit_pnl"] is not None
        assert match[0]["exit_pnl"] == closed.realized_pnl_usd

    def test_close_without_tag_skips_audit(self):
        pos = self._futures_position("[SCALP-PRICE_ACTION] long")
        closed = ps.close_position(pos.id, exit_spot_price=50_500.0)
        assert closed is not None
        # No audit rows were touched
        assert derivatives_audit.list_recent() == []

    def test_close_with_invalid_tag_doesnt_crash(self):
        # Tag references a non-existent audit_id — must not raise
        pos = self._futures_position("[RSI2-MEANREV] long [DERIV-aid=deadbeef]")
        closed = ps.close_position(pos.id, exit_spot_price=50_500.0)
        assert closed is not None


# ─── selector profile resolution at execute callsites ────────────────


class TestProfileGating:
    """We don't drive the full /scalping/execute path here (that needs the
    whole app stack); instead we verify the selector returns the expected
    DecisionStatus that the wiring branches on."""

    def test_disabled_profile_returns_profile_off(self):
        from app.engines.derivatives.selector import decide
        sig = SignalContext(strategy="scalping/price_action", underlying="BTC",
                            direction="long", entry=50_000, stop_loss=49_500,
                            take_profit=51_000)
        mkt = MarketContext(spot=50_000, underlying="BTC", portfolio_value=100_000)
        # No overrides → uses default DEFAULT_PROFILES which has enabled=False
        d = decide(signal=sig, market=mkt, chain=None)
        assert d.status == DecisionStatus.PROFILE_OFF

    def test_enabled_profile_returns_ok(self):
        from app.engines.derivatives.selector import decide
        from app.engines.derivatives.profiles import DEFAULT_PROFILES
        sig = SignalContext(strategy="triple_st", underlying="BTC",
                            direction="long", entry=50_000, stop_loss=49_000,
                            take_profit=53_000, atr=1_000, rr_target=2.0,
                            signal_score=75, signal_strength="STRONG",
                            expected_hold_minutes=5 * 24 * 60, mode_name="swing")
        mkt = MarketContext(spot=50_000, underlying="BTC",
                            portfolio_value=100_000, win_rate=0.6, avg_R=1.5,
                            cb_size_mult=1.0)
        override = DEFAULT_PROFILES["triple_st"].model_copy(update={"enabled": True})
        d = decide(signal=sig, market=mkt, chain=None,
                   profile_overrides={"triple_st": override})
        assert d.status == DecisionStatus.OK
        assert d.chosen is not None
        # No chain → futures only
        assert d.chosen.instrument_type == "futures"


# ─── selector-stamped notes propagate through paper_store ─────────────


class TestNotesTagging:
    def test_notes_with_deriv_tag_persisted(self):
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
            leverage=5, entry_price=50_000.0,
        )
        sized = SizedTrade(structure=struct, contracts=1,
                           position_value=50_000, max_risk_usd=500,
                           capital_at_risk_pct=0.01)
        pos = ps.add_position(
            underlying="BTC", sized_trade=sized,
            entry_spot_price=50_000.0, is_paper=True,
            notes="[SCALP-PRICE_ACTION] long [DERIV-aid=12345678]",
        )
        roundtrip = ps.get_position(pos.id)
        assert "[DERIV-aid=12345678]" in roundtrip.notes
