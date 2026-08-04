"""Signal detail must resolve rows from BOTH engines.

Navigator is a peer engine with its own snapshot. Its originated rows never
pass through the Kite engine's scanner, and when the SuperTrend engine is
switched off that scanner holds nothing at all — so a detail lookup that only
consults the scanner 404s on a board the user can plainly see.
"""
from __future__ import annotations

import pytest

from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.services.kite_engine import detail as detail_service
from app.services.kite_engine.scanner import scanner
from app.services.navigator import runtime as navigator_runtime

_TS = 1_753_000_000_000


class FakeClient:
    """No legs on these rows, so only the underlying LTP is ever requested."""

    async def get_ltp(self, symbols):
        return {symbols[0]: {"last_price": 24_600.0}}

    async def get_quote(self, symbols):  # pragma: no cover - no legs in these rows
        return {}


def _nav_row(token=256265, timestamp_ms=_TS, **updates):
    row = EngineSignalRow(
        underlying="NIFTY 50", token=token, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=0, mid=0, slow=0),
        direction="long", option_type="CE", legs=[],
        spot=24_500.0, underlying_spot=24_500.0, stop_loss=24_400.0, score=50.0,
        timestamp_ms=timestamp_ms, is_active=True, is_fresh=True, source="navigator",
    )
    return row.model_copy(update=updates)


@pytest.fixture(autouse=True)
def clean_snapshots():
    """Start with an empty scanner — the point is that Navigator answers alone."""
    scanner._users.pop("user-1", None)
    navigator_runtime._snapshots.pop("user-1", None)
    yield
    scanner._users.pop("user-1", None)
    navigator_runtime._snapshots.pop("user-1", None)


class TestNavigatorOwnedDetail:
    @pytest.mark.asyncio
    async def test_navigator_row_resolves_when_the_scanner_has_nothing(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row()]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out is not None
        assert out.underlying == "NIFTY 50"
        assert out.triggered_ms == _TS
        assert out.spot_now == 24_600.0

    @pytest.mark.asyncio
    async def test_prefers_the_clicked_timestamp_but_still_answers_without_it(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row(timestamp_ms=_TS), _nav_row(timestamp_ms=_TS + 3_600_000)]

        exact = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)
        assert exact.triggered_ms == _TS

        # a background scan can regroup the row between click and request — answer
        # with the newest match rather than a misleading 404
        stale = await detail_service.build_detail(FakeClient(), "user-1", 256265, 1)
        assert stale.triggered_ms == _TS + 3_600_000

    @pytest.mark.asyncio
    async def test_unknown_token_is_still_a_miss(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row()]

        assert await detail_service.build_detail(FakeClient(), "user-1", 999_999, _TS) is None


class TestDetailCarriesTheSignalPlan:
    """The dock is opened from a board that mixes both engines. Without the owning
    engine, the exit rule, the target and the per-leg premium plan, the same layout
    describes a SuperTrend trail-and-red-counter trade and a Navigator AVWAP
    stop/target trade identically — and cannot explain the badge the user clicked."""

    @pytest.mark.asyncio
    async def test_navigator_decision_and_plan_reach_the_response(self):
        from app.engines.navigator.schemas import NavigatorDecision

        decision = NavigatorDecision(
            decision_id="nav_test", schema_version=1, config_revision=1, model_versions={},
            generated_at_ms=_TS, bar_close_ms=_TS, activation_watermark_ms=0,
            base_signal_id="origin:NIFTY 50:long", trigger="avwap_fresh", direction="long",
            status="CONFIRMED", base_score=50.0, suite_score=72.0, effective_score=68.0,
            execution_eligible=True, data_quality="ok", reason_codes=["OK"],
        )
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row(navigator=decision, entry_sl=24_400.0, target=24_900.0,
                              exit_state="0/3 red", adx=22.0, atr_pct=61.0)]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out.source == "navigator"
        assert out.navigator is not None and out.navigator.status == "CONFIRMED"
        assert out.entry_sl == 24_400.0
        assert out.target == 24_900.0
        assert out.exit_state == "0/3 red"
        assert out.is_active is True
        assert (out.adx, out.atr_pct) == (22.0, 61.0)

    @pytest.mark.asyncio
    async def test_supertrend_row_reports_no_target_rather_than_a_fabricated_one(self):
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row(source="spot", entry_sl=24_400.0)]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out.source == "spot"
        assert out.target is None
        assert out.navigator is None

    @pytest.mark.asyncio
    async def test_leg_premium_plan_reaches_the_response(self):
        from app.engines.sterling_kite_engine.schemas import OptionLeg

        class LegClient(FakeClient):
            async def get_quote(self, symbols):
                return {symbols[0]: {"last_price": 300.0, "depth": {"buy": [], "sell": []}}}

        leg = OptionLeg(moneyness="ATM", option_type="CE", option_symbol="NIFTY26AUG24500CE",
                        strike=24_500.0, expiry="2026-08-27", lot_size=75, token=9_001,
                        premium_spot=320.0, entry_sl=210.0, premium_sl=255.0,
                        premium_target=540.0, is_active=True)
        snap = navigator_runtime.snapshot("user-1")
        snap.rows = [_nav_row(legs=[leg])]

        out = await detail_service.build_detail(LegClient(), "user-1", 256265, _TS)

        assert len(out.options) == 1
        opt = out.options[0]
        assert (opt.entry_premium, opt.initial_stop_premium) == (320.0, 210.0)
        assert (opt.trail_stop_premium, opt.target_premium) == (255.0, 540.0)
        assert opt.is_active is True


class TestBothEnginesHoldTheSameToken:
    """A Navigator origination is keyed on the underlying's token — the very same
    token every SuperTrend row for that instrument carries. Resolving a click by
    token alone therefore answers with whichever engine's row is found first, and
    the user reads another signal's entry, stop and legs under the row they
    clicked."""

    @staticmethod
    def _engine_row(timestamp_ms=_TS, **updates):
        row = _nav_row(timestamp_ms=timestamp_ms)
        return row.model_copy(update={"source": "spot", "spot": 24_111.0,
                                      "stop_loss": 24_000.0, **updates})

    @pytest.mark.asyncio
    async def test_source_picks_the_engine_that_owns_the_click(self):
        scanner.snapshot("user-1").rows = [self._engine_row()]
        navigator_runtime.snapshot("user-1").rows = [_nav_row()]

        nav = await detail_service.build_detail(
            FakeClient(), "user-1", 256265, _TS, source="navigator")
        engine = await detail_service.build_detail(
            FakeClient(), "user-1", 256265, _TS, source="spot")

        assert nav.source == "navigator"
        assert engine.source == "spot"

    @pytest.mark.asyncio
    async def test_exact_navigator_match_beats_a_loose_engine_match(self):
        """Without `source` (an older client), the timestamp still decides. The
        engine row here is for a DIFFERENT bar, so a same-token fallback to it
        would be answering with a different trade."""
        scanner.snapshot("user-1").rows = [self._engine_row(timestamp_ms=_TS - 3_600_000)]
        navigator_runtime.snapshot("user-1").rows = [_nav_row(timestamp_ms=_TS)]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out.source == "navigator"
        assert out.triggered_ms == _TS

    @pytest.mark.asyncio
    async def test_loose_fallback_survives_a_regroup(self):
        """The clicked bar is gone from both snapshots — answer with the current
        row rather than a 404, which is why the loose match exists at all."""
        scanner.snapshot("user-1").rows = [self._engine_row(timestamp_ms=_TS + 3_600_000)]

        out = await detail_service.build_detail(FakeClient(), "user-1", 256265, _TS)

        assert out is not None and out.triggered_ms == _TS + 3_600_000
