"""Machine-readable registry for Adaptive Edge mathematics.

The registry is deliberately conservative: a formula can only become
IMPLEMENTED after its canonical specification has been recovered and tests
have been attached. This prevents implementation code from silently becoming
the source of strategy truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FormulaStatus(str, Enum):
    ANCHORED = "anchored"
    IMPLEMENTED = "implemented"
    LOCKED = "locked"


@dataclass(frozen=True)
class FormulaDefinition:
    formula_id: str
    version: str
    name: str
    status: FormulaStatus
    units: str
    owner: str


FORMULAS: dict[str, FormulaDefinition] = {
    "F-001": FormulaDefinition("F-001", "1.0", "Causal availability", FormulaStatus.ANCHORED, "boolean", "feature_engine"),
    "F-002": FormulaDefinition("F-002", "1.0", "Peak P&L", FormulaStatus.ANCHORED, "accounting currency", "accounting"),
    "F-003": FormulaDefinition("F-003", "1.0", "Profit giveback", FormulaStatus.ANCHORED, "accounting currency", "accounting"),
    "F-004": FormulaDefinition("F-004", "1.0", "Expected net value", FormulaStatus.IMPLEMENTED, "value", "economic"),
    "F-005": FormulaDefinition("F-005", "1.0", "Risk authorization immutability", FormulaStatus.ANCHORED, "authorization state", "risk"),
    "F-006": FormulaDefinition("F-006", "1.0", "Mode/risk independence", FormulaStatus.ANCHORED, "state invariant", "risk"),
    "F-007": FormulaDefinition("F-007", "1.0", "Executable BUY reference", FormulaStatus.ANCHORED, "price", "execution"),
    "F-008": FormulaDefinition("F-008", "1.0", "Executable SELL reference", FormulaStatus.ANCHORED, "price", "execution"),
}

for _id, _name in {
    "F-101": "Feature normalization / feature score",
    "F-102": "Edge / prediction score",
    "F-103": "Opportunity eligibility",
    "F-104": "Dynamic-mode transition",
    "F-105": "Predictive-profit protection",
    "F-106": "Dynamic-risk schedule",
    "F-107": "Risk-per-unit",
    "F-108": "Position sizing",
    "F-109": "Instrument / option selection",
    "F-110": "Entry trigger",
    "F-111": "Exit trigger",
    "F-112": "Trailing / protection parameterization",
    "F-113": "Re-entry",
    "F-114": "Multi-position interaction",
}.items():
    FORMULAS[_id] = FormulaDefinition(_id, "0.0", _name, FormulaStatus.LOCKED, "unspecified", "unassigned")


def get_formula(formula_id: str) -> FormulaDefinition:
    try:
        return FORMULAS[formula_id]
    except KeyError as exc:
        raise KeyError(f"unknown Adaptive Edge formula ID: {formula_id}") from exc


def require_implemented(formula_id: str) -> FormulaDefinition:
    definition = get_formula(formula_id)
    if definition.status is not FormulaStatus.IMPLEMENTED:
        raise RuntimeError(
            f"Adaptive Edge formula {formula_id} is not executable: {definition.status.value}"
        )
    return definition
