from app.engines.adaptive_edge.calibration_gate import assess_f101_calibration_readiness
from app.engines.adaptive_edge.research_pipeline import CoverageReport, ResearchQualityReport


def _coverage(**overrides):
    values = dict(
        symbol="NIFTY-I",
        bar_count=45_000,
        tick_count=100_000,
        trading_days=120,
        valid_scores=45_000,
        missing_scores=0,
        li_valid=45_000,
        first_decision_time="2026-01-01T09:15:00+00:00",
        last_decision_time="2026-07-01T15:00:00+00:00",
        bar_sequence_hash="a" * 64,
        tick_sequence_hash="b" * 64,
        meets_a197=True,
        status="A197_COVERAGE_MET",
    )
    values.update(overrides)
    return CoverageReport(**values)


def _quality(**overrides):
    values = dict(
        missing_score_rate=0.0,
        li_valid_rate=1.0,
        missing_log_return=0,
        missing_liquidity_imbalance=0,
        missing_volatility_ratio=0,
        bars_outside_session=0,
        bars_after_a126_cutoff=0,
        max_li_quote_lag_seconds=0.2,
        mean_li_quote_lag_seconds=0.1,
        meets_a197=True,
        status="TRIAL_NOT_A197_QUALITY",
    )
    values.update(overrides)
    return ResearchQualityReport(**values)


def test_calibration_gate_is_fail_closed_without_provenance():
    decision = assess_f101_calibration_readiness(
        _coverage(),
        _quality(),
        dataset_sha256=None,
        canonical_sequence_hash=None,
    )
    assert decision.allowed is False
    assert decision.status == "A197_CALIBRATION_BLOCKED"
    assert "dataset_sha256_missing" in decision.reasons
    assert "canonical_sequence_hash_missing" in decision.reasons


def test_calibration_gate_accepts_only_complete_entry_evidence():
    decision = assess_f101_calibration_readiness(
        _coverage(),
        _quality(),
        dataset_sha256="a" * 64,
        canonical_sequence_hash="b" * 64,
    )
    assert decision.allowed is True
    assert decision.status == "A197_CALIBRATION_ELIGIBLE"
    assert decision.reasons == ()


def test_calibration_gate_blocks_insufficient_true_data_history():
    decision = assess_f101_calibration_readiness(
        _coverage(bar_count=44_999, trading_days=119, li_valid=44_999),
        _quality(),
        dataset_sha256="a" * 64,
        canonical_sequence_hash="b" * 64,
    )
    assert decision.allowed is False
    assert "bar_coverage<45000" in decision.reasons
    assert "trading_day_coverage<120" in decision.reasons
    assert "liquidity_imbalance_incomplete" in decision.reasons


def test_calibration_gate_blocks_quality_contamination():
    decision = assess_f101_calibration_readiness(
        _coverage(),
        _quality(missing_score_rate=0.0011, bars_outside_session=1, bars_after_a126_cutoff=2),
        dataset_sha256="a" * 64,
        canonical_sequence_hash="b" * 64,
    )
    assert decision.allowed is False
    assert "missing_score_rate>0.1%" in decision.reasons
    assert "observations_outside_session" in decision.reasons
    assert "observations_after_a126_cutoff" in decision.reasons


def test_calibration_gate_rejects_non_hex_64_character_hashes():
    decision = assess_f101_calibration_readiness(
        _coverage(),
        _quality(),
        dataset_sha256="z" * 64,
        canonical_sequence_hash="not-a-sha" + "x" * 54,
    )
    assert decision.allowed is False
    assert "dataset_sha256_missing" in decision.reasons
    assert "canonical_sequence_hash_missing" in decision.reasons
