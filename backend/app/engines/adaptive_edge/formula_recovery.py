"""Validation harness for promoting recovered Adaptive Edge formulas.

This module does not define missing strategy mathematics. It validates that a
recovered definition contains enough metadata to become executable without
losing causal, numerical, or provenance semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class RecoveryStatus(str, Enum):
    RECOVERED = "recovered"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


@dataclass(frozen=True)
class RecoveredFormula:
    formula_id: str
    version: str
    name: str
    equation: str
    inputs: tuple[str, ...]
    units: str
    boundary_conditions: tuple[str, ...]
    causal_requirements: tuple[str, ...]
    source_evidence: tuple[str, ...]
    recovery_status: RecoveryStatus


REQUIRED_FIELDS: tuple[str, ...] = (
    "formula_id",
    "version",
    "name",
    "equation",
    "inputs",
    "units",
    "boundary_conditions",
    "causal_requirements",
    "source_evidence",
)


def validate_recovered_formula(formula: RecoveredFormula) -> None:
    """Fail closed unless the recovered formula is complete and unambiguous."""
    if not formula.formula_id.startswith("F-10"):
        raise ValueError("only strategy-specific Adaptive Edge formula IDs may use this recovery harness")
    if formula.recovery_status is not RecoveryStatus.RECOVERED:
        raise ValueError(f"formula {formula.formula_id} is {formula.recovery_status.value}, not recovered")
    if not formula.version or formula.version == "0.0":
        raise ValueError(f"formula {formula.formula_id} requires a real version")
    if not formula.equation.strip():
        raise ValueError(f"formula {formula.formula_id} requires an exact equation or executable pseudocode")
    if not formula.inputs:
        raise ValueError(f"formula {formula.formula_id} requires explicit inputs")
    if not formula.units.strip():
        raise ValueError(f"formula {formula.formula_id} requires units")
    if not formula.boundary_conditions:
        raise ValueError(f"formula {formula.formula_id} requires boundary conditions")
    if not formula.causal_requirements:
        raise ValueError(f"formula {formula.formula_id} requires causal availability requirements")
    if not formula.source_evidence:
        raise ValueError(f"formula {formula.formula_id} requires source evidence")


def validate_recovery_set(formulas: Sequence[RecoveredFormula]) -> None:
    """Validate a recovery batch before registry promotion."""
    ids = [f.formula_id for f in formulas]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Adaptive Edge formula IDs in recovery batch")
    for formula in formulas:
        validate_recovered_formula(formula)
