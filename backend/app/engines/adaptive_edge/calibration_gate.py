"""Fail-closed readiness gate for F-101 calibration.

This module does not calibrate parameters and does not promote F-101.
It only determines whether the supplied dataset/report is eligible to enter
A197 calibration. Missing provider history, insufficient coverage, invalid
feature completeness, or stale/causally invalid observations block entry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .research_pipeline import (
    A197_MIN_BARS,
    A197_MIN_TRADING_DAYS,
    CoverageReport,
    ResearchQualityReport,
)

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class CalibrationGateDecision:
    allowed: bool
    reasons: tuple[str, ...]
    status: str

    def assert_allowed(self) -> None:
        if not self.allowed:
            raise RuntimeError("F-101 calibration blocked: " + "; ".join(self.reasons))


def _valid_sha256(value: str | None) -> bool:
    return value is not None and _SHA256_RE.fullmatch(value) is not None


def assess_f101_calibration_readiness(
    coverage: CoverageReport,
    quality: ResearchQualityReport,
    *,
    dataset_sha256: str | None,
    canonical_sequence_hash: str | None,
) -> CalibrationGateDecision:
    """Return a fail-closed A197 entry decision.

    The gate deliberately checks evidence supplied by the caller rather than
    deriving missing strategy assumptions. A true result means only that the
    dataset may enter calibration; it does not authorize parameter promotion.
    """
    reasons: list[str] = []

    if coverage.bar_count < A197_MIN_BARS:
        reasons.append(f"bar_coverage<{A197_MIN_BARS}")
    if coverage.trading_days < A197_MIN_TRADING_DAYS:
        reasons.append(f"trading_day_coverage<{A197_MIN_TRADING_DAYS}")
    if coverage.tick_count <= 0:
        reasons.append("tick_history_missing")
    if coverage.li_valid < A197_MIN_BARS:
        reasons.append("liquidity_imbalance_incomplete")
    if quality.missing_score_rate > 0.001:
        reasons.append("missing_score_rate>0.1%")
    if quality.bars_outside_session > 0:
        reasons.append("observations_outside_session")
    if quality.bars_after_a126_cutoff > 0:
        reasons.append("observations_after_a126_cutoff")
    if not _valid_sha256(dataset_sha256):
        reasons.append("dataset_sha256_missing")
    if not _valid_sha256(canonical_sequence_hash):
        reasons.append("canonical_sequence_hash_missing")

    if reasons:
        return CalibrationGateDecision(False, tuple(reasons), "A197_CALIBRATION_BLOCKED")
    return CalibrationGateDecision(True, (), "A197_CALIBRATION_ELIGIBLE")
