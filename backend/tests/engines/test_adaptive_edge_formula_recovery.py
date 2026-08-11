import pytest

from app.engines.adaptive_edge.formula_recovery import (
    RecoveredFormula,
    RecoveryStatus,
    validate_recovered_formula,
    validate_recovery_set,
)


def complete_formula(**overrides):
    values = dict(
        formula_id="F-101",
        version="1.0",
        name="Recovered feature formula",
        equation="x = explicit_equation(x_1, x_2)",
        inputs=("x_1", "x_2"),
        units="dimensionless",
        boundary_conditions=("x is finite",),
        causal_requirements=("all inputs available at decision time",),
        source_evidence=("strategy specification §F-101",),
        recovery_status=RecoveryStatus.RECOVERED,
    )
    values.update(overrides)
    return RecoveredFormula(**values)


def test_complete_recovery_is_accepted():
    validate_recovered_formula(complete_formula())


def test_ambiguous_formula_is_rejected():
    with pytest.raises(ValueError, match="ambiguous"):
        validate_recovered_formula(complete_formula(recovery_status=RecoveryStatus.AMBIGUOUS))


def test_missing_equation_is_rejected():
    with pytest.raises(ValueError, match="exact equation"):
        validate_recovered_formula(complete_formula(equation=""))


def test_missing_source_evidence_is_rejected():
    with pytest.raises(ValueError, match="source evidence"):
        validate_recovered_formula(complete_formula(source_evidence=()))


def test_recovery_batch_rejects_duplicate_ids():
    with pytest.raises(ValueError, match="duplicate"):
        validate_recovery_set([complete_formula(), complete_formula()])
