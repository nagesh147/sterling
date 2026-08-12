from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.decision_utility import (
    DecisionAssessment,
    DecisionFailure,
    DecisionUtilityError,
    EconomicContext,
    require_economic_value,
)

UTC = timezone.utc


def test_missing_economic_inputs_fail_closed():
    context = EconomicContext("econ-1", 100.0, None, None, None)
    with pytest.raises(DecisionUtilityError, match="economic value is unavailable"):
        require_economic_value(context)


def test_structural_net_value_is_gross_minus_ex_ante_cost():
    context = EconomicContext("econ-1", 100.0, 15.0, "risk-1", "exec-1")
    assert require_economic_value(context) == 85.0


def test_ineligible_decision_requires_explicit_failure_reason():
    with pytest.raises(DecisionUtilityError, match="explicit failure reason"):
        DecisionAssessment(
            "d-1", "p-1", "snap-1", "econ-1", None, None, "policy-1",
            datetime(2026, 8, 12, 10, 0, tzinfo=UTC), False,
        )


def test_eligible_decision_cannot_have_failure_reason():
    with pytest.raises(DecisionUtilityError, match="eligible decision"):
        DecisionAssessment(
            "d-1", "p-1", "snap-1", "econ-1", None, None, "policy-1",
            datetime(2026, 8, 12, 10, 0, tzinfo=UTC), True, DecisionFailure.RISK_CONSTRAINT,
        )
