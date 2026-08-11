"""Formula registry for Adaptive Edge.

F-101..F-114 were provisional identifiers introduced after the original
strategy discussion and are NOT part of the Master Mathematical Specification.
They are retained only as deprecated compatibility metadata.

The source-derived registry lives in ``spec_registry.py`` and anchors
implementation concepts to the Master Mathematical Specification v1.0.
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
    "F-101": FormulaDefinition("F-101", "0.1.0", "Provisional composite feature score", FormulaStatus.DEPRECATED, "[-1,1]", "legacy_model"),
    "F-102": FormulaDefinition("F-102", "0.1.0", "Provisional edge score", FormulaStatus.DEPRECATED, "[-1,1]", "legacy_model"),
    "F-103": FormulaDefinition("F-103", "0.1.0", "Provisional opportunity eligibility", FormulaStatus.DEPRECATED, "boolean", "legacy_model"),
    "F-104": FormulaDefinition("F-104", "0.1.0", "Provisional dynamic operating mode", FormulaStatus.DEPRECATED, "enum", "legacy_model"),
    "F-105": FormulaDefinition("F-105", "0.1.0", "Provisional profit protection", FormulaStatus.DEPRECATED, "accounting currency", "legacy_model"),
    "F-106": FormulaDefinition("F-106", "0.1.0", "Provisional dynamic risk", FormulaStatus.DEPRECATED, "accounting currency", "legacy_model"),
    "F-107": FormulaDefinition("F-107", "0.1.0", "Provisional risk per unit", FormulaStatus.DEPRECATED, "accounting currency/unit", "legacy_model"),
    "F-108": FormulaDefinition("F-108", "0.1.0", "Provisional position sizing", FormulaStatus.DEPRECATED, "lots", "legacy_model"),
    "F-109": FormulaDefinition("F-109", "0.1.0", "Provisional instrument selection", FormulaStatus.DEPRECATED, "score", "legacy_model"),
    "F-110": FormulaDefinition("F-110", "0.1.0", "Provisional entry trigger", FormulaStatus.DEPRECATED, "boolean", "legacy_model"),
    "F-111": FormulaDefinition("F-111", "0.1.0", "Provisional exit trigger", FormulaStatus.DEPRECATED, "boolean", "legacy_model"),
    "F-112": FormulaDefinition("F-112", "0.1.0", "Provisional protection parameters", FormulaStatus.DEPRECATED, "price/value", "legacy_model"),
    "F-113": FormulaDefinition("F-113", "0.1.0", "Provisional re-entry", FormulaStatus.DEPRECATED, "boolean", "legacy_model"),
    "F-114": FormulaDefinition("F-114", "0.1.0", "Provisional multi-position interaction", FormulaStatus.DEPRECATED, "risk fraction", "legacy_model"),
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
