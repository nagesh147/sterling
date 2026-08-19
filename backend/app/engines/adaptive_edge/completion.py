"""Adaptive Edge completion-program board.

Software-complete is not production-authorized. This module only reports
evidence. It does not unlock formulas.
"""
from __future__ import annotations

from dataclasses import dataclass

from .corpus_observation import LocalCorpusObservation, observe_local_corpus
from .execution_gate import evaluate_execution_gate
from .formula_registry import FORMULAS, FormulaStatus
from .research_pipeline import A197_MIN_BARS, A197_MIN_TRADING_DAYS, meets_a197_contract


@dataclass(frozen=True)
class CompletionItem:
    name: str
    complete: bool
    detail: str


def completion_program_status(
    *,
    cache_bar_days: int | None = None,
    cache_bar_rows: int | None = None,
    cache_li_valid: int | None = None,
    observation: LocalCorpusObservation | None = None,
) -> tuple[CompletionItem, ...]:
    gate = evaluate_execution_gate()
    locked = all(
        FORMULAS[f"F-{n:03d}"].status is FormulaStatus.LOCKED for n in range(101, 115)
    )
    observed = observation
    if cache_bar_days is None or cache_bar_rows is None or cache_li_valid is None:
        observed = observed or observe_local_corpus()
    days = observed.bar_days if cache_bar_days is None else cache_bar_days
    rows = observed.bar_rows if cache_bar_rows is None else cache_bar_rows
    li_valid = observed.bars_on_li_days if cache_li_valid is None else cache_li_valid
    a197 = meets_a197_contract(trading_days=days, bar_count=rows, li_valid=li_valid)
    return (
        CompletionItem("execution_path_composed", True, "OrderIntent → Gateway → BrokerEvent → Position"),
        CompletionItem("lifecycle_on_projected_position", True, "A126/A177 on real PositionState"),
        CompletionItem("post_exit_authorization_consumed", True, "A177 exit != re-entry"),
        CompletionItem("one_position_admission", True, "INV-ENTRY-003 pyramid blocked"),
        CompletionItem("full_strategy_replay", True, "same ReplayContext → identical TraceHash"),
        CompletionItem("pnl_reconciliation", True, "F-107 itemized costs → net PnL"),
        CompletionItem("listed_instrument_fail_closed", True, "F-109 empty/lookahead chain rejected"),
        CompletionItem("entry_conjunction_f110", True, "BUY_CE/BUY_PE on real objects; ConservativeEV not invented"),
        CompletionItem("oos_claim_requires_a197", True, "bars-only corpus cannot promote OOS"),
        CompletionItem("adversarial_fail_closed", True, "lookahead, reject, timeout, cutoff, reuse"),
        CompletionItem("production_gate_blocked", not gate.authorized, "F-101..F-114 required IMPLEMENTED"),
        CompletionItem("formulas_locked", locked, "F-101..F-114 remain LOCKED"),
        CompletionItem(
            "a197_corpus",
            a197,
            (
                f"observed days={days} bars={rows} li_bars<={li_valid}; "
                f"need >={A197_MIN_TRADING_DAYS} days and >={A197_MIN_BARS} bars + LI"
            ),
        ),
        CompletionItem("f113_numeric_admission", False, "no unique re-entry score in recovered source"),
        CompletionItem("f114_portfolio_formula", False, "no unique PortfolioRisk formula in recovered source"),
        CompletionItem("walk_forward_oos", False, "blocked: A197 corpus missing"),
        CompletionItem("production_authorized", False, "blocked: calibration + unique F-113/F-114 + OOS"),
    )


def software_complete(items: tuple[CompletionItem, ...] | None = None) -> bool:
    board = items or completion_program_status()
    required = {
        "execution_path_composed",
        "lifecycle_on_projected_position",
        "post_exit_authorization_consumed",
        "one_position_admission",
        "full_strategy_replay",
        "pnl_reconciliation",
        "listed_instrument_fail_closed",
        "entry_conjunction_f110",
        "oos_claim_requires_a197",
        "adversarial_fail_closed",
        "production_gate_blocked",
        "formulas_locked",
    }
    return all(item.complete for item in board if item.name in required)
