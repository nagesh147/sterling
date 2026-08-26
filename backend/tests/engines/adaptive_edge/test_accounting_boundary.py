from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.accounting_boundary import (
    AccountingBoundaryError,
    CashEffect,
    ExecutionCost,
    RiskReconciliationBoundary,
    ValuationObservation,
    net_economic_result,
)

T0 = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)


def test_cash_effect_requires_policy_and_currency():
    with pytest.raises(AccountingBoundaryError):
        CashEffect("c1", "f1", 100.0, "", T0, "v1")


def test_execution_cost_requires_source_and_policy():
    with pytest.raises(AccountingBoundaryError):
        ExecutionCost("c1", "f1", "fee", 1.0, "INR", T0, "", "v1")


def test_valuation_rejects_availability_before_observation():
    """Availability must not precede observation — that is a lookahead value.

    T0 is 10:00, so the availability argument was T0.replace(minute=9) = 10:09,
    which is nine minutes *after* observation and therefore perfectly valid. The
    guard was right not to raise. hour=9 gives the 09:00 the name describes.
    """
    with pytest.raises(AccountingBoundaryError, match="availability_time"):
        ValuationObservation("NIFTY", "last", 100.0, "provider", T0, T0.replace(hour=9), 0, "v1")


def test_net_result_subtracts_only_explicit_costs():
    cost = ExecutionCost("c1", "f1", "fee", 2.0, "INR", T0, "provider", "v1")
    assert net_economic_result(100.0, (cost,)) == 98.0


def test_risk_reconciliation_is_reference_only():
    result = RiskReconciliationBoundary("r1", "auth1", T0, "authorized-risk", "actual-state", "PENDING")
    assert result.authorized_risk_reference != result.actual_state_reference
