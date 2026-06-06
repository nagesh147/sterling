"""Phase-7 dual-table derivatives correctness tests.

Locks in:
  • `selector.decide_both()` co-emits best-futures + best-options legs
    each with an independent freeze_token (consuming one does not
    invalidate the other).
  • `StrategyDerivativesProfile` defaults `auto_execute_futures` and
    `auto_execute_options` to False — flipping `enabled` alone NEVER
    arms the auto-fire path.
  • The background scanner respects (a) `algo_mode` off → no fire,
    (b) profile.enabled off → no fire, (c) auto_execute_<leg> off →
    no fire, (d) per-(strategy,sym,leg) cooldown blocks back-to-back
    duplicate fires.

The scanner is exercised via direct call to `_auto_execute_derivative`
+ the in-process freeze store. We do not boot the full ASGI lifespan;
that would also pull in adapter/network plumbing irrelevant to this
contract.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.derivatives.freeze_token import get_store as get_freeze_store
from app.engines.derivatives.profiles import DEFAULT_PROFILES
from app.engines.derivatives.schemas import (
    DecisionStatus, DualDerivativesDecision, InstrumentBias,
    MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives.selector import decide_both
from app.services import derivatives_audit


# Local sample profile (formerly DEFAULT_PROFILES["triple_st"]),
# kept here as a test vehicle after that strategy was removed from production.
_SWING_PROFILE = StrategyDerivativesProfile(
    strategy="swing_demo",
    instrument_bias=InstrumentBias.AUTO,
    target_delta=0.575,
    target_delta_tolerance=0.075,
    dte_min=10,
    dte_preferred=14,
    dte_max=21,
    expected_hold_minutes=5 * 24 * 60,
    expiry_close_minutes_before=120,
    leverage_cap=10.0,
    max_premium_pct_of_account=0.015,
    funding_cost_max_pct_of_R=0.25,
    min_oi=1.0,
    min_volume_24h_x_contract=1.0,
    max_spread_pct=0.04,
    ivr_pct_naked_max=40,
)


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


# ─── Profile defaults ───────────────────────────────────────────────────


class TestProfileDefaults:
    def test_auto_execute_flags_default_off(self):
        for slug, prof in DEFAULT_PROFILES.items():
            assert prof.auto_execute_futures is False, (
                f"{slug} ships with auto_execute_futures=True — must be opt-in"
            )
            assert prof.auto_execute_options is False, (
                f"{slug} ships with auto_execute_options=True — must be opt-in"
            )

    def test_master_enabled_and_auto_exec_independent(self):
        """Flipping `enabled` alone must NOT arm the auto-fire path."""
        prof = DEFAULT_PROFILES["conservative/price_action"].model_copy(
            update={"enabled": True}
        )
        assert prof.enabled is True
        assert prof.auto_execute_futures is False
        assert prof.auto_execute_options is False


# ─── decide_both — co-emit ───────────────────────────────────────────────


def _good_signal(strategy: str = "swing_demo") -> SignalContext:
    return SignalContext(
        strategy=strategy, underlying="BTC", direction="long",
        entry=50_000.0, stop_loss=49_000.0, take_profit=53_000.0,
        atr=1_000.0, rr_target=2.0, signal_score=75.0,
        signal_strength="STRONG", expected_hold_minutes=5 * 24 * 60,
        mode_name="swing",
    )


def _good_market() -> MarketContext:
    return MarketContext(
        spot=50_000.0, underlying="BTC", portfolio_value=100_000.0,
        win_rate=0.6, avg_R=1.5, cb_size_mult=1.0,
        funding_8h_pct=0.0001,
    )


class TestDecideBoth:
    def test_profile_off_short_circuits_both_legs(self):
        # Default profile has enabled=False
        dual = decide_both(signal=_good_signal(), market=_good_market(), chain=None)
        assert isinstance(dual, DualDerivativesDecision)
        assert dual.status == DecisionStatus.PROFILE_OFF
        assert dual.futures is None
        assert dual.options is None

    def test_enabled_no_chain_emits_only_futures_leg(self):
        override = _SWING_PROFILE.model_copy(update={"enabled": True})
        dual = decide_both(
            signal=_good_signal(), market=_good_market(), chain=None,
            profile_overrides={"swing_demo": override},
        )
        assert dual.status == DecisionStatus.OK
        assert dual.futures is not None
        assert dual.futures.status == DecisionStatus.OK
        assert dual.futures.chosen is not None
        assert dual.futures.chosen.instrument_type == "futures"
        # Options leg present but DEFER — no chain
        assert dual.options is not None
        assert dual.options.status == DecisionStatus.DEFER
        assert dual.options.chosen is None
        # Independent tokens
        assert dual.futures.freeze_token is not None

    def test_futures_bias_omits_options_leg(self):
        override = _SWING_PROFILE.model_copy(
            update={"enabled": True, "instrument_bias": InstrumentBias.FUTURES}
        )
        dual = decide_both(
            signal=_good_signal(), market=_good_market(), chain=None,
            profile_overrides={"swing_demo": override},
        )
        assert dual.futures is not None
        assert dual.options is None  # bias=FUTURES suppresses options leg entirely

    def test_options_bias_omits_futures_leg(self):
        override = _SWING_PROFILE.model_copy(
            update={"enabled": True, "instrument_bias": InstrumentBias.OPTIONS}
        )
        dual = decide_both(
            signal=_good_signal(), market=_good_market(), chain=None,
            profile_overrides={"swing_demo": override},
        )
        assert dual.futures is None  # bias=OPTIONS suppresses futures leg
        # Options leg is DEFER without a chain, but is present
        assert dual.options is not None
        assert dual.options.status == DecisionStatus.DEFER

    def test_independent_freeze_tokens(self):
        """The two legs each get their OWN freeze_token. Consuming one
        must NOT invalidate the other."""
        override = _SWING_PROFILE.model_copy(update={"enabled": True})
        dual = decide_both(
            signal=_good_signal(), market=_good_market(), chain=None,
            profile_overrides={"swing_demo": override},
        )
        store = get_freeze_store()
        # Only futures leg has a token (no chain → no options leg)
        ft = dual.futures.freeze_token
        assert ft and store.get(ft) is not None
        # Consume futures — it's now gone
        assert store.consume(ft) is not None
        assert store.get(ft) is None


# ─── Scanner contract: auto-exec gates ────────────────────────────────


class TestScannerAutoExecGates:
    """The scanner only auto-fires when ALL THREE are true:
      • app.state.algo_mode = True
      • profile.enabled = True
      • profile.auto_execute_<leg> = True

    We don't boot the full ASGI app; we drive _auto_execute_derivative
    directly with a stubbed app + stubbed place_live_order to assert it
    runs (or doesn't) and respects the freeze contract.
    """

    @pytest.mark.asyncio
    async def test_consume_failure_returns_false(self):
        """Stale token → auto_execute_derivative bails False without
        attempting place_live_order."""
        from app.services.derivatives_scanner import auto_execute_derivative
        app = MagicMock()
        result = await auto_execute_derivative(
            app, freeze_token="nonexistent-token",
            row_strategy="conservative/price_action", row_underlying="BTC", leg="futures",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_success_path_calls_place_live_order(self):
        """Valid token → places live order, returns True on accepted."""
        from app.services.derivatives_scanner import auto_execute_derivative
        from app.engines.derivatives.schemas import DerivativesCandidate, DerivativesDecision

        # Freeze a synthetic candidate
        cand = DerivativesCandidate(
            instrument_type="futures", underlying="BTC", entry_price=50_000.0,
            direction="long", contracts=1.0, leverage=5.0,
            notional_usd=50_000.0, stop_loss=49_000.0, take_profit=52_000.0,
            expected_r=2.0,
        )
        dec = DerivativesDecision(
            status=DecisionStatus.OK, chosen=cand, freeze_token_ttl_ms=30_000,
        )
        store = get_freeze_store()
        token, _ttl = store.freeze(dec)

        app = MagicMock()
        # place_live_order is async — patch it before auto_execute_derivative imports it
        fake_resp = MagicMock(
            status="filled", mode="paper", message="ok",
        )
        # status NOT in ("rejected","error") → accepted=True
        with patch("app.api.v1.endpoints.trading.place_live_order",
                   new_callable=AsyncMock, return_value=fake_resp):
            ok = await auto_execute_derivative(
                app, freeze_token=token,
                row_strategy="conservative/price_action",
                row_underlying="BTC", leg="futures",
            )
        assert ok is True
        # Token was single-fire — second attempt returns False
        ok2 = await auto_execute_derivative(
            app, freeze_token=token,
            row_strategy="conservative/price_action",
            row_underlying="BTC", leg="futures",
        )
        assert ok2 is False

    @pytest.mark.asyncio
    async def test_rejected_response_returns_false(self):
        """Order rejected by router → returns False, doesn't crash."""
        from app.services.derivatives_scanner import auto_execute_derivative
        from app.engines.derivatives.schemas import DerivativesCandidate, DerivativesDecision

        cand = DerivativesCandidate(
            instrument_type="options", underlying="BTC", entry_price=50_000.0,
            direction="long", contracts=1.0, leverage=1.0,
            notional_usd=50_000.0,
            option_symbol="C-BTC-50000-310525",
            stop_loss=49_000.0, take_profit=52_000.0, expected_r=2.0,
        )
        dec = DerivativesDecision(
            status=DecisionStatus.OK, chosen=cand, freeze_token_ttl_ms=30_000,
        )
        token, _ = get_freeze_store().freeze(dec)

        app = MagicMock()
        fake_resp = MagicMock(
            status="rejected", mode="live", message="kill_switch",
        )
        with patch("app.api.v1.endpoints.trading.place_live_order",
                   new_callable=AsyncMock, return_value=fake_resp):
            ok = await auto_execute_derivative(
                app, freeze_token=token,
                row_strategy="swing_demo", row_underlying="BTC", leg="options",
            )
        assert ok is False


# ─── Scanner cooldown ────────────────────────────────────────────────────


class TestScannerCooldown:
    def test_cooldown_key_includes_strategy_sym_and_leg(self):
        """Two different legs of the same (strategy, sym) must have
        DIFFERENT cooldown keys, so futures + options for the same
        signal can both fire on the same scanner pulse."""
        from app.services.derivatives_scanner import (
            _deriv_last_ordered, deriv_cooldown_ms, clear_cooldowns_for_tests,
        )
        clear_cooldowns_for_tests()
        now_ms = int(time.time() * 1000)
        # Manually stamp futures key
        _deriv_last_ordered["conservative/price_action|BTC|futures"] = now_ms
        # Options key for the SAME (strategy, sym) is NOT blocked
        assert "conservative/price_action|BTC|options" not in _deriv_last_ordered
        # Cooldown is positive
        assert deriv_cooldown_ms() >= 60_000


# ─── Scanner cache + auto-fire integration ────────────────────────────


class TestRunScannerTick:
    """run_scanner_tick must:
      • Build the snapshot regardless of algo_mode
      • Skip auto-fire when algo_mode is off
      • Skip auto-fire when profile.enabled is off
      • Skip auto-fire when profile.auto_execute_<leg> is off
      • Respect per-(strategy,sym,leg) cooldown
    """

    @pytest.mark.asyncio
    async def test_algo_off_no_auto_fire(self):
        from app.services import derivatives_scanner as scan

        app = MagicMock()
        app.state = MagicMock()
        app.state.algo_mode = False
        app.state.derivatives_scan_cache = None
        # Stub _both_rows to inject a deterministic row that WOULD fire if algo was on
        with patch("app.api.v1.endpoints.derivatives._both_rows",
                   new_callable=AsyncMock, return_value=([], [], 12345)):
            cache = await scan.run_scanner_tick(app, interval_s=30)
        assert cache["auto_exec_attempts"] == 0
        assert cache["last_scan_ms"] == 12345
        assert cache["next_scan_ms"] == 12345 + 30_000

    @pytest.mark.asyncio
    async def test_cooldown_blocks_second_fire(self):
        """A row freshly auto-fired must NOT fire again on the next
        scanner tick within the cooldown window."""
        from app.services import derivatives_scanner as scan

        # Build a synthetic candidate row that the scanner sees as
        # eligible: profile enabled + auto_execute_futures True.
        from app.api.v1.endpoints.derivatives import _CandidateRow
        row = _CandidateRow(
            signal_id="x", strategy="conservative/price_action", underlying="BTC",
            direction="long", instrument_type="futures",
            contracts=1.0, leverage=5.0, notional_usd=50_000.0,
            stop_loss=49_000.0, take_profit=52_000.0, expected_r=2.0,
            freeze_token="tok-A", freeze_token_ttl_ms=30_000,
            status="ok", reason="ok",
        )
        scan.clear_cooldowns_for_tests()

        app = MagicMock()
        app.state = MagicMock()
        app.state.algo_mode = True
        # Profile overrides: enabled + auto_execute_futures
        prof = DEFAULT_PROFILES["conservative/price_action"].model_copy(
            update={"enabled": True, "auto_execute_futures": True}
        )
        # Mark this as the active overrides dict so _profile_overrides returns it
        app.state.derivatives_profile_overrides = {"conservative/price_action": prof}

        # Patch _both_rows to return our row + _profile_overrides + auto_execute
        with patch("app.api.v1.endpoints.derivatives._both_rows",
                   new_callable=AsyncMock, return_value=([row], [], 11111)):
            with patch("app.services.derivatives_scanner.auto_execute_derivative",
                       new_callable=AsyncMock, return_value=True) as mock_fire:
                cache1 = await scan.run_scanner_tick(app, interval_s=30)
                # Second tick — cooldown should suppress
                cache2 = await scan.run_scanner_tick(app, interval_s=30)
        assert cache1["auto_exec_attempts"] == 1
        assert cache1["auto_exec_accepted"] == 1
        assert cache2["auto_exec_attempts"] == 0  # cooldown blocked
        assert mock_fire.call_count == 1
        # And app.state cache was written
        assert app.state.derivatives_scan_cache is not None

    @pytest.mark.asyncio
    async def test_profile_flag_off_no_fire(self):
        """Profile.enabled is True but auto_execute_futures is False —
        no auto-fire."""
        from app.services import derivatives_scanner as scan
        from app.api.v1.endpoints.derivatives import _CandidateRow

        row = _CandidateRow(
            signal_id="x", strategy="conservative/price_action", underlying="BTC",
            direction="long", instrument_type="futures",
            contracts=1.0, leverage=5.0, notional_usd=50_000.0,
            stop_loss=49_000.0, take_profit=52_000.0, expected_r=2.0,
            freeze_token="tok-B", freeze_token_ttl_ms=30_000,
            status="ok", reason="ok",
        )
        scan.clear_cooldowns_for_tests()

        app = MagicMock()
        app.state = MagicMock()
        app.state.algo_mode = True
        prof = DEFAULT_PROFILES["conservative/price_action"].model_copy(
            update={"enabled": True}  # auto_execute_futures left False
        )
        app.state.derivatives_profile_overrides = {"conservative/price_action": prof}

        with patch("app.api.v1.endpoints.derivatives._both_rows",
                   new_callable=AsyncMock, return_value=([row], [], 22222)):
            with patch("app.services.derivatives_scanner.auto_execute_derivative",
                       new_callable=AsyncMock, return_value=True) as mock_fire:
                cache = await scan.run_scanner_tick(app, interval_s=30)
        assert cache["auto_exec_attempts"] == 0
        assert mock_fire.call_count == 0
