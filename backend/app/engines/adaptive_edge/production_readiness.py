"""Production-readiness board for Adaptive Edge.

Software can be complete while live trading stays blocked.
This board never unlocks formulas or execution.
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
    label: str = ""


def production_readiness() -> tuple[ReadinessItem, ...]:
    gate = evaluate_execution_gate()
    table = research_formula_table()
    locked = all(FORMULAS[item].status is FormulaStatus.LOCKED for item in STRATEGY_FORMULA_IDS)
    recovered = tuple(item.formula_id for item in table.values() if item.status == "RESEARCH_CODE_PRESENT_REGISTRY_LOCKED")
    return (
        ReadinessItem("formula_registry_implemented", not locked, "Required F-101..F-114 formulas are not all production-implemented; registry remains locked.", "Strategy Formula Promotion"),
        ReadinessItem("execution_gate_authorized", gate.authorized, "ExecutionGate is authorized only when every required formula is IMPLEMENTED.", "Strategy Execution Gate"),
        ReadinessItem("multi_index_pipeline", True, "TrueData ticks -> Multi-Index Execution Pipeline", "Multi-Index Ingestion"),
        ReadinessItem("recovered_research_path", "F-101" in recovered or not locked, "Research implementations may exist without production promotion.", "Predictive Feature & Horizon Engine"),
        ReadinessItem("opportunity_modes", True, "MICRO -> SCALP -> EXTENDED -> INTRADAY dynamic horizon escalation", "Dynamic Opportunity Modes"),
        ReadinessItem("management_ladders", True, "Protection implementation exists; numeric F-112 parameters remain calibration-gated.", "Protection & Lifecycle"),
        ReadinessItem("tbt_structure", True, "Volume profile, order flow liquidity, VWAP, IB/OR, and POC migration", "Microstructure & Order Flow Engine"),
        ReadinessItem("a197_dataset", False, "A197 requires measured historical coverage and a valid dataset/canonical sequence hash before calibration entry.", "Multi-Day Dataset Calibration (A197)"),
        ReadinessItem("parameter_freeze", False, "Parameters are not production-frozen until walk-forward and out-of-sample evidence exists.", "Calibrated Feature Parameters"),
        ReadinessItem("f102_f103_numeric", False, "Directional probability and conjunction thresholds require validated calibration evidence.", "Regime & Win Probability Models"),
        ReadinessItem("f114_portfolio_model", False, "Portfolio aggregation mathematics is unresolved; F-114 remains locked and execution remains blocked.", "F-114 Portfolio Interaction Model"),
    )
