"""Machine-readable registry for the reconstructed Adaptive Edge model.

No historical F-101..F-114 equations were retrievable from the available
conversation context. These formulas are therefore an explicit strategy
revision, versioned separately and requiring backtest validation before live
execution authorization.
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
    "F-101": FormulaDefinition("F-101", "0.1.0", "Composite feature score", FormulaStatus.IMPLEMENTED, "[-1,1]", "model"),
    "F-102": FormulaDefinition("F-102", "0.1.0", "Edge / prediction score", FormulaStatus.IMPLEMENTED, "[-1,1]", "model"),
    "F-103": FormulaDefinition("F-103", "0.1.0", "Opportunity eligibility", FormulaStatus.IMPLEMENTED, "boolean", "model"),
    "F-104": FormulaDefinition("F-104", "0.1.0", "Dynamic operating mode", FormulaStatus.IMPLEMENTED, "enum", "mode"),
    "F-105": FormulaDefinition("F-105", "0.1.0", "Predictive-profit protection floor", FormulaStatus.IMPLEMENTED, "accounting currency", "protection"),
    "F-106": FormulaDefinition("F-106", "0.1.0", "Dynamic risk schedule", FormulaStatus.IMPLEMENTED, "accounting currency", "risk"),
    "F-107": FormulaDefinition("F-107", "0.1.0", "Risk per unit", FormulaStatus.IMPLEMENTED, "accounting currency/unit", "sizing"),
    "F-108": FormulaDefinition("F-108", "0.1.0", "Position sizing", FormulaStatus.IMPLEMENTED, "lots", "sizing"),
    "F-109": FormulaDefinition("F-109", "0.1.0", "Instrument selection score", FormulaStatus.IMPLEMENTED, "[0,1]", "instrument"),
    "F-110": FormulaDefinition("F-110", "0.1.0", "Entry trigger", FormulaStatus.IMPLEMENTED, "boolean", "entry"),
    "F-111": FormulaDefinition("F-111", "0.1.0", "Exit trigger", FormulaStatus.IMPLEMENTED, "boolean", "exit"),
    "F-112": FormulaDefinition("F-112", "0.1.0", "Trailing/protection parameterization", FormulaStatus.IMPLEMENTED, "price/value", "protection"),
    "F-113": FormulaDefinition("F-113", "0.1.0", "Re-entry rule", FormulaStatus.IMPLEMENTED, "boolean", "entry"),
    "F-114": FormulaDefinition("F-114", "0.1.0", "Multi-position interaction", FormulaStatus.IMPLEMENTED, "risk fraction", "portfolio"),
}


def get_formula(formula_id: str) -> FormulaDefinition:
    try:
        return FORMULAS[formula_id]
    except KeyError as exc:
        raise KeyError(f"unknown Adaptive Edge formula ID: {formula_id}") from exc


def require_implemented(formula_id: str) -> FormulaDefinition:
    definition = get_formula(formula_id)
    if definition.status is not FormulaStatus.IMPLEMENTED:
        raise RuntimeError(f"Adaptive Edge formula {formula_id} is not executable: {definition.status.value}")
    return definition
