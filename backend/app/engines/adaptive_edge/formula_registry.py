"""Formula registry for Adaptive Edge.

F-101..F-114 are implemented by the explicitly versioned Adaptive Edge V2.1
new-definition proposal. Their implementation status is distinct from
production promotion status; promotion.py remains the authoritative execution
approval boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FormulaStatus(str, Enum):
    ANCHORED = "anchored"
    IMPLEMENTED = "implemented"
    LOCKED = "locked"
    DEPRECATED = "deprecated"


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
    "F-101": FormulaDefinition("F-101", "2.1.0", "Weighted normalized composite feature score", FormulaStatus.IMPLEMENTED, "[-1,1]", "strategy_v21"),
    "F-102": FormulaDefinition("F-102", "2.1.0", "Three-state directional edge", FormulaStatus.IMPLEMENTED, "[-1,1]", "strategy_v21"),
    "F-103": FormulaDefinition("F-103", "2.1.0", "Causal opportunity eligibility", FormulaStatus.IMPLEMENTED, "boolean", "strategy_v21"),
    "F-104": FormulaDefinition("F-104", "2.1.0", "Volatility/drawdown operating mode", FormulaStatus.IMPLEMENTED, "enum", "strategy_v21"),
    "F-105": FormulaDefinition("F-105", "2.1.0", "Monotonic profit protection", FormulaStatus.IMPLEMENTED, "price", "strategy_v21"),
    "F-106": FormulaDefinition("F-106", "2.1.0", "Dynamic risk schedule", FormulaStatus.IMPLEMENTED, "accounting currency", "strategy_v21"),
    "F-107": FormulaDefinition("F-107", "2.1.0", "Protection-and-cost risk per unit", FormulaStatus.IMPLEMENTED, "accounting currency/unit", "strategy_v21"),
    "F-108": FormulaDefinition("F-108", "2.1.0", "Increment-aligned position sizing", FormulaStatus.IMPLEMENTED, "quantity units", "strategy_v21"),
    "F-109": FormulaDefinition("F-109", "2.1.0", "Directional option selection", FormulaStatus.IMPLEMENTED, "candidate score", "strategy_v21"),
    "F-110": FormulaDefinition("F-110", "2.1.0", "Directional entry trigger", FormulaStatus.IMPLEMENTED, "boolean", "strategy_v21"),
    "F-111": FormulaDefinition("F-111", "2.1.0", "Protection/target/horizon exit", FormulaStatus.IMPLEMENTED, "boolean", "strategy_v21"),
    "F-112": FormulaDefinition("F-112", "2.1.0", "Protection parameterization", FormulaStatus.IMPLEMENTED, "price", "strategy_v21"),
    "F-113": FormulaDefinition("F-113", "2.1.0", "Cooldown/new-opportunity re-entry", FormulaStatus.IMPLEMENTED, "boolean", "strategy_v21"),
    "F-114": FormulaDefinition("F-114", "2.1.0", "Shared-risk multi-position constraint", FormulaStatus.IMPLEMENTED, "risk capacity", "strategy_v21"),
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
