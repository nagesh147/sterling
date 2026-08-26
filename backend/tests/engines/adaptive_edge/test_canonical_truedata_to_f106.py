from __future__ import annotations

import pytest

from app.engines.adaptive_edge.canonical_a_to_k_runner import run_truedata_bar_to_f106
from app.engines.adaptive_edge.f101_f106_contracts import F106OptionCandidate, ResearchContractError


BASE = dict(
    symbol="NIFTY",
    bar_record={"timestamp": "2026-08-19 09:16:00", "open": 24500, "high": 24540, "low": 24490, "close": 24530, "volume": 10000, "oi": 100000},
    receipt_time_iso="2026-08-19T03:46:05+00:00",
    feature_values={"close": 24530.0, "vwap": 24510.0, "poc": 24500.0, "cvd": 500.0},
    quality_ok=True,
    decision_time="2026-08-19T03:46:10+00:00",
    probabilities=(0.7, 0.2, 0.1),
    directional_edge=0.2,
    eligibility_reason="directional_edge_positive",
    expected_gross_value=80.0,
    execution_cost=20.0,
    conservative_net_value=60.0,
    minimum_net_value=10.0,
    horizons={"MICRO": 0.6, "SCALP": 0.4},
    selected_horizon="MICRO",
    option_candidates=(
        F106OptionCandidate("NIFTY-24500-CE", 60.0, True, True, True, True),
    ),
)


def test_canonical_truedata_event_crosses_f101_to_f106():
    result = run_truedata_bar_to_f106(**BASE)
    assert result.market_event.source == "truedata"
    assert result.market_event.event_type == "bar"
    assert result.market_event.available_at >= result.market_event.event_time
    assert result.upstream.selected_option.instrument_id == "NIFTY-24500-CE"
    assert result.downstream_admissible is True


def test_canonical_runner_preserves_missing_economics_fail_closed():
    data = {**BASE, "expected_gross_value": None, "conservative_net_value": None}
    result = run_truedata_bar_to_f106(**data)
    assert result.upstream.economics.eligible is False
    assert result.downstream_admissible is False


def test_canonical_runner_rejects_lookahead_at_f101():
    data = {**BASE, "decision_time": "2026-08-19T03:45:00+00:00"}
    with pytest.raises(ResearchContractError, match="lookahead"):
        run_truedata_bar_to_f106(**data)


def test_canonical_runner_is_deterministic():
    a = run_truedata_bar_to_f106(**BASE)
    b = run_truedata_bar_to_f106(**BASE)
    assert a.market_event.record_id == b.market_event.record_id
    assert a.market_event.event_time == b.market_event.event_time
    assert a.upstream == b.upstream
