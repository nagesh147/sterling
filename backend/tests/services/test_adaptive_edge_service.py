"""Adaptive Edge service layer: config, scanner funnel, positions, runner authority.

The engine ships enabled and on auto by design, so the tests that matter most
here are the ones that prove it still cannot reach real money: the promotion
gate, the paper/live default, and the safety field name.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.engines.adaptive_edge import AdaptiveEdgeConfig
from app.engines.adaptive_edge.config import CALIBRATED_FIELDS, PARAMETER_PROVENANCE
from app.engines.adaptive_edge.state_machine import Event, StrategyState
from app.services import adaptive_edge as service
from app.services import adaptive_edge_positions as positions
from app.services import adaptive_edge_runner as runner
from app.services.adaptive_edge_scanner import listed_contracts, tradeable_contracts


# ----------------------------------------------------------------- config

def test_default_config_validates():
    assert AdaptiveEdgeConfig().validate() is not None


def test_config_round_trips_through_json():
    """as_dict must survive storage, or a saved config stops equalling itself."""
    cfg = AdaptiveEdgeConfig().validate()
    restored = AdaptiveEdgeConfig(**{
        k: (tuple(v) if isinstance(v, list) else v)
        for k, v in json.loads(json.dumps(cfg.as_dict())).items()
    }).validate()
    assert restored == cfg


def test_expiry_window_that_excludes_every_contract_is_rejected():
    """The recurring defect: a filter that silently disables the strategy.

    avoid_expiry_day with a zero-day ceiling leaves no eligible contract, which
    renders as "found no setup" rather than as a misconfiguration.
    """
    with pytest.raises(ValueError, match="excludes every contract"):
        AdaptiveEdgeConfig(expiry_dte_max=0, avoid_expiry_day=True).validate()


def test_expiry_window_bounds_must_be_ordered():
    with pytest.raises(ValueError, match="expiry_dte_max"):
        AdaptiveEdgeConfig(expiry_dte_min=5, expiry_dte_max=2).validate()


def test_empty_universe_is_rejected():
    with pytest.raises(ValueError, match="at least one of"):
        AdaptiveEdgeConfig(scan_indices=(), scan_stocks=(), scan_all_stocks=False).validate()


@pytest.mark.parametrize("field,value", [
    ("min_expected_net_value", -1.0),
    ("min_conservative_ev", -1.0),
])
def test_negative_ev_floor_is_rejected(field, value):
    """Master Spec §35 makes both strictly positive a mandatory entry gate,
    so a negative floor would authorize trades the source forbids outright."""
    with pytest.raises(ValueError, match="Master Spec"):
        AdaptiveEdgeConfig(**{field: value}).validate()


def test_warmup_cannot_exceed_lookback():
    with pytest.raises(ValueError, match="normalization_warmup_bars"):
        AdaptiveEdgeConfig(feature_lookback_bars=10, normalization_warmup_bars=50).validate()


def test_session_times_must_be_ordered():
    with pytest.raises(ValueError, match="session_end"):
        AdaptiveEdgeConfig(session_start="15:00", session_end="09:20").validate()


def test_square_off_cannot_precede_session_end():
    with pytest.raises(ValueError, match="square_off_time"):
        AdaptiveEdgeConfig(session_end="15:10", square_off_time="15:00").validate()


def test_nothing_is_marked_calibrated():
    """The honest counterpart to Gamma Move's CALIBRATED_FIELDS.

    If this ever becomes non-empty without a validation report landing beside
    it, a placeholder has been promoted to a measured value.
    """
    assert CALIBRATED_FIELDS == frozenset()
    assert "UNCALIBRATED" in PARAMETER_PROVENANCE["status"]


def test_warnings_lead_with_the_calibration_gap():
    warnings = AdaptiveEdgeConfig().validate().warnings()
    assert warnings, "an uncalibrated engine must say so"
    assert "calibrated" in warnings[0]


def test_monitor_only_stop_is_called_out():
    warnings = AdaptiveEdgeConfig(stop_mode="monitor").validate().warnings()
    assert any("this process" in w for w in warnings)


# --------------------------------------------------------- config storage

def test_get_config_returns_real_defaults_when_nothing_stored(monkeypatch):
    """Nothing stored must mean the shipped defaults, not a fabricated OFF."""
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key: None)
    cfg = service.get_config()
    assert cfg.enabled is True
    assert cfg == AdaptiveEdgeConfig()


def test_get_config_falls_back_to_disabled_when_stored_config_is_invalid(monkeypatch):
    """A config that will not validate must never become a trading config."""
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key: json.dumps({"expiry_dte_max": 0,
                                                                  "avoid_expiry_day": True}))
    assert service.get_config().enabled is False


def test_get_config_falls_back_to_disabled_when_store_is_unavailable(monkeypatch):
    import app.services.db as db

    def boom(key):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "get_config", boom)
    assert service.get_config().enabled is False


def test_stored_value_beats_a_default(monkeypatch):
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key: json.dumps({"lots": 7}))
    assert service.get_config().lots == 7


def test_set_config_refuses_unknown_fields(monkeypatch):
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key: None)
    monkeypatch.setattr(db, "set_config", lambda key, value: None)
    with pytest.raises(ValueError, match="Unknown"):
        service.set_config({"not_a_field": 1})


# ------------------------------------------------------------ descriptor

def test_descriptor_does_not_claim_validation():
    d = service.descriptor()
    assert d["validated"] is False
    assert d["calibrated_fields"] == []
    # "no edge" and "a weak edge" are different claims; this engine has the first.
    assert "has no demonstrated edge" in d["headline_finding"]


def test_descriptor_cites_the_authoritative_source():
    assert "Master Mathematical Specification" in service.descriptor()["provenance"]


# --------------------------------------------------------- scanner funnel

def _row(name, strike, dte=7, **over):
    row = {"strike": float(strike), "option_type": "call", "expiry_date": "2026-09-03",
           "instrument_name": name, "lot_size": 50, "token": abs(hash(name)) % 10_000}
    if dte is not None:
        row["dte"] = dte
    row.update(over)
    return row


def test_listed_contracts_keeps_the_contract_inside_both_windows():
    cfg = AdaptiveEdgeConfig().validate()
    out = listed_contracts([_row("GOOD", 25_000)], cfg, spot=25_000.0)
    assert [r["instrument_name"] for r in out] == ["GOOD"]


def test_listed_contracts_drops_expiry_day_when_configured():
    cfg = AdaptiveEdgeConfig(avoid_expiry_day=True).validate()
    out = listed_contracts([_row("TODAY", 25_000, dte=0)], cfg, spot=25_000.0)
    assert out == []


def test_listed_contracts_drops_strikes_outside_the_window():
    cfg = AdaptiveEdgeConfig(strike_window_pct=2.0).validate()
    out = listed_contracts([_row("FAR", 40_000)], cfg, spot=25_000.0)
    assert out == []


def test_row_without_dte_is_rejected_rather_than_defaulted():
    """A missing dte defaulting to 0 combines with avoid_expiry_day to drop
    every contract, which is indistinguishable from finding no setup."""
    cfg = AdaptiveEdgeConfig().validate()
    assert listed_contracts([_row("NODTE", 25_000, dte=None)], cfg, spot=25_000.0) == []


def test_listed_contracts_needs_a_real_spot():
    cfg = AdaptiveEdgeConfig().validate()
    assert listed_contracts([_row("GOOD", 25_000)], cfg, spot=0.0) == []


def _quote(price=120.0, oi=60_000.0, volume=5_000.0, bid=119.0, ask=121.0):
    return {"last_price": price, "oi": oi, "volume": volume,
            "depth": {"buy": [{"price": bid}], "sell": [{"price": ask}]}}


def test_tradeable_contracts_keeps_a_liquid_contract():
    cfg = AdaptiveEdgeConfig().validate()
    rows = [_row("GOOD", 25_000)]
    kept, dropped = tradeable_contracts(rows, {"NFO:GOOD": _quote()}, cfg, spot=25_000.0)
    assert [r["symbol"] for r in kept] == ["GOOD"]
    assert dropped == {}


@pytest.mark.parametrize("quote,reason", [
    (_quote(oi=10.0), "open interest below floor"),
    (_quote(volume=1.0), "volume below floor"),
    (_quote(price=2.0), "premium below floor"),
    (_quote(bid=100.0, ask=140.0), "spread too wide"),
])
def test_tradeable_contracts_reports_why_each_drop_happened(quote, reason):
    """An empty board must distinguish illiquid from wide from too-cheap."""
    cfg = AdaptiveEdgeConfig().validate()
    kept, dropped = tradeable_contracts([_row("X", 25_000)], {"NFO:X": quote}, cfg, spot=25_000.0)
    assert kept == []
    assert dropped == {reason: 1}


def test_missing_quote_is_a_drop_not_a_crash():
    cfg = AdaptiveEdgeConfig().validate()
    kept, dropped = tradeable_contracts([_row("X", 25_000)], {}, cfg, spot=25_000.0)
    assert kept == [] and dropped == {"no quote": 1}


def test_penny_option_is_excluded_because_the_tick_dominates_it():
    """At a 0.05 tick a 2.00 option moves in 2.5% steps, so a premium-change
    feature would be measuring the tick grid rather than the market."""
    cfg = AdaptiveEdgeConfig(min_option_premium=10.0).validate()
    kept, _ = tradeable_contracts([_row("P", 25_000)], {"NFO:P": _quote(price=2.0)},
                                  cfg, spot=25_000.0)
    assert kept == []


# ------------------------------------------------------------- positions

def _position(**over):
    base = dict(symbol="SYM", token=1, underlying="NIFTY", direction="CE", quantity=50,
                lot_size=50, entry_price=100.0, stop_price=70.0, target_price=200.0)
    base.update(over)
    return positions.AdaptiveEdgePosition(**base)


def test_a_rejected_entry_leaves_no_open_position():
    pos = _position()
    pos.apply(Event.ORDER_SUBMITTED).apply(Event.REJECTED)
    assert pos.state == StrategyState.REJECTED.value
    assert pos.is_open is False


def test_a_rejected_exit_keeps_the_position():
    """Treating a refused exit as closed silently abandons a live position."""
    pos = _position()
    pos.apply(Event.ORDER_SUBMITTED).apply(Event.FILL).apply(Event.EXIT_INTENT)
    pos.apply(Event.REJECTED)
    assert pos.state == StrategyState.OPEN.value
    assert pos.is_open is True


def test_a_partially_filled_entry_still_holds_quantity():
    pos = _position()
    pos.apply(Event.ORDER_SUBMITTED).apply(Event.PARTIAL_FILL)
    assert pos.is_open is True
    pos.apply(Event.REJECTED)          # remainder refused
    assert pos.state == StrategyState.OPEN.value


def test_an_undefined_broker_event_raises_rather_than_being_ignored():
    pos = _position()
    with pytest.raises(ValueError, match="invalid transition"):
        pos.apply(Event.FILL)          # nothing was ordered yet


def test_load_refuses_to_report_flat_when_the_store_is_unreadable(monkeypatch):
    """Reporting "no positions" for an unreadable store lets the engine open a
    duplicate of something it is already holding."""
    import app.services.db as db
    positions.reset("u1")

    def boom(key):
        raise RuntimeError("store down")

    monkeypatch.setattr(db, "get_config", boom)
    with pytest.raises(RuntimeError):
        positions.load("u1")
    positions.reset("u1")


# -------------------------------------------------------- runner authority

def test_unknown_account_means_paper():
    """Failing the other way places real orders on a lookup that did not work."""
    assert runner.is_paper("definitely-not-a-user") is True


def test_unknown_account_means_manual():
    assert runner.auto_execute("definitely-not-a-user") is False


def test_promotion_gate_blocks_live_execution():
    blocked, reason = runner.promotion_blocked()
    assert blocked is True
    assert reason == "strategy_promotion_required"


def test_safety_is_read_through_allowed_not_ok(monkeypatch):
    """SafetyDecision exposes .allowed. Reading a .ok that does not exist with a
    truthy default fails open, and the kill switch stops blocking anything."""
    import app.services.live_safety as live_safety

    class OnlyOk:
        ok = True                       # deliberately the wrong field name

    monkeypatch.setattr(live_safety, "assert_safe_to_trade",
                        lambda *a, **k: OnlyOk())
    allowed, _ = runner._safety("u1", None)
    assert allowed is False


def test_safety_skips_the_usd_daily_loss_breaker_and_passes_uid(monkeypatch):
    """That breaker uses a legacy accounting unit and reads zero for
    an INR position, so including it would be a gate that always passes. uid is
    what routes the check at the right account."""
    import app.services.live_safety as live_safety
    seen: dict = {}

    class Ok:
        allowed = True
        reason = ""

    def capture(*args, **kwargs):
        seen.update(kwargs)
        return Ok()

    monkeypatch.setattr(live_safety, "assert_safe_to_trade", capture)
    runner._safety("u-42", "key-1")
    assert seen.get("check_daily_loss") is False
    assert seen.get("uid") == "u-42"


def test_safety_denial_is_respected(monkeypatch):
    import app.services.live_safety as live_safety

    class Denied:
        allowed = False
        reason = "kill switch engaged"

    monkeypatch.setattr(live_safety, "assert_safe_to_trade", lambda *a, **k: Denied())
    allowed, reason = runner._safety("u1", None)
    assert allowed is False and reason == "kill switch engaged"


def test_safety_unavailable_fails_closed(monkeypatch):
    import app.services.live_safety as live_safety

    def boom(*a, **k):
        raise RuntimeError("safety service down")

    monkeypatch.setattr(live_safety, "assert_safe_to_trade", boom)
    allowed, _ = runner._safety("u1", None)
    assert allowed is False


def test_arm_refuses_a_live_account_while_unpromoted(monkeypatch):
    """The gate that makes it safe to ship this engine enabled."""
    monkeypatch.setattr(runner, "is_paper", lambda uid: False)
    result = asyncio.run(runner.arm("u1", "any-signal"))
    assert result["ok"] is False
    assert result["reason"] == "strategy_promotion_required"


def test_scan_is_a_no_op_while_disabled(monkeypatch):
    monkeypatch.setattr(runner, "get_config",
                        lambda: AdaptiveEdgeConfig(enabled=False).validate())
    state = asyncio.run(runner.scan_once("u1"))
    assert state["signals"] == [] and state["reason"] == "engine disabled"


def test_scan_is_a_no_op_outside_the_session_window(monkeypatch):
    monkeypatch.setattr(runner, "_is_market_open", lambda cfg: False)
    state = asyncio.run(runner.scan_once("u1"))
    assert state["signals"] == []
    assert "session" in state["reason"]


def test_auto_enter_does_nothing_on_manual(monkeypatch):
    monkeypatch.setattr(runner, "auto_execute", lambda uid: False)
    assert asyncio.run(runner._auto_enter("u1")) == 0


def test_a_signal_with_no_direction_is_refused_by_the_entry_gate():
    """F-110 is the mandatory §35 conjunction and it now actually runs."""
    cfg = AdaptiveEdgeConfig().validate()
    signals = runner._signals_from(
        [{"symbol": "X", "expiry": "2026-09-03", "option_type": "CE",
          "direction": "NEUTRAL", "actionable": False}], cfg)
    assert signals[0]["entry_ok"] is False
    assert signals[0]["entry_decision"] == "NO_TRADE"
    assert signals[0]["reason"] == "no directional edge"


def test_conservative_ev_is_what_refuses_a_directional_signal_today():
    """The engine declines at the gate the source names, not at a flag.

    §35 requires ConservativeEV > 0, which is LowerConfidenceBound(EV) and needs
    the fitted probability model. The reason names exactly that, so the thing
    calibration has to supply is legible from the board.
    """
    cfg = AdaptiveEdgeConfig().validate()
    signals = runner._signals_from(
        [{"symbol": "X", "expiry": "2026-09-03", "option_type": "CE",
          "direction": "BULLISH", "actionable": True,
          "expected_net_value": 500.0}], cfg)
    assert signals[0]["entry_ok"] is False
    assert "conservative EV unavailable" in signals[0]["reason"]


def test_the_gate_opens_once_a_conservative_ev_exists():
    """Proves the refusal is the missing quantity, not a disabled code path."""
    cfg = AdaptiveEdgeConfig().validate()
    signals = runner._signals_from(
        [{"symbol": "X", "expiry": "2026-09-03", "option_type": "CE",
          "direction": "BULLISH", "actionable": True,
          "expected_net_value": 500.0, "conservative_ev": 120.0}], cfg)
    assert signals[0]["entry_ok"] is True
    assert signals[0]["entry_decision"] == "BUY_CE"


def test_a_bearish_decision_buys_a_put():
    cfg = AdaptiveEdgeConfig().validate()
    signals = runner._signals_from(
        [{"symbol": "X", "expiry": "2026-09-03", "option_type": "PE",
          "direction": "BEARISH", "actionable": True,
          "expected_net_value": 500.0, "conservative_ev": 90.0}], cfg)
    assert signals[0]["entry_decision"] == "BUY_PE"


def test_a_non_positive_conservative_ev_is_refused():
    cfg = AdaptiveEdgeConfig().validate()
    signals = runner._signals_from(
        [{"symbol": "X", "expiry": "2026-09-03", "option_type": "CE",
          "direction": "BULLISH", "actionable": True,
          "expected_net_value": 500.0, "conservative_ev": 0.0}], cfg)
    assert signals[0]["entry_ok"] is False
    assert "conservative expected value not positive" in signals[0]["reason"]


def test_session_status_reports_the_live_block():
    runner.clear("u1")
    runner.session_for("u1")
    status = runner.session_status("u1")
    assert status["live_blocked"] is True
    assert status["live_blocked_reason"] == "strategy_promotion_required"
    runner.clear("u1")


# ----------------------------------------------------------- observations

@pytest.fixture
def observation_store(monkeypatch):
    store: dict[str, str] = {}
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key, default="": store.get(key, default))
    monkeypatch.setattr(db, "set_config", lambda key, value: store.__setitem__(key, value))
    return store


def _candidate(symbol="NIFTY26090325000CE", **over):
    row = {"underlying": "NIFTY", "symbol": symbol, "token": 1, "option_type": "CE",
           "strike": 25000.0, "dte": 7, "spot": 25000.0, "last_price": 120.0,
           "oi": 60000.0, "volume": 5000.0, "bid": 119.0, "ask": 121.0}
    row.update(over)
    return row


def test_observations_are_recorded_so_a_paper_session_is_not_wasted(observation_store):
    from app.services import adaptive_edge_observations as obs
    assert obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000) == 1
    assert obs.summary("u1", "2026-08-27")["observations"] == 1


def test_the_same_candidate_in_the_same_scan_is_not_recorded_twice(observation_store):
    """Scans repeat every 60s and re-surface the same contract."""
    from app.services import adaptive_edge_observations as obs
    obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000)
    assert obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000) == 0
    assert obs.summary("u1", "2026-08-27")["observations"] == 1


def test_the_same_contract_at_a_later_time_is_a_new_observation(observation_store):
    from app.services import adaptive_edge_observations as obs
    obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000)
    obs.record("u1", "2026-08-27", [_candidate()], observed_ms=2000)
    assert obs.summary("u1", "2026-08-27")["observations"] == 2


def test_an_outcome_updates_its_observation_rather_than_appending(observation_store):
    """A second row would silently double the day's sample size."""
    from app.services import adaptive_edge_observations as obs
    obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000)
    key = "NIFTY26090325000CE:1000"
    assert obs.record_outcome("u1", "2026-08-27", key,
                              forward_premium=150.0, horizon_bars=15) is True
    summary = obs.summary("u1", "2026-08-27")
    assert summary["observations"] == 1 and summary["resolved"] == 1
    row = obs.load("u1", "2026-08-27")[0]
    assert row["forward_return_pct"] == pytest.approx(25.0)


def test_an_unresolved_observation_is_distinguishable_from_a_zero_return(observation_store):
    from app.services import adaptive_edge_observations as obs
    obs.record("u1", "2026-08-27", [_candidate()], observed_ms=1000)
    assert obs.pending("u1", "2026-08-27")
    obs.record_outcome("u1", "2026-08-27", "NIFTY26090325000CE:1000",
                       forward_premium=120.0, horizon_bars=15)
    assert obs.pending("u1", "2026-08-27") == []
    assert obs.load("u1", "2026-08-27")[0]["forward_return_pct"] == pytest.approx(0.0)


def test_an_outcome_for_an_unknown_observation_is_refused(observation_store):
    from app.services import adaptive_edge_observations as obs
    assert obs.record_outcome("u1", "2026-08-27", "NOPE:1",
                              forward_premium=1.0, horizon_bars=1) is False


def test_a_candidate_without_a_symbol_is_not_recorded(observation_store):
    from app.services import adaptive_edge_observations as obs
    assert obs.record("u1", "2026-08-27", [_candidate(symbol="")], observed_ms=1000) == 0
