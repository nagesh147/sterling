"""Research E2E: coverage, folds, simulated fill. Production stays locked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_gate import evaluate_execution_gate
from app.engines.adaptive_edge.f101 import dump_f101_parameters, trial_identity_parameters
from app.engines.adaptive_edge.feature_engine import FeatureStatus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.research_e2e import run_research_e2e
from app.engines.adaptive_edge.research_formulas import (
    STRATEGY_FORMULA_IDS,
    assert_production_strategy_locked,
    research_formula_table,
)
from app.engines.adaptive_edge.research_pipeline import (
    A197_MIN_BARS,
    A197_MIN_TRADING_DAYS,
    build_research_cycle,
    coverage_report,
    estimate_params_from_train,
    observations_for_walk_forward,
    score_window_candidates,
)
from app.engines.adaptive_edge.trial_dataset import score_trial_bars
from app.engines.adaptive_edge.walk_forward import assign_observation, ObservationDisposition


def _bar(i: int, close: float) -> CanonicalMarketEvent:
    ts = f"2026-08-13T03:{15 + i:02d}:00+00:00"
    return CanonicalMarketEvent(
        record_id=f"B{i}",
        event_type="bar",
        instrument_id="NIFTY-I",
        event_time=ts,
        available_at=ts,
        source="truedata",
        source_version="2.6",
        payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0, "oi": 1.0},
    )


def _tick(ts: str, bidqty: float, askqty: float, seq: int) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id=f"T{seq}",
        event_type="tick",
        instrument_id="NIFTY-I",
        event_time=ts,
        available_at=ts,
        source="truedata",
        source_version="2.6",
        sequence=seq,
        payload={"ltp": 1.0, "volume": 1.0, "oi": 1.0, "bid": 1.0, "bidqty": bidqty, "ask": 1.0, "askqty": askqty},
    )


def _session():
    bars = [_bar(i, 100.0 + i) for i in range(20)]
    ticks = [_tick(bar.available_at, 80.0 + i, 20.0, i) for i, bar in enumerate(bars)]
    return bars, ticks


def test_coverage_is_not_a197_on_short_window():
    bars, ticks = _session()
    params = trial_identity_parameters(w_short=5, w_long=10)
    rows = score_trial_bars(bar_events=bars, tick_events=ticks, params=params)
    report = coverage_report(
        symbol="NIFTY-I",
        observations=rows,
        tick_count=len(ticks),
        bar_sequence_hash="bar-hash",
        tick_sequence_hash="tick-hash",
    )
    assert report.meets_a197 is False
    assert report.status == "TRIAL_NOT_A197"
    assert report.trading_days < A197_MIN_TRADING_DAYS
    assert report.bar_count < A197_MIN_BARS
    report.assert_not_a197()


def test_window_search_does_not_pick_a_production_pair():
    scores = score_window_candidates(19, [(5, 10), (5, 15), (20, 10)])
    assert scores[0].valid is True
    assert scores[0].reason == "TRIAL_PLACEHOLDER_SEARCH"
    assert scores[2].valid is False
    assert scores[2].reason == "A203_WINDOW_CONSTRAINT"


def test_walk_forward_train_cannot_see_test():
    bars, ticks = _session()
    params = trial_identity_parameters(w_short=5, w_long=10)
    rows = score_trial_bars(bar_events=bars, tick_events=ticks, params=params)
    mapped = observations_for_walk_forward(rows, horizon=timedelta(minutes=5))
    start = datetime(2026, 8, 13, 3, 15, tzinfo=timezone.utc)
    cycle = build_research_cycle(
        cycle_id="c-research",
        train_start=start,
        train_end=start + timedelta(minutes=10),
        validation_end=start + timedelta(minutes=15),
        test_end=start + timedelta(minutes=25),
        purge=timedelta(minutes=1),
        embargo=timedelta(minutes=1),
    )
    train_ids = {
        item.observation_id
        for item in mapped
        if assign_observation(item, cycle) is ObservationDisposition.TRAIN
    }
    test_ids = {
        item.observation_id
        for item in mapped
        if assign_observation(item, cycle) is ObservationDisposition.TEST
    }
    assert train_ids
    assert test_ids
    assert train_ids.isdisjoint(test_ids)


def test_train_only_estimate_and_refuse_v1_freeze(tmp_path):
    bars, ticks = _session()
    identity = trial_identity_parameters(w_short=5, w_long=10)
    rows = score_trial_bars(bar_events=bars, tick_events=ticks, params=identity)
    valid = [row for row in rows if row.result.status is FeatureStatus.VALID]
    estimated = estimate_params_from_train(valid, w_short=5, w_long=10)
    assert estimated.status == "TRIAL_NOT_A197_TRAIN_ONLY"
    dump_f101_parameters(estimated, tmp_path / "f101_parameters_trial.json")
    with pytest.raises(RuntimeError, match="f101_parameters_v1"):
        dump_f101_parameters(estimated, tmp_path / "f101_parameters_v1.json")


def test_research_e2e_simulates_fill_and_keeps_production_blocked():
    bars, ticks = _session()
    params = trial_identity_parameters(w_short=5, w_long=10)
    result = run_research_e2e(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=params,
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert result.label == "RESEARCH_NOT_LIVE"
    assert result.traded is True
    assert result.order is not None
    assert result.position_quantity == 1
    assert result.lifecycle_action is not None
    assert result.production_gate_authorized is False
    assert result.reference_formula_id in {"F-007", "F-008"}
    assert result.fill_price is not None
    assert result.accounting is not None
    assert result.accounting.profit_giveback >= 0.0
    assert evaluate_execution_gate().authorized is False
    assert_production_strategy_locked()
    for formula_id in STRATEGY_FORMULA_IDS:
        assert FORMULAS[formula_id].status is FormulaStatus.LOCKED
    table = research_formula_table()
    assert table["F-101"].status == "RESEARCH_CODE_PRESENT_REGISTRY_LOCKED"
    assert table["F-102"].status == "SPEC_GAP"
    assert result.opportunity is not None
    assert result.opportunity.recovered_conjunction is True
    assert result.opportunity.gates["DataValid"].status == "PASS"
    assert result.opportunity.gates["EconomicDecisionValid"].status == "SPEC_GAP"
    assert result.opportunity.formula_note == "not_F102_not_F103"


def test_f002_f003_and_executable_references():
    from app.engines.adaptive_edge.accounting import mark_accounting
    from app.engines.adaptive_edge.research_references import executable_reference

    snap = mark_accounting((0.0, 10.0, 6.0))
    assert snap.peak_pnl == 10.0
    assert snap.profit_giveback == 4.0

    ts = "2026-08-13T03:15:00+00:00"
    tick = _tick(ts, 80.0, 20.0, 0)
    # payload bid/ask prices are 1.0 in helper
    buy = executable_reference([tick], ts, "BUY")
    sell = executable_reference([tick], ts, "SELL")
    assert buy.formula_id == "F-007"
    assert sell.formula_id == "F-008"
    assert buy.status is FeatureStatus.VALID
    assert buy.price == 1.0
    missing = executable_reference([], ts, "BUY")
    assert missing.status is FeatureStatus.MISSING


def test_research_e2e_uses_explicit_f107_f108_inputs():
    from app.engines.adaptive_edge.research_e2e import ResearchSizingInputs
    from app.engines.adaptive_edge.risk_sizing import (
        ExecutionCostParameters,
        ParameterEstimationMethod,
        ParameterMetadata,
        ParameterValidationStatus,
        SizingParameters,
    )

    def param(name: str, value: float, units: str = "INR") -> ParameterMetadata:
        return ParameterMetadata(
            name=name,
            value=value,
            units=units,
            version="research-1",
            provenance="RESEARCH_NOT_LIVE_explicit",
            estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
            validation_status=ParameterValidationStatus.VALIDATED,
        )

    bars, ticks = _session()
    params = trial_identity_parameters(w_short=5, w_long=10)
    sizing = ResearchSizingInputs(
        authorized_risk=10.0,
        initial_stop=0.5,
        cost_params=ExecutionCostParameters(
            spread_cost=param("spread_cost", 0.0),
            expected_slippage=param("expected_slippage", 0.0),
            brokerage_per_unit=param("brokerage_per_unit", 0.0),
            exchange_charges_per_unit=param("exchange_charges_per_unit", 0.0),
            taxes_per_unit=param("taxes_per_unit", 0.0),
            latency_cost_per_unit=param("latency_cost_per_unit", 0.0),
        ),
        sizing_params=SizingParameters(
            max_position_qty=param("max_position_qty", 25.0, "contracts"),
            max_capital_allocation=param("max_capital_allocation", 1000.0),
            lot_size=param("lot_size", 1.0, "contracts"),
        ),
        issued_at="2026-08-13T03:15:00+00:00",
    )
    result = run_research_e2e(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=params,
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
        sizing_inputs=sizing,
    )
    assert result.traded is True
    assert result.sizing is not None
    assert result.sizing.final_quantity >= 1
    assert result.risk_per_unit is not None
    assert result.risk_per_unit.formula_id == "F-107"
    assert FORMULAS["F-107"].status is FormulaStatus.LOCKED
    assert result.opportunity is not None
    assert result.opportunity.gates["RiskValid"].status == "PASS"
    assert result.opportunity.gates["CapitalValid"].status == "PASS"
    assert result.opportunity.gates["SessionValid"].status == "FAIL"
    assert result.engine_state is not None
    assert result.engine_state.authorization is not None
    after_mode = __import__(
        "app.engines.adaptive_edge.state", fromlist=["StateEvent", "transition"]
    )
    moved = after_mode.transition(
        result.engine_state, after_mode.StateEvent.ENTER_INTRADAY
    ).resulting_state
    assert moved.authorization is result.engine_state.authorization
    assert moved.authorization.authorized_risk == result.engine_state.authorization.authorized_risk


def test_research_opportunity_does_not_invent_f102():
    from app.engines.adaptive_edge.f101 import F101Result
    from app.engines.adaptive_edge.feature_engine import (
        FeatureInput,
        FeatureProvenance,
        FeatureStatus,
        InstrumentContext,
        build_feature_snapshot,
    )
    from app.engines.adaptive_edge.research_opportunity import evaluate_research_opportunity
    from app.engines.adaptive_edge.research_references import ExecutableReference

    ts = "2026-08-13T03:20:00+00:00"
    inputs = [
        FeatureInput(name, 0.1, ts, FeatureStatus.VALID, FeatureProvenance())
        for name in ("LogReturn", "LiquidityImbalance", "VolatilityRatio")
    ]
    snap = build_feature_snapshot(
        snapshot_id="s1",
        strategy_version="trial-a206-3vec",
        feature_set_version="trial-not-a197",
        observation_cutoff_time=ts,
        decision_time=ts,
        instrument_context=InstrumentContext("NIFTY-I"),
        inputs=inputs,
    )
    f101 = F101Result(score=0.2, z={}, status=FeatureStatus.VALID, parameter_status="TRIAL_NOT_A197")
    ref = ExecutableReference("BUY", 100.0, ts, FeatureStatus.VALID, "F-007", "T0")
    opp = evaluate_research_opportunity(
        opportunity_id="o1",
        snapshot=snap,
        f101=f101,
        side="BUY",
        reference=ref,
    )
    assert opp.recovered_conjunction is True
    assert opp.gates["EconomicDecisionValid"].status == "SPEC_GAP"
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-103"].status is FormulaStatus.LOCKED


def test_operational_session_clock_is_not_f103():
    from app.engines.adaptive_edge.research_session import nse_regular_session

    assert nse_regular_session("2026-08-13T03:45:00+00:00") is True  # 09:15 IST
    assert nse_regular_session("2026-08-13T03:14:00+00:00") is False  # 08:44 IST
    assert FORMULAS["F-103"].status is FormulaStatus.LOCKED


def test_session_replay_blocks_second_entry_and_marks_later_bars():
    from app.engines.adaptive_edge.research_e2e import run_research_session

    bars, ticks = _session()
    params = trial_identity_parameters(w_short=5, w_long=10)
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=params,
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert session.entries == 1
    assert session.blocked_pyramid >= 1
    assert session.marks > 1
    assert session.last_accounting is not None
    assert session.last_accounting.profit_giveback >= 0.0
    assert session.production_gate_authorized is False
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-111"].status is FormulaStatus.LOCKED
    assert session.exits == 0
    assert session.reentries == 0
    assert session.software_complete is True
    assert session.incomplete_reasons == ()


def test_a126_cutoff_blocks_new_entry():
    from app.engines.adaptive_edge.research_session import a126_session_cutoff_reached

    assert a126_session_cutoff_reached("2026-08-13T09:15:00+00:00") is True  # 14:45 IST
    assert a126_session_cutoff_reached("2026-08-13T09:14:00+00:00") is False
    bars = []
    ticks = []
    for i in range(20):
        ts = f"2026-08-13T09:{15 + i:02d}:00+00:00"
        bars.append(
            CanonicalMarketEvent(
                record_id=f"C{i}",
                event_type="bar",
                instrument_id="NIFTY-I",
                event_time=ts,
                available_at=ts,
                source="truedata",
                source_version="2.6",
                payload={"open": 100.0 + i, "high": 100.0 + i, "low": 100.0 + i, "close": 100.0 + i, "volume": 1.0, "oi": 1.0},
            )
        )
        ticks.append(_tick(ts, 80.0, 20.0, i))
    result = run_research_e2e(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert result.traded is False
    assert result.skip_reason == "a126_session_cutoff"
    assert FORMULAS["F-111"].status is FormulaStatus.LOCKED


def test_a126_cutoff_flattens_open_position():
    from app.engines.adaptive_edge.research_e2e import run_research_session

    bars, ticks = _session()
    late = "2026-08-13T09:20:00+00:00"
    bars = list(bars) + [
        CanonicalMarketEvent(
            record_id="LATE",
            event_type="bar",
            instrument_id="NIFTY-I",
            event_time=late,
            available_at=late,
            source="truedata",
            source_version="2.6",
            payload={"open": 130.0, "high": 130.0, "low": 130.0, "close": 130.0, "volume": 1.0, "oi": 1.0},
        )
    ]
    ticks = list(ticks) + [_tick(late, 80.0, 20.0, 99)]
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert session.entries == 1
    assert session.exits == 1
    assert session.reentries == 0
    assert session.last_lifecycle_action == "EXIT_SESSION_CUTOFF"
    assert session.last_position_quantity == 0
    assert session.exit_fill_price is not None
    assert "session_cutoff_exit" in session.audit_stages
    assert session.software_complete is True
    assert session.incomplete_reasons == ()


def test_research_folds_do_not_overlap_train_and_test():
    from app.engines.adaptive_edge.research_pipeline import (
        ResearchWalkForwardSpec,
        summarize_research_folds,
    )
    from app.engines.adaptive_edge.trial_dataset import score_trial_bars

    bars, ticks = _session()
    rows = score_trial_bars(
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
    )
    summary = summarize_research_folds(
        rows,
        ResearchWalkForwardSpec(
            horizon=timedelta(minutes=1),
            purge=timedelta(minutes=1),
            embargo=timedelta(minutes=1),
            train_fraction=0.5,
            validation_fraction=0.2,
        ),
    )
    assert summary.train_test_overlap is False
    assert summary.train >= 1
    assert summary.test >= 1
    assert summary.label == "RESEARCH_PLACEHOLDER_SPLITS"


def _bar_at(ts: str, record_id: str, close: float) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id=record_id,
        event_type="bar",
        instrument_id="NIFTY-I",
        event_time=ts,
        available_at=ts,
        source="truedata",
        source_version="2.6",
        payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0, "oi": 1.0},
    )


def test_session_reenters_next_day_after_a126_flatten():
    from app.engines.adaptive_edge.research_e2e import run_research_session

    bars: list[CanonicalMarketEvent] = []
    ticks: list[CanonicalMarketEvent] = []
    day1 = datetime(2026, 8, 13, 3, 45, tzinfo=timezone.utc)  # 09:15 IST
    for i in range(16):
        ts = (day1 + timedelta(minutes=i)).isoformat()
        bars.append(_bar_at(ts, f"D1-{i}", 100.0 + i))
        ticks.append(_tick(ts, 80.0 + i, 20.0, i))
    late = "2026-08-13T09:20:00+00:00"  # 14:50 IST
    bars.append(_bar_at(late, "D1-CUTOFF", 130.0))
    ticks.append(_tick(late, 80.0, 20.0, 50))
    day2 = datetime(2026, 8, 14, 3, 45, tzinfo=timezone.utc)
    for i in range(16):
        ts = (day2 + timedelta(minutes=i)).isoformat()
        bars.append(_bar_at(ts, f"D2-{i}", 140.0 + i))
        ticks.append(_tick(ts, 70.0 + i, 30.0, 100 + i))
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert session.entries == 2
    assert session.exits == 1
    assert session.reentries == 1
    assert session.last_position_quantity > 0
    assert session.software_complete is True
    assert session.incomplete_reasons == ()
    assert "accounting" in session.audit_stages
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED


def test_walk_forward_estimates_on_train_and_rescores_test():
    from app.engines.adaptive_edge.research_pipeline import (
        ResearchWalkForwardSpec,
        evaluate_research_walk_forward,
    )

    bars = [_bar(i, 100.0 + i + (0.4 if i % 2 else 0.0)) for i in range(40)]
    ticks = [_tick(bar.available_at, 80.0 + i, 20.0, i) for i, bar in enumerate(bars)]
    rows = score_trial_bars(
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
    )
    ev = evaluate_research_walk_forward(
        rows,
        ResearchWalkForwardSpec(
            horizon=timedelta(minutes=1),
            purge=timedelta(minutes=1),
            embargo=timedelta(minutes=1),
            train_fraction=0.5,
            validation_fraction=0.2,
        ),
        w_short=5,
        w_long=10,
    )
    assert ev.summary.train_test_overlap is False
    assert ev.estimated_from_train_only is True
    assert ev.train_parameter_status == "TRIAL_NOT_A197_TRAIN_ONLY"
    assert ev.test_rescored >= 1
    assert ev.test_valid >= 1
    assert ev.validation_rescored >= 1
    assert ev.train_med is not None
    assert ev.reason == "TRIAL_NOT_A197_TRAIN_ONLY"


def test_session_daily_ledger_and_quality_are_not_a197():
    from app.engines.adaptive_edge.research_e2e import run_research_session

    bars, ticks = _session()
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
    )
    assert len(session.legs) == session.entries == 1
    assert len(session.daily) == 1
    assert session.daily[0].session_date == "2026-08-13"
    assert session.legs[0].entry_time
    assert session.legs[0].flattened is False
    assert session.quality is not None
    assert session.quality.meets_a197 is False
    assert session.quality.status == "TRIAL_NOT_A197_QUALITY"
    assert session.quality.missing_volatility_ratio >= 1
    assert session.artifact_digest
    assert session.holdout is None


def test_holdout_replay_uses_train_params_and_test_bars_only():
    from app.engines.adaptive_edge.research_e2e import run_research_session
    from app.engines.adaptive_edge.research_pipeline import ResearchWalkForwardSpec

    bars = [_bar(i, 100.0 + i + (0.4 if i % 2 else 0.0)) for i in range(40)]
    ticks = [_tick(bar.available_at, 80.0 + i, 20.0, i) for i, bar in enumerate(bars)]
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
        walk_forward_spec=ResearchWalkForwardSpec(
            horizon=timedelta(minutes=1),
            purge=timedelta(minutes=1),
            embargo=timedelta(minutes=1),
            train_fraction=0.5,
            validation_fraction=0.2,
        ),
    )
    assert session.walk_forward_eval is not None
    assert session.walk_forward_eval.estimated_from_train_only is True
    assert session.holdout is not None
    assert session.holdout.label == "RESEARCH_HOLDOUT_NOT_LIVE"
    assert session.holdout.used_train_params_only is True
    assert session.holdout.test_bar_count >= 1
    assert session.holdout.parameter_status == "TRIAL_NOT_A197_TRAIN_ONLY"
    assert session.software_complete is True
    assert session.artifact_digest
    assert session.quality is not None
    assert session.daily
