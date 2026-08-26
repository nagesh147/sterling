"""Trial F-101 path: A206 3-vector + A196 operator. Registry stays LOCKED."""
from __future__ import annotations

import json
import math

import pytest

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.f101 import F101Parameters, evaluate_f101
from app.engines.adaptive_edge.feature_engine import FeatureInput, FeatureStatus
from app.engines.adaptive_edge.features_f101 import (
    F101_FEATURE_NAMES,
    assemble_f101_inputs,
    log_return,
    volatility_ratio,
)
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus


def test_a206_subset_excludes_delta_velocity():
    assert "DeltaVelocity" not in F101_FEATURE_NAMES
    assert F101_FEATURE_NAMES == ("LogReturn", "LiquidityImbalance", "VolatilityRatio")


def test_f101_registry_is_locked():
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED


def test_log_return_and_vr_formulas():
    value, status = log_return(110.0, 100.0)
    assert status is FeatureStatus.VALID
    assert value == pytest.approx(math.log(1.1))
    assert log_return(0.0, 100.0)[1] is FeatureStatus.MISSING

    returns = [0.001] * 10 + [0.05, -0.04, 0.06, -0.05, 0.04]
    vr, st = volatility_ratio(returns, w_short=5, w_long=15)
    assert st is FeatureStatus.VALID
    assert vr is not None and vr > 1.0
    assert volatility_ratio([0.01] * 3, w_short=5, w_long=15)[1] is FeatureStatus.MISSING
    with pytest.raises(ValueError):
        volatility_ratio([0.01] * 20, w_short=20, w_long=10)


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


def test_assemble_three_features_and_trial_score():
    bars = [_bar(i, 100.0 + i) for i in range(20)]
    ticks = [_tick(bars[-1].available_at, 80.0, 20.0, 0)]
    lr, li, vr = assemble_f101_inputs(
        bar_events=bars, index=19, tick_events=ticks, w_short=5, w_long=10
    )
    assert lr.status is FeatureStatus.VALID
    assert li.status is FeatureStatus.VALID
    assert li.value == pytest.approx(0.6)
    assert vr.status is FeatureStatus.VALID
    assert "DeltaVelocity" not in {lr.name, li.name, vr.name}

    params = F101Parameters(
        status="TRIAL_NOT_A197",
        w_short=5,
        w_long=10,
        med={n: 0.0 for n in F101_FEATURE_NAMES},
        scale={n: 1.349 for n in F101_FEATURE_NAMES},
        weights={n: 1.0 / 3.0 for n in F101_FEATURE_NAMES},
    )
    result = evaluate_f101({"LogReturn": lr, "LiquidityImbalance": li, "VolatilityRatio": vr}, params)
    assert result.status is FeatureStatus.VALID
    assert result.score is not None
    assert -1.0 < result.score < 1.0
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED


def test_evaluate_fail_closed_on_missing_and_rejects_production_status():
    missing = FeatureInput(name="LogReturn", value=None, available_at="2026-08-13T04:00:00+00:00", status=FeatureStatus.MISSING)
    ok = FeatureInput(name="X", value=1.0, available_at="2026-08-13T04:00:00+00:00", status=FeatureStatus.VALID)
    params = F101Parameters(
        status="TRIAL_NOT_A197",
        w_short=5,
        w_long=10,
        med={n: 0.0 for n in F101_FEATURE_NAMES},
        scale={n: 1.349 for n in F101_FEATURE_NAMES},
        weights={n: 1.0 / 3.0 for n in F101_FEATURE_NAMES},
    )
    features = {
        "LogReturn": missing,
        "LiquidityImbalance": ok,
        "VolatilityRatio": ok,
    }
    out = evaluate_f101(features, params)
    assert out.status is FeatureStatus.MISSING
    assert out.score is None

    with pytest.raises(RuntimeError, match="production freeze"):
        evaluate_f101(
            features,
            F101Parameters(
                status="FROZEN",
                w_short=5,
                w_long=10,
                med={n: 0.0 for n in F101_FEATURE_NAMES},
                scale={n: 1.349 for n in F101_FEATURE_NAMES},
                weights={n: 1.0 / 3.0 for n in F101_FEATURE_NAMES},
            ),
        )


def test_trial_dataset_scores_and_rejects_v1_freeze_path(tmp_path):
    from app.engines.adaptive_edge.execution_gate import evaluate_execution_gate
    from app.engines.adaptive_edge.f101 import (
        dump_f101_parameters,
        estimate_trial_parameters,
        trial_identity_parameters,
    )
    from app.engines.adaptive_edge.trial_dataset import (
        collect_valid_feature_values,
        score_trial_bars,
        score_trial_bars_unoptimized,
    )

    bars = [_bar(i, 100.0 + i) for i in range(20)]
    ticks = [_tick(bar.available_at, 80.0 + i, 20.0, i) for i, bar in enumerate(bars)]
    params = trial_identity_parameters(w_short=5, w_long=10)
    scored = score_trial_bars(bar_events=bars, tick_events=ticks, params=params)
    reference = score_trial_bars_unoptimized(bar_events=bars, tick_events=ticks, params=params)
    assert len(scored) == 20
    assert scored[-1].result.status is FeatureStatus.VALID
    assert scored[-1].result.score == pytest.approx(reference[-1].result.score)
    assert "DeltaVelocity" not in scored[-1].snapshot.values
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED
    assert evaluate_execution_gate().authorized is False

    values = collect_valid_feature_values(scored)
    estimated = estimate_trial_parameters(values, w_short=5, w_long=10)
    assert estimated.status == "TRIAL_NOT_A197_IN_SAMPLE"
    path = tmp_path / "f101_parameters_trial.json"
    dump_f101_parameters(estimated, path)
    assert json.loads(path.read_text())["not_a197"] is True
    with pytest.raises(RuntimeError, match="f101_parameters_v1"):
        dump_f101_parameters(estimated, tmp_path / "f101_parameters_v1.json")
