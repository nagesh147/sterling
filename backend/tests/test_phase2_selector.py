"""Phase-2 derivatives-build correctness tests — DerivativesSelector engine.

Locks in every Phase 2 module:
  • profiles.get_profile resolution (exact / prefix / fallback)
  • liquidity_score composite + hard floors
  • expiry_picker 2× hold rule
  • time_shifted_revaluation BSM-at-exit-T
  • pinning_gate (DTE ≤ 2, ≥ 20% OI concentration, < 1% from spot)
  • funding_cost_gate hard cap + max_leverage solve
  • leverage_engine cold-start fail-loud + CB scaling + product cap
  • instrument_chooser AUTO heuristic + hard overrides
  • sl_tp_solver futures + options
  • strike_picker Greeks-aware ranking + drop reasons
  • selector.decide() full pipeline + DecisionStatus paths
  • freeze_token TTL + consume semantics
  • derivatives_audit ring + record_exit
"""
from __future__ import annotations

import time

import pytest

from app.engines.derivatives import (
    funding_cost_gate, instrument_chooser, leverage_engine, pinning_gate,
    profiles as profiles_mod, sl_tp_solver, strike_picker, expiry_picker,
    liquidity_score, time_shifted_revaluation as tsr,
)
from app.engines.derivatives.freeze_token import FreezeTokenStore, get_store
from app.engines.derivatives.schemas import (
    DecisionStatus, InstrumentBias, MarketContext, SignalContext,
    StrategyDerivativesProfile,
)
from app.engines.derivatives.selector import decide
from app.engines.derivatives.profiles import DEFAULT_PROFILES
from app.engines.risk import option_pricing
from app.schemas.market import OptionSummary
from app.services import derivatives_audit


@pytest.fixture(autouse=True)
def _reset_state():
    from app.engines.risk import cooldown
    from app.services import live_safety
    cooldown.clear()
    live_safety.reset_all_for_tests()
    option_pricing.clear_cache()
    get_store().clear()
    derivatives_audit.clear_for_tests()
    yield
    cooldown.clear()
    live_safety.reset_all_for_tests()
    option_pricing.clear_cache()
    get_store().clear()
    derivatives_audit.clear_for_tests()


def _opt(strike=50000, dte=14, oi=400, vol=200, iv=55, opt_type="call",
         expiry="140625", delta=None, mark=None, spread_pct=0.03) -> OptionSummary:
    if mark is None:
        intrinsic = (50000 - strike) if opt_type == "call" else (strike - 50000)
        mark = max(50.0, intrinsic + 800)
    if delta is None:
        delta = 0.55 if strike <= 50000 else 0.35
    return OptionSummary(
        instrument_name=f"{'C' if opt_type=='call' else 'P'}-BTC-{int(strike)}-{expiry}",
        underlying="BTC", strike=strike, expiry_date=expiry, dte=dte,
        option_type=opt_type, bid=mark * 0.97, ask=mark * 1.03,
        mark_price=mark, mid_price=mark, mark_iv=iv,
        delta=delta if opt_type == "call" else -delta,
        open_interest=oi, volume_24h=vol,
        last_updated_ms=int(time.time() * 1000),
        spread_pct=spread_pct,
    )


# ─── 1. profiles ────────────────────────────────────────────────────────


class TestProfiles:
    def test_exact_match(self):
        p = profiles_mod.get_profile("triple_st")
        assert p.strategy == "triple_st"
        assert p.leverage_cap == 10.0

    def test_prefix_fallback(self):
        # Unknown scalping subtype → falls back to scalping_grind
        p = profiles_mod.get_profile("scalping/wildcard_x")
        assert p.strategy == "scalping/wildcard_x"
        assert p.leverage_cap == 25.0    # matches scalping/price_action

    def test_unknown_strategy_returns_disabled(self):
        p = profiles_mod.get_profile("nonexistent_strategy")
        assert p.enabled is False

    def test_overrides_take_precedence(self):
        override = StrategyDerivativesProfile(strategy="triple_st", enabled=True, leverage_cap=42.0)
        p = profiles_mod.get_profile("triple_st", overrides={"triple_st": override})
        assert p.leverage_cap == 42.0
        assert p.enabled is True


# ─── 2. liquidity_score ─────────────────────────────────────────────────


class TestLiquidityScore:
    def test_healthy_passes(self):
        p = DEFAULT_PROFILES["triple_st"]
        s = liquidity_score.score(_opt(spread_pct=0.02, oi=500, vol=300), p)
        assert s.passes_floor

    def test_spread_floor_breach(self):
        p = DEFAULT_PROFILES["triple_st"]
        s = liquidity_score.score(_opt(spread_pct=0.10), p)
        assert not s.passes_floor
        assert "spread" in s.floor_breach_reason

    def test_oi_floor_breach(self):
        p = DEFAULT_PROFILES["triple_st"]
        # OI below the venue-realistic floor (min_oi=1.0) must breach.
        s = liquidity_score.score(_opt(oi=0.5), p)
        assert not s.passes_floor
        assert "oi" in s.floor_breach_reason

    def test_composite_weighting(self):
        p = DEFAULT_PROFILES["triple_st"]
        tight = liquidity_score.score(_opt(spread_pct=0.005, oi=2000, vol=1000), p)
        wide  = liquidity_score.score(_opt(spread_pct=0.039, oi=110, vol=10), p)
        assert tight.composite > wide.composite


# ─── 3. expiry_picker ───────────────────────────────────────────────────


class TestExpiryPicker:
    def test_picks_preferred_dte(self):
        p = DEFAULT_PROFILES["triple_st"]    # preferred=14
        chain = [_opt(dte=d, expiry=f"{d:02d}0625") for d in (5, 10, 12, 14, 21, 30)]
        res = expiry_picker.pick_expiry(chain, p, expected_hold_minutes=5 * 24 * 60)
        assert res is not None
        dte, expiry, contracts = res
        assert dte == 14

    def test_2x_hold_rule_excludes_short_dte(self):
        p = DEFAULT_PROFILES["triple_st"]
        # 7-day hold → DTE must be ≥ 14
        chain = [_opt(dte=10, expiry="100625"), _opt(dte=14, expiry="140625")]
        res = expiry_picker.pick_expiry(chain, p, expected_hold_minutes=7 * 24 * 60)
        assert res[0] == 14

    def test_no_valid_expiry_returns_none(self):
        p = DEFAULT_PROFILES["triple_st"]    # max=21
        chain = [_opt(dte=30, expiry="300625")]
        res = expiry_picker.pick_expiry(chain, p, expected_hold_minutes=5 * 24 * 60)
        assert res is None


# ─── 4. time_shifted_revaluation ────────────────────────────────────────


class TestTimeShiftedRevaluation:
    def test_positive_R_on_winning_trade(self):
        res = tsr.revalue(
            spot_now=50_000, spot_tp=52_500, spot_sl=49_000,
            strike=50_000, dte_now=30, expected_hold_days=3,
            iv=0.65, is_call=True,
        )
        assert res is not None
        assert res.expected_r > 0
        assert res.veto_reason == ""

    def test_premium_floor_veto(self):
        # Push TP so close to spot that premium would crush
        res = tsr.revalue(
            spot_now=50_000, spot_tp=50_100, spot_sl=49_000,
            strike=50_000, dte_now=30, expected_hold_days=29,   # nearly all decay
            iv=0.65, is_call=True,
        )
        assert res is not None
        assert "premium_floor_crushed" in res.veto_reason

    def test_theta_burn_positive(self):
        res = tsr.revalue(
            spot_now=50_000, spot_tp=51_000, spot_sl=49_500,
            strike=50_000, dte_now=30, expected_hold_days=10,
            iv=0.65, is_call=True,
        )
        assert res.theta_burn_pct > 0
        assert res.theta_burn_pct < 1.0

    def test_degenerate_inputs_return_none(self):
        assert tsr.revalue(spot_now=0, spot_tp=51_000, spot_sl=49_500,
                           strike=50_000, dte_now=30, expected_hold_days=3,
                           iv=0.65, is_call=True) is None
        assert tsr.revalue(spot_now=50_000, spot_tp=51_000, spot_sl=49_500,
                           strike=50_000, dte_now=0, expected_hold_days=3,
                           iv=0.65, is_call=True) is None


# ─── 5. pinning_gate ────────────────────────────────────────────────────


class TestPinningGate:
    def _chain(self):
        # Heavy OI at 50000 on both call + put sides → pinning strike
        return [
            _opt(strike=49_000, dte=1, oi=100, expiry="050625"),
            _opt(strike=50_000, dte=1, oi=1000, expiry="050625"),
            _opt(strike=51_000, dte=1, oi=100, expiry="050625"),
            _opt(strike=49_000, dte=1, oi=100, opt_type="put", expiry="050625"),
            _opt(strike=50_000, dte=1, oi=800, opt_type="put", expiry="050625"),
            _opt(strike=51_000, dte=1, oi=100, opt_type="put", expiry="050625"),
        ]

    def test_vetoes_near_pin_inside_window(self):
        target = _opt(strike=50_000, dte=1, expiry="050625")
        chain = self._chain()
        r = pinning_gate.check_pinning(target, spot=50_050, full_chain=chain)
        assert r.veto
        assert r.nearest_pin_strike == 50_000

    def test_no_veto_outside_dte_window(self):
        target = _opt(strike=50_000, dte=14, expiry="200625")
        r = pinning_gate.check_pinning(target, spot=50_050, full_chain=self._chain())
        assert not r.veto

    def test_no_veto_far_from_pin(self):
        target = _opt(strike=50_000, dte=1, expiry="050625")
        r = pinning_gate.check_pinning(target, spot=51_500, full_chain=self._chain())
        assert not r.veto


# ─── 6. funding_cost_gate ───────────────────────────────────────────────


class TestFundingCostGate:
    def test_options_always_allowed(self):
        r = funding_cost_gate.check(
            instrument_type="options", leverage=1, funding_8h_pct=0.5,
            hold_days=10, entry=50_000, stop_dist=500, rr=2.0,
            contracts=1.0, funding_cost_max_pct_of_R=0.25,
        )
        assert r.allowed

    def test_low_funding_passes(self):
        r = funding_cost_gate.check(
            instrument_type="futures", leverage=5, funding_8h_pct=0.00005,
            hold_days=1.0, entry=50_000, stop_dist=500, rr=2.0,
            contracts=1.0, funding_cost_max_pct_of_R=0.25,
        )
        assert r.allowed

    def test_high_funding_breaches_and_returns_max(self):
        r = funding_cost_gate.check(
            instrument_type="futures", leverage=25, funding_8h_pct=0.001,
            hold_days=7, entry=50_000, stop_dist=500, rr=2.0,
            contracts=1.0, funding_cost_max_pct_of_R=0.25,
        )
        assert not r.allowed
        assert r.max_leverage_for_budget >= 1.0
        assert r.projected_cost_pct_of_r > 0.25


# ─── 7. leverage_engine ─────────────────────────────────────────────────


class TestLeverageEngine:
    def _market(self, **overrides):
        d = dict(spot=50_000, underlying="BTC", portfolio_value=100_000,
                 cb_size_mult=1.0, atr_percentile=50)
        d.update(overrides)
        return MarketContext(**d)

    def _funding_ok(self):
        return funding_cost_gate.FundingGateResult(
            allowed=True, max_leverage_for_budget=100.0,
            projected_cost_usd=0.0, projected_cost_pct_of_r=0.0,
        )

    def test_options_returns_one(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        d = leverage_engine.decide(
            instrument_type="options", underlying="BTC",
            profile=p, market=self._market(), funding_result=self._funding_ok(),
        )
        assert d.leverage == 1.0

    def test_cold_start_caps_at_2x(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        d = leverage_engine.decide(
            instrument_type="futures", underlying="BTC",
            profile=p, market=self._market(), funding_result=self._funding_ok(),
        )
        assert d.leverage <= 2.0
        assert "cold_start_kelly" in d.warnings

    def test_warm_kelly_no_cold_start_warning(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        m = self._market(win_rate=0.6, avg_R=1.5)
        d = leverage_engine.decide(
            instrument_type="futures", underlying="BTC",
            profile=p, market=m, funding_result=self._funding_ok(),
        )
        assert "cold_start_kelly" not in d.warnings

    def test_cb_halt_zeros_leverage(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        m = self._market(win_rate=0.6, avg_R=1.5, cb_size_mult=0.0)
        d = leverage_engine.decide(
            instrument_type="futures", underlying="BTC",
            profile=p, market=m, funding_result=self._funding_ok(),
        )
        # CB HALT (size_mult=0) collapses leverage to the 1× floor.
        assert d.leverage == 1.0

    def test_product_cap_enforced(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        m = self._market(win_rate=0.8, avg_R=3.0, cb_size_mult=1.0)
        d = leverage_engine.decide(
            instrument_type="futures", underlying="XRP",         # cap = 25
            profile=p, market=m, funding_result=self._funding_ok(),
        )
        assert d.leverage <= 25.0


# ─── 8. instrument_chooser ──────────────────────────────────────────────


class TestInstrumentChooser:
    def _sig(self, **overrides):
        d = dict(strategy="scalping/price_action", underlying="BTC", direction="long",
                 entry=50_000, stop_loss=49_500, take_profit=51_000, atr=500,
                 signal_score=60, signal_strength="STRONG")
        d.update(overrides)
        return SignalContext(**d)

    def _mkt(self, **overrides):
        d = dict(spot=50_000, underlying="BTC", portfolio_value=100_000,
                 cb_size_mult=1.0, ivr_pct=40, basis_pct=0.001)
        d.update(overrides)
        return MarketContext(**d)

    def test_hard_override_futures(self):
        p = DEFAULT_PROFILES["statarb"]      # FUTURES bias
        r = instrument_chooser.choose(
            signal=self._sig(strategy="statarb"), profile=p, market=self._mkt(),
            best_option_expected_r=10.0,     # would normally pick options
        )
        assert r.instrument_type == "futures"

    def test_hard_override_options(self):
        p = DEFAULT_PROFILES["scalping/breakout"]
        r = instrument_chooser.choose(
            signal=self._sig(strategy="scalping/breakout"), profile=p, market=self._mkt(),
            best_option_expected_r=0.5,
        )
        assert r.instrument_type == "options"

    def test_auto_options_when_all_criteria_met(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        r = instrument_chooser.choose(
            signal=self._sig(signal_score=75),
            profile=p, market=self._mkt(ivr_pct=30),
            best_option_expected_r=4.0,
        )
        assert r.instrument_type == "options"

    def test_auto_futures_on_high_ivr(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        r = instrument_chooser.choose(
            signal=self._sig(signal_score=80),
            profile=p, market=self._mkt(ivr_pct=95),     # > 85 cap
            best_option_expected_r=5.0,
        )
        assert r.instrument_type == "futures"

    def test_auto_futures_on_low_conviction(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        r = instrument_chooser.choose(
            signal=self._sig(signal_score=30), profile=p, market=self._mkt(),
            best_option_expected_r=5.0,
        )
        assert r.instrument_type == "futures"

    def test_auto_futures_on_low_asymmetry(self):
        p = DEFAULT_PROFILES["scalping/price_action"]
        r = instrument_chooser.choose(
            signal=self._sig(signal_score=80), profile=p, market=self._mkt(),
            best_option_expected_r=1.5,
        )
        assert r.instrument_type == "futures"


# ─── 9. sl_tp_solver ────────────────────────────────────────────────────


class TestSLTPSolver:
    def test_futures_ok(self):
        # TP needs to clear stop_dist × rr + ATR cushion (resolve_trade_risk
        # adds 0.25 × ATR by default), so 53k is comfortably above 2× the
        # ~1.1k stop distance.
        s = sl_tp_solver.solve_futures(
            direction="long", entry=50_000, structure_stop=49_000,
            atr_val=500, take_profit=53_000, rr=2.0,
        )
        assert s.ok
        assert s.stop_loss < 50_000
        assert s.take_profit and s.take_profit > 50_000

    def test_futures_rejects_unscalpable_stop(self):
        # Stop > 3% from entry → solver rejects
        s = sl_tp_solver.solve_futures(
            direction="long", entry=50_000, structure_stop=47_000,
            atr_val=500, take_profit=52_000, rr=2.0,
        )
        assert not s.ok

    def test_options_premium_floor(self):
        # If BSM SL is below 50% of premium_now, floor kicks in
        s = sl_tp_solver.solve_options(
            direction="long", entry_spot=50_000, stop_spot=49_000, target_spot=52_000,
            premium_now=1200, premium_at_tp=2400, premium_at_sl=300,
        )
        assert s.sl_premium == 600.0           # 50% × 1200

    def test_options_premium_no_floor_when_natural_higher(self):
        s = sl_tp_solver.solve_options(
            direction="long", entry_spot=50_000, stop_spot=49_500, target_spot=51_000,
            premium_now=1200, premium_at_tp=1500, premium_at_sl=900,
        )
        assert s.sl_premium == 900.0


# ─── 10. strike_picker ──────────────────────────────────────────────────


class TestStrikePicker:
    def test_picks_target_delta_first(self):
        p = DEFAULT_PROFILES["triple_st"]      # target_delta=0.575
        candidates = [
            _opt(strike=48_000, dte=14, delta=0.75, iv=55, oi=400, vol=300),
            _opt(strike=49_000, dte=14, delta=0.65, iv=55, oi=400, vol=300),
            _opt(strike=50_000, dte=14, delta=0.55, iv=55, oi=400, vol=300),
            _opt(strike=51_000, dte=14, delta=0.40, iv=55, oi=400, vol=300),
        ]
        ranked = strike_picker.pick(
            candidates=candidates, profile=p, spot=50_000,
            spot_tp=51_500, spot_sl=49_250, expected_hold_days=5, prefer_gamma=False,
        )
        kept = [s for s in ranked if not s.drop_reason]
        assert len(kept) > 0
        # Top candidate's delta should be near target (0.575 ± 0.075 → 0.5–0.65)
        assert 0.5 <= abs(kept[0].option.delta) <= 0.65

    def test_drops_iv_too_high(self):
        p = DEFAULT_PROFILES["triple_st"]
        candidates = [_opt(strike=50_000, dte=14, delta=0.55, iv=85, oi=400, vol=300)]
        ranked = strike_picker.pick(
            candidates=candidates, profile=p, spot=50_000,
            spot_tp=51_500, spot_sl=49_250, expected_hold_days=5, prefer_gamma=False,
        )
        assert ranked[0].drop_reason.startswith("iv_too_high")

    def test_drops_low_liquidity(self):
        p = DEFAULT_PROFILES["triple_st"]
        candidates = [_opt(strike=50_000, dte=14, delta=0.55, iv=55, oi=0.5, vol=100, spread_pct=0.02)]
        ranked = strike_picker.pick(
            candidates=candidates, profile=p, spot=50_000,
            spot_tp=51_500, spot_sl=49_250, expected_hold_days=5, prefer_gamma=False,
        )
        assert ranked[0].drop_reason.startswith("liquidity")


# ─── 11. freeze_token ───────────────────────────────────────────────────


class TestFreezeToken:
    def test_roundtrip(self):
        store = FreezeTokenStore()
        token, ttl = store.freeze({"x": 1})
        assert ttl == 120_000
        assert store.get(token) == {"x": 1}

    def test_consume_removes(self):
        store = FreezeTokenStore()
        token, _ = store.freeze("payload")
        assert store.consume(token) == "payload"
        assert store.consume(token) is None
        assert store.get(token) is None

    def test_get_after_consume_returns_none(self):
        store = FreezeTokenStore()
        token, _ = store.freeze("x")
        store.consume(token)
        assert store.get(token) is None

    def test_unknown_token(self):
        store = FreezeTokenStore()
        assert store.get("nonexistent") is None
        assert store.consume("nonexistent") is None


# ─── 12. derivatives_audit ──────────────────────────────────────────────


class TestDerivativesAudit:
    def test_record_and_list(self):
        sig = SignalContext(strategy="triple_st", underlying="BTC", direction="long",
                            entry=50_000, stop_loss=49_000, take_profit=52_000)
        mkt = MarketContext(spot=50_000, underlying="BTC", portfolio_value=100_000)

        # Minimal stand-in for a decision
        class _Dec:
            class status:
                value = "ok"
            chosen = None

        aid = derivatives_audit.record(decision=_Dec(), signal=sig, market=mkt)
        rows = derivatives_audit.list_recent(strategy="triple_st")
        assert len(rows) >= 1
        assert rows[0]["audit_id"] == aid

    def test_record_exit_updates_pnl(self):
        sig = SignalContext(strategy="triple_st", underlying="BTC", direction="long",
                            entry=50_000, stop_loss=49_000, take_profit=52_000)
        mkt = MarketContext(spot=50_000, underlying="BTC", portfolio_value=100_000)

        class _Dec:
            class status:
                value = "ok"
            chosen = None

        aid = derivatives_audit.record(decision=_Dec(), signal=sig, market=mkt)
        derivatives_audit.record_exit(aid, exit_pnl=420.5)
        rows = derivatives_audit.list_recent()
        assert any(r["exit_pnl"] == 420.5 for r in rows if r["audit_id"] == aid)


# ─── 13. selector.decide() full pipeline ────────────────────────────────


def _make_chain():
    """A multi-strike multi-expiry chain covering the triple_st DTE window."""
    chain = []
    for dte, expiry in [(10, "100625"), (14, "140625"), (21, "210625")]:
        for strike in (48_000, 49_000, 50_000, 51_000, 52_000):
            chain.append(_opt(strike=strike, dte=dte, expiry=expiry, oi=500, vol=300, iv=35))
        for strike in (48_000, 49_000, 50_000, 51_000):
            chain.append(_opt(strike=strike, dte=dte, expiry=expiry, oi=500, vol=300, iv=35, opt_type="put"))
    return chain


class TestSelectorPipeline:
    def _sig(self, **overrides):
        d = dict(strategy="triple_st", underlying="BTC", direction="long",
                 entry=50_000, stop_loss=49_000, take_profit=53_000, atr=1_000,
                 rr_target=2.0, signal_score=75, signal_strength="STRONG",
                 expected_hold_minutes=5 * 24 * 60, mode_name="swing")
        d.update(overrides)
        return SignalContext(**d)

    def _mkt(self, **overrides):
        d = dict(spot=50_000, underlying="BTC", portfolio_value=100_000,
                 funding_8h_pct=0.0001, basis_pct=0.001, ivr_pct=30,
                 atr_percentile=50, win_rate=0.6, avg_R=1.5, cb_size_mult=1.0)
        d.update(overrides)
        return MarketContext(**d)

    def test_profile_disabled_returns_profile_off(self):
        d = decide(signal=self._sig(), market=self._mkt(), chain=_make_chain())
        assert d.status == DecisionStatus.PROFILE_OFF
        assert d.chosen is None
        assert d.freeze_token is None

    def test_profile_enabled_returns_ok(self):
        override = DEFAULT_PROFILES["triple_st"].model_copy(update={"enabled": True})
        d = decide(signal=self._sig(), market=self._mkt(), chain=_make_chain(),
                   profile_overrides={"triple_st": override})
        assert d.status == DecisionStatus.OK
        assert d.chosen is not None
        assert d.freeze_token is not None
        assert d.freeze_token_ttl_ms == 120_000
        # Token must round-trip
        assert get_store().get(d.freeze_token) is d

    def test_no_chain_falls_back_to_futures(self):
        override = DEFAULT_PROFILES["triple_st"].model_copy(update={"enabled": True})
        d = decide(signal=self._sig(), market=self._mkt(), chain=None,
                   profile_overrides={"triple_st": override})
        # No chain → only futures candidate is possible
        assert d.chosen is not None
        assert d.chosen.instrument_type == "futures"

    def test_decision_has_alternatives(self):
        override = DEFAULT_PROFILES["triple_st"].model_copy(update={"enabled": True})
        d = decide(signal=self._sig(), market=self._mkt(), chain=_make_chain(),
                   profile_overrides={"triple_st": override})
        assert isinstance(d.alternatives, list)
        # The selector must surface at least one alternative when chain is rich.
        assert len(d.alternatives) >= 1
