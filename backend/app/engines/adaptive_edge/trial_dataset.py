"""Assemble a trial F-101 dataset from canonical bars + ticks.

This is a development E2E path on an entitled window. It does not unlock
F-101, does not create a production freeze, and is not an A197 calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .event_boundary import CanonicalMarketEvent
from .f101 import F101Parameters, F101Result, evaluate_f101
from .feature_engine import (
    FeatureInput,
    FeatureProvenance,
    FeatureSnapshot,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)
from .features_f101 import (
    F101_FEATURE_NAMES,
    assemble_f101_inputs,
    log_return_at,
    volatility_ratio_at,
)
from .liquidity_imbalance import compute_liquidity_imbalance

TRIAL_STRATEGY_VERSION = "trial-a206-3vec"
TRIAL_FEATURE_SET_VERSION = "trial-not-a197"


@dataclass(frozen=True)
class F101TrialObservation:
    bar_index: int
    bar_record_id: str
    decision_time: str
    snapshot: FeatureSnapshot
    result: F101Result


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed


def build_f101_snapshot(
    inputs: Sequence[FeatureInput],
    *,
    instrument_id: str,
    decision_time: str,
    snapshot_id: str,
) -> FeatureSnapshot:
    return build_feature_snapshot(
        snapshot_id=snapshot_id,
        strategy_version=TRIAL_STRATEGY_VERSION,
        feature_set_version=TRIAL_FEATURE_SET_VERSION,
        observation_cutoff_time=decision_time,
        decision_time=decision_time,
        instrument_context=InstrumentContext(instrument_id=instrument_id),
        inputs=list(inputs),
        formula_ids=(),
    )


def _liquidity_from_quote(
    quote: CanonicalMarketEvent | None, decision_time: str
) -> FeatureInput:
    if quote is None:
        return FeatureInput(
            name="LiquidityImbalance",
            value=None,
            available_at=decision_time,
            status=FeatureStatus.MISSING,
            provenance=FeatureProvenance(source_event_ids=()),
        )
    value, status = compute_liquidity_imbalance(
        quote.payload.get("bidqty"),
        quote.payload.get("askqty"),
    )
    return FeatureInput(
        name="LiquidityImbalance",
        value=value,
        available_at=quote.available_at,
        status=status,
        provenance=FeatureProvenance(source_event_ids=(quote.record_id,)),
    )


def _advance_last_quote(
    ticks: Sequence[CanonicalMarketEvent],
    cursor: int,
    decision_time: str,
) -> tuple[CanonicalMarketEvent | None, int]:
    cutoff = _parse_ts(decision_time)
    index = cursor
    while index + 1 < len(ticks) and _parse_ts(ticks[index + 1].available_at) <= cutoff:
        index += 1
    if index < 0:
        return None, index
    return ticks[index], index


def score_trial_bars(
    *,
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent],
    params: F101Parameters,
) -> list[F101TrialObservation]:
    """Score each bar close with the A206 3-vector. Registry stays LOCKED."""
    bars = sorted(bar_events, key=lambda event: (event.event_time, event.record_id))
    ticks = sorted(
        (event for event in tick_events if event.event_type == "tick"),
        key=lambda event: (
            event.available_at,
            event.event_time,
            event.sequence or 0,
            event.record_id,
        ),
    )
    observations: list[F101TrialObservation] = []
    returns: list[float] = []
    return_ids: list[str] = []
    tick_cursor = -1
    for index, bar in enumerate(bars):
        lr = log_return_at(bars, index)
        if lr.status is FeatureStatus.VALID and lr.value is not None:
            returns.append(lr.value)
            return_ids.extend(lr.provenance.source_event_ids)
        vr = volatility_ratio_at(
            returns,
            bar.available_at,
            tuple(return_ids[-params.w_long * 2 :]) if return_ids else (bar.record_id,),
            w_short=params.w_short,
            w_long=params.w_long,
        )
        quote, tick_cursor = _advance_last_quote(ticks, tick_cursor, bar.available_at)
        li = _liquidity_from_quote(quote, bar.available_at)
        snapshot = build_f101_snapshot(
            (lr, li, vr),
            instrument_id=bar.instrument_id,
            decision_time=bar.available_at,
            snapshot_id=f"TRIAL-{bar.record_id}",
        )
        result = evaluate_f101(
            {"LogReturn": lr, "LiquidityImbalance": li, "VolatilityRatio": vr},
            params,
        )
        observations.append(
            F101TrialObservation(
                bar_index=index,
                bar_record_id=bar.record_id,
                decision_time=bar.available_at,
                snapshot=snapshot,
                result=result,
            )
        )
    return observations


def collect_valid_feature_values(
    observations: Sequence[F101TrialObservation],
) -> dict[str, list[float]]:
    values = {name: [] for name in F101_FEATURE_NAMES}
    for item in observations:
        if any(item.snapshot.statuses[name] is not FeatureStatus.VALID for name in F101_FEATURE_NAMES):
            continue
        for name in F101_FEATURE_NAMES:
            value = item.snapshot.values[name]
            if value is not None:
                values[name].append(float(value))
    return values


def rescore_trial_observations(
    observations: Sequence[F101TrialObservation],
    params: F101Parameters,
) -> list[F101TrialObservation]:
    """Re-evaluate F-101 on already-built snapshots. Features are not recomputed."""
    rescored: list[F101TrialObservation] = []
    for item in observations:
        features = {
            name: FeatureInput(
                name=name,
                value=item.snapshot.values[name],
                available_at=item.snapshot.available_at[name],
                status=item.snapshot.statuses[name],
                provenance=item.snapshot.provenance[name],
            )
            for name in F101_FEATURE_NAMES
        }
        rescored.append(
            F101TrialObservation(
                bar_index=item.bar_index,
                bar_record_id=item.bar_record_id,
                decision_time=item.decision_time,
                snapshot=item.snapshot,
                result=evaluate_f101(features, params),
            )
        )
    return rescored


def score_trial_bars_unoptimized(
    *,
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent],
    params: F101Parameters,
) -> list[F101TrialObservation]:
    """Reference path that calls assemble_f101_inputs at each index."""
    observations: list[F101TrialObservation] = []
    for index, bar in enumerate(bar_events):
        lr, li, vr = assemble_f101_inputs(
            bar_events=bar_events,
            index=index,
            tick_events=tick_events,
            w_short=params.w_short,
            w_long=params.w_long,
        )
        snapshot = build_f101_snapshot(
            (lr, li, vr),
            instrument_id=bar.instrument_id,
            decision_time=bar.available_at,
            snapshot_id=f"TRIAL-{bar.record_id}",
        )
        result = evaluate_f101(
            {"LogReturn": lr, "LiquidityImbalance": li, "VolatilityRatio": vr},
            params,
        )
        observations.append(
            F101TrialObservation(
                bar_index=index,
                bar_record_id=bar.record_id,
                decision_time=bar.available_at,
                snapshot=snapshot,
                result=result,
            )
        )
    return observations
