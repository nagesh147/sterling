"""Production-readiness board for Adaptive Edge.

Software can be complete while live trading stays blocked.
This does not unlock F-101 or ExecutionGate.
"""
from __future__ import annotations

from dataclasses import dataclass

from .execution_gate import evaluate_execution_gate
from .formula_registry import FORMULAS, FormulaStatus
from .research_formulas import STRATEGY_FORMULA_IDS, research_formula_table


@dataclass(frozen=True)
class ReadinessItem:
    name: str
    ready: bool
    detail: str


def production_readiness() -> tuple[ReadinessItem, ...]:
    gate = evaluate_execution_gate()
    table = research_formula_table()
    locked = all(FORMULAS[item].status is FormulaStatus.LOCKED for item in STRATEGY_FORMULA_IDS)
    recovered = tuple(
        item.formula_id
        for item in table.values()
        if item.status == "RESEARCH_CODE_PRESENT_REGISTRY_LOCKED"
    )
    return (
        ReadinessItem("formula_registry_locked", locked, "F-101..F-114 stay LOCKED"),
        ReadinessItem("execution_gate_blocked", not gate.authorized, gate.reason or "blocked"),
        ReadinessItem("kite_disconnected", True, "Adaptive Edge does not submit to Kite"),
        ReadinessItem(
            "recovered_research_path",
            "F-101" in recovered,
            "features, score, gates, sim fill, A126, modes, A177 policy, accounting, WF",
        ),
        ReadinessItem(
            "opportunity_modes",
            True,
            "MICRO/SCALP/EXTENDED_SCALP/INTRADAY machinery; F-104 still LOCKED",
        ),
        ReadinessItem(
            "management_ladders",
            True,
            "thesis, P0-P3, overlays, H4, operating posture; F-105/F-106 still LOCKED",
        ),
        ReadinessItem(
            "tbt_structure",
            True,
            "profile, TBT flow, VWAP, IB/OR, HVN/LVN, POC migration; not canonical DeltaVelocity",
        ),
        ReadinessItem(
            "a197_dataset",
            False,
            "needs TrueData premium tick history before 2026-08-06",
        ),
        ReadinessItem(
            "parameter_freeze",
            False,
            "f101_parameters_v1.json is not written from the trial path",
        ),
        ReadinessItem(
            "f102_f103_numeric",
            False,
            "no recovered closed-form; gates stay SPEC_GAP unless supplied",
        ),
    )
