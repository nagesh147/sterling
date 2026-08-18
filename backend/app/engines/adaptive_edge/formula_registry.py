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

# F-101..F-114 are the recovered strategy-specific contract slots. Their
# descriptions are governance metadata only; implementation status remains
# LOCKED until each canonical artifact has passed its promotion contract.
_FORMULA_METADATA: dict[str, tuple[str, str, str]] = {
    "F-101": ("Feature normalization", "normalized feature state", "f101_normalization"),
    "F-102": ("Probability / prediction state", "probability vector", "f102_prediction"),
    "F-103": ("Opportunity eligibility", "boolean / state", "f103_opportunity"),
    "F-104": ("Adaptive horizon distribution", "probability vector", "f104_horizon"),
    "F-105": ("Target/stop competition and conservative EV", "value / state", "f105_economics"),
    "F-106": ("Option candidate economic selection", "candidate / instrument", "f106_option_selection"),
    "F-107": ("Effective risk per unit", "INR / unit", "risk_sizing"),
    "F-108": ("Position sizing", "contracts", "risk_sizing"),
    "F-109": ("Option moneyness / listed-contract selection", "strike / leg", "option_ladder"),
    "F-110": ("Canonical order intent", "order intent", "execution_adapter"),
    "F-111": ("Canonical execution event", "execution event", "execution_adapter"),
    "F-112": ("Dynamic protection", "protection state", "protection"),
    "F-113": ("Lifecycle termination", "lifecycle state", "lifecycle_engine"),
    "F-114": ("Final portfolio interaction", "portfolio state", "management"),
}

for _id, (_name, _units, _owner) in _FORMULA_METADATA.items():
    FORMULAS[_id] = FormulaDefinition(_id, "1.0", _name, FormulaStatus.LOCKED, _units, _owner)


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
