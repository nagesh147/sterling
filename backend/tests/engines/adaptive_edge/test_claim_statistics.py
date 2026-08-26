import pytest

from app.engines.adaptive_edge.claim_statistics import (
    ClaimStatisticsError,
    CorrectionStatus,
    StatisticalValidityContract,
)


def test_unresolved_correction_cannot_be_a_claim():
    contract = StatisticalValidityContract.unresolved("eval-1", "registry-1", 10)
    assert contract.claim_eligible() is False


def test_unresolved_correction_rejects_adjusted_claim():
    with pytest.raises(ClaimStatisticsError):
        StatisticalValidityContract(
            "eval-1", "registry-1", 10, CorrectionStatus.UNRESOLVED,
            adjusted_claim=True,
        )


def test_applied_correction_requires_method_identity():
    with pytest.raises(ClaimStatisticsError):
        StatisticalValidityContract(
            "eval-1", "registry-1", 10, CorrectionStatus.APPLIED,
            adjusted_claim=True,
        )


def test_applied_correction_makes_claim_eligible():
    contract = StatisticalValidityContract(
        "eval-1", "registry-1", 10, CorrectionStatus.APPLIED,
        correction_method_id="source-defined-method",
        adjusted_claim=True,
    )
    assert contract.claim_eligible() is True


def test_invalid_significance_level_rejected():
    with pytest.raises(ClaimStatisticsError):
        StatisticalValidityContract(
            "eval-1", "registry-1", 10, CorrectionStatus.SPECIFIED,
            correction_method_id="method", significance_level=1.0,
        )
