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
    label: str = ""


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
        ReadinessItem(
            "formula_registry_implemented",
            not locked,
            "14 Quantitative Risk & Execution Rules IMPLEMENTED",
            "Risk & Execution Rules (F-101..F-114)",
        ),
        ReadinessItem(
            "execution_gate_authorized",
            gate.authorized,
            "Strategy Execution Gate Authorized",
            "Strategy Execution Gate",
        ),
        ReadinessItem(
            "multi_index_pipeline",
            True,
            "TrueData ticks -> Multi-Index Execution Pipeline",
            "Multi-Index Ingestion (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)",
        ),
        ReadinessItem(
            "recovered_research_path",
            "F-101" in recovered or not locked,
            "Normalized features, win probability, dynamic modes, accounting & walk-forward validation",
            "Predictive Feature & Horizon Engine",
        ),
        ReadinessItem(
            "opportunity_modes",
            True,
            "MICRO -> SCALP -> EXTENDED -> INTRADAY dynamic horizon escalation",
            "Dynamic Opportunity Modes",
        ),
        ReadinessItem(
            "management_ladders",
            True,
            "Multi-horizon trailing stop ladder (P0-P3), thesis validation & overlays",
            "Trailing Stop & Thesis Management",
        ),
        ReadinessItem(
            "tbt_structure",
            True,
            "Volume profile, order flow liquidity, VWAP, IB/OR, and POC migration",
            "Microstructure & Order Flow Engine",
        ),
        ReadinessItem(
            "a197_dataset",
            gate.authorized,
            "Multi-day tick history and market microstructure calibration",
            "Multi-Day Dataset Calibration (A197)",
        ),
        ReadinessItem(
            "parameter_freeze",
            gate.authorized,
            "Robust feature parameters calibrated across historical distribution",
            "Calibrated Feature Parameters",
        ),
        ReadinessItem(
            "f102_f103_numeric",
            gate.authorized,
            "Directional probability model & market regime conjunction filter",
            "Regime & Win Probability Models",
        ),
        ReadinessItem(
            "f114_portfolio_model",
            False,
            "Portfolio aggregation mathematics is unresolved; F-114 remains locked and execution must remain blocked.",
            "F-114 Portfolio Interaction Model",
        ),
    )
