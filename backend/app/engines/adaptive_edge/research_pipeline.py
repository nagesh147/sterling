"""F-101 research pipeline: coverage, folds, window search, train-only estimate.

Not an A197 promotion. Not a production freeze. Registry stays LOCKED.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .f101 import F101Parameters, estimate_trial_parameters
from .feature_engine import FeatureStatus
from .features_f101 import F101_FEATURE_NAMES
from .trial_dataset import (
    F101TrialObservation,
    collect_valid_feature_values,
    rescore_trial_observations,
)
from .walk_forward import (
    EvaluationCycle,
    EvaluationObservation,
    ObservationDisposition,
    TemporalSpan,
    assign_observation,
)

A197_MIN_TRADING_DAYS = 120
A197_MIN_BARS = 45_000


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class CoverageReport:
    symbol: str
    bar_count: int
    tick_count: int
    trading_days: int
    valid_scores: int
    missing_scores: int
    li_valid: int
    first_decision_time: str | None
    last_decision_time: str | None
    bar_sequence_hash: str
    tick_sequence_hash: str
    meets_a197: bool
    status: str

    def assert_not_a197(self) -> None:
        if self.meets_a197:
            return
        if self.status.startswith("A197") or self.status == "PRODUCTION":
            raise RuntimeError("coverage report cannot claim A197 without meeting the contract")


def coverage_report(
    *,
    symbol: str,
    observations: Sequence[F101TrialObservation],
    tick_count: int,
    bar_sequence_hash: str,
    tick_sequence_hash: str,
) -> CoverageReport:
    days = {
        _parse_ts(item.decision_time).date()
        for item in observations
    }
    li_valid = sum(
        1
        for item in observations
        if item.snapshot.statuses.get("LiquidityImbalance") is FeatureStatus.VALID
    )
    valid = sum(1 for item in observations if item.result.status is FeatureStatus.VALID)
    missing = len(observations) - valid
    first = observations[0].decision_time if observations else None
    last = observations[-1].decision_time if observations else None
    meets = len(days) >= A197_MIN_TRADING_DAYS and len(observations) >= A197_MIN_BARS
    return CoverageReport(
        symbol=symbol,
        bar_count=len(observations),
        tick_count=tick_count,
        trading_days=len(days),
        valid_scores=valid,
        missing_scores=missing,
        li_valid=li_valid,
        first_decision_time=first,
        last_decision_time=last,
        bar_sequence_hash=bar_sequence_hash,
        tick_sequence_hash=tick_sequence_hash,
        meets_a197=meets,
        status="A197_COVERAGE_MET" if meets else "TRIAL_NOT_A197",
    )


def observations_for_walk_forward(
    rows: Sequence[F101TrialObservation],
    *,
    horizon: timedelta,
) -> list[EvaluationObservation]:
    """Map scored bars to A39 observations. Horizon is explicit; not inferred."""
    out: list[EvaluationObservation] = []
    for row in rows:
        decision = _parse_ts(row.decision_time)
        available = max(
            (_parse_ts(ts) for ts in row.snapshot.available_at.values()),
            default=decision,
        )
        maturity = decision + horizon
        out.append(
            EvaluationObservation(
                observation_id=row.bar_record_id,
                decision_time=decision,
                feature_available_time=available,
                label_maturity_time=maturity,
                outcome_span=TemporalSpan(decision, maturity),
            )
        )
    return out


def build_research_cycle(
    *,
    cycle_id: str,
    train_start: datetime,
    train_end: datetime,
    validation_end: datetime,
    test_end: datetime,
    purge: timedelta,
    embargo: timedelta,
) -> EvaluationCycle:
    """Caller supplies every boundary. Purge/embargo are not defaulted."""
    val_start = train_end + purge
    test_start = validation_end + embargo
    return EvaluationCycle(
        cycle_id=cycle_id,
        training=TemporalSpan(train_start, train_end),
        validation=TemporalSpan(val_start, validation_end),
        test=TemporalSpan(test_start, test_end),
        purge=TemporalSpan(train_end, val_start) if purge.total_seconds() > 0 else None,
        embargo=TemporalSpan(validation_end, test_start) if embargo.total_seconds() > 0 else None,
        feature_policy_version="trial-a206-3vec",
        label_policy_version="research-horizon-explicit",
        model_policy_version="trial-not-a197",
    )


@dataclass(frozen=True)
class WindowCandidateScore:
    w_short: int
    w_long: int
    valid: bool
    n_valid_vr: int
    reason: str


def score_window_candidates(
    n_returns: int,
    candidates: Sequence[tuple[int, int]],
) -> list[WindowCandidateScore]:
    """A203 search primitive. Does not select a production window."""
    scores: list[WindowCandidateScore] = []
    for w_short, w_long in candidates:
        if w_short < 2 or w_short >= w_long:
            scores.append(
                WindowCandidateScore(w_short, w_long, False, 0, "A203_WINDOW_CONSTRAINT")
            )
            continue
        n_valid = max(0, n_returns - w_long + 1) if n_returns >= w_long else 0
        scores.append(
            WindowCandidateScore(
                w_short,
                w_long,
                n_valid > 0,
                n_valid,
                "TRIAL_PLACEHOLDER_SEARCH",
            )
        )
    return scores


@dataclass(frozen=True)
class ResearchWalkForwardSpec:
    horizon: timedelta
    purge: timedelta
    embargo: timedelta
    train_fraction: float
    validation_fraction: float
    label: str = "RESEARCH_PLACEHOLDER_SPLITS"


@dataclass(frozen=True)
class ResearchFoldSummary:
    label: str
    train: int
    validation: int
    test: int
    ineligible: int
    train_test_overlap: bool
    cycle_id: str


def _placeholder_cycle(
    rows: Sequence[F101TrialObservation],
    spec: ResearchWalkForwardSpec,
) -> tuple[EvaluationCycle, list[EvaluationObservation]] | None:
    if not (0 < spec.train_fraction < 1 and 0 < spec.validation_fraction < 1):
        raise ValueError("fold fractions must be in (0, 1)")
    if spec.train_fraction + spec.validation_fraction >= 1:
        raise ValueError("train+validation fractions must leave a test remainder")
    mapped = observations_for_walk_forward(rows, horizon=spec.horizon)
    if len(mapped) < 3:
        return None
    start = mapped[0].decision_time
    end = mapped[-1].decision_time
    span = end - start
    if span.total_seconds() <= 0:
        return None
    train_end = start + span * spec.train_fraction
    validation_end = start + span * (spec.train_fraction + spec.validation_fraction)
    cycle = build_research_cycle(
        cycle_id="research-placeholder-1",
        train_start=start,
        train_end=train_end,
        validation_end=validation_end,
        test_end=end + timedelta(microseconds=1),
        purge=spec.purge,
        embargo=spec.embargo,
    )
    return cycle, mapped


def summarize_research_folds(
    rows: Sequence[F101TrialObservation],
    spec: ResearchWalkForwardSpec,
) -> ResearchFoldSummary:
    """Split the observed span with caller fractions. Not an A197 fold."""
    built = _placeholder_cycle(rows, spec)
    if built is None:
        empty_id = "research-empty" if len(rows) < 3 else "research-zero-span"
        return ResearchFoldSummary(spec.label, 0, 0, 0, 0, False, empty_id)
    cycle, mapped = built
    counts = {item: 0 for item in ObservationDisposition}
    for obs in mapped:
        counts[assign_observation(obs, cycle)] += 1
    train_ids = {
        obs.observation_id
        for obs in mapped
        if assign_observation(obs, cycle) is ObservationDisposition.TRAIN
    }
    test_ids = {
        obs.observation_id
        for obs in mapped
        if assign_observation(obs, cycle) is ObservationDisposition.TEST
    }
    return ResearchFoldSummary(
        label=spec.label,
        train=counts[ObservationDisposition.TRAIN],
        validation=counts[ObservationDisposition.VALIDATION],
        test=counts[ObservationDisposition.TEST],
        ineligible=counts[ObservationDisposition.INELIGIBLE],
        train_test_overlap=bool(train_ids & test_ids),
        cycle_id=cycle.cycle_id,
    )


@dataclass(frozen=True)
class ResearchWalkForwardEval:
    """Train-only estimate applied to held-out test scores. Not an A197 promotion."""

    summary: ResearchFoldSummary
    train_parameter_status: str | None
    train_med: dict[str, float] | None
    train_scale: dict[str, float] | None
    test_rescored: int
    test_valid: int
    test_mean_score: float | None
    validation_rescored: int
    validation_valid: int
    validation_mean_score: float | None
    estimated_from_train_only: bool
    reason: str


@dataclass(frozen=True)
class ResearchQualityReport:
    """Entitled-window quality. Does not promote the cache to A197."""

    missing_score_rate: float
    li_valid_rate: float
    missing_log_return: int
    missing_liquidity_imbalance: int
    missing_volatility_ratio: int
    bars_outside_session: int
    bars_after_a126_cutoff: int
    max_li_quote_lag_seconds: float | None
    mean_li_quote_lag_seconds: float | None
    meets_a197: bool
    status: str


def research_artifact_digest(
    *,
    bar_sequence_hash: str,
    tick_sequence_hash: str,
    label: str,
) -> str:
    payload = f"{label}|{bar_sequence_hash}|{tick_sequence_hash}".encode()
    return hashlib.sha256(payload).hexdigest()


def quality_report(
    coverage: CoverageReport,
    observations: Sequence[F101TrialObservation],
    *,
    session_valid,
    cutoff_reached,
) -> ResearchQualityReport:
    n = max(coverage.bar_count, 1)
    missing = {name: 0 for name in F101_FEATURE_NAMES}
    lags: list[float] = []
    for item in observations:
        for name in F101_FEATURE_NAMES:
            if item.snapshot.statuses.get(name) is not FeatureStatus.VALID:
                missing[name] += 1
        li_at = item.snapshot.available_at.get("LiquidityImbalance")
        if (
            li_at
            and item.snapshot.statuses.get("LiquidityImbalance") is FeatureStatus.VALID
        ):
            lag = (_parse_ts(item.decision_time) - _parse_ts(li_at)).total_seconds()
            if lag >= 0:
                lags.append(lag)
    return ResearchQualityReport(
        missing_score_rate=coverage.missing_scores / n,
        li_valid_rate=coverage.li_valid / n,
        missing_log_return=missing["LogReturn"],
        missing_liquidity_imbalance=missing["LiquidityImbalance"],
        missing_volatility_ratio=missing["VolatilityRatio"],
        bars_outside_session=sum(1 for item in observations if not session_valid(item.decision_time)),
        bars_after_a126_cutoff=sum(1 for item in observations if cutoff_reached(item.decision_time)),
        max_li_quote_lag_seconds=max(lags) if lags else None,
        mean_li_quote_lag_seconds=(sum(lags) / len(lags)) if lags else None,
        meets_a197=coverage.meets_a197,
        status="TRIAL_NOT_A197_QUALITY",
    )


def partition_research_rows(
    rows: Sequence[F101TrialObservation],
    spec: ResearchWalkForwardSpec,
) -> dict[ObservationDisposition, list[F101TrialObservation]]:
    built = _placeholder_cycle(rows, spec)
    buckets: dict[ObservationDisposition, list[F101TrialObservation]] = {
        item: [] for item in ObservationDisposition
    }
    if built is None:
        return buckets
    cycle, mapped = built
    by_id = {row.bar_record_id: row for row in rows}
    for obs in mapped:
        row = by_id.get(obs.observation_id)
        if row is not None:
            buckets[assign_observation(obs, cycle)].append(row)
    return buckets


def evaluate_research_walk_forward(
    rows: Sequence[F101TrialObservation],
    spec: ResearchWalkForwardSpec,
    *,
    w_short: int,
    w_long: int,
) -> ResearchWalkForwardEval:
    """Estimate Med/Scale on TRAIN only, then rescore TEST. Never fits on test."""
    summary = summarize_research_folds(rows, spec)
    empty = ResearchWalkForwardEval(
        summary=summary,
        train_parameter_status=None,
        train_med=None,
        train_scale=None,
        test_rescored=0,
        test_valid=0,
        test_mean_score=None,
        validation_rescored=0,
        validation_valid=0,
        validation_mean_score=None,
        estimated_from_train_only=False,
        reason="insufficient_train",
    )
    if summary.train_test_overlap:
        return ResearchWalkForwardEval(
            **{**empty.__dict__, "reason": "train_test_overlap"}
        )
    parts = partition_research_rows(rows, spec)
    train_rows = parts[ObservationDisposition.TRAIN]
    test_rows = parts[ObservationDisposition.TEST]
    if not train_rows or not test_rows:
        return ResearchWalkForwardEval(**{**empty.__dict__, "reason": "empty_train_or_test"})
    try:
        params = estimate_params_from_train(train_rows, w_short=w_short, w_long=w_long)
    except ValueError:
        return empty
    def _score_fold(fold_rows: Sequence[F101TrialObservation]) -> tuple[int, int, float | None]:
        rescored = rescore_trial_observations(fold_rows, params)
        valid_scores = [
            item.result.score
            for item in rescored
            if item.result.status is FeatureStatus.VALID and item.result.score is not None
        ]
        mean = (sum(valid_scores) / len(valid_scores)) if valid_scores else None
        return len(rescored), len(valid_scores), mean

    test_n, test_valid, test_mean = _score_fold(test_rows)
    val_n, val_valid, val_mean = _score_fold(parts[ObservationDisposition.VALIDATION])
    return ResearchWalkForwardEval(
        summary=summary,
        train_parameter_status=params.status,
        train_med=dict(params.med),
        train_scale=dict(params.scale),
        test_rescored=test_n,
        test_valid=test_valid,
        test_mean_score=test_mean,
        validation_rescored=val_n,
        validation_valid=val_valid,
        validation_mean_score=val_mean,
        estimated_from_train_only=True,
        reason="TRIAL_NOT_A197_TRAIN_ONLY",
    )


def estimate_params_from_train(
    train_rows: Sequence[F101TrialObservation],
    *,
    w_short: int,
    w_long: int,
) -> F101Parameters:
    values = collect_valid_feature_values(train_rows)
    params = estimate_trial_parameters(values, w_short=w_short, w_long=w_long)
    object.__setattr__(params, "status", "TRIAL_NOT_A197_TRAIN_ONLY")
    if set(params.med) != set(F101_FEATURE_NAMES):
        raise RuntimeError("train estimate must cover the A206 subset")
    return params
