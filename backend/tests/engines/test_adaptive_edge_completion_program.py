"""Completion program: software-complete != production-authorized."""
from __future__ import annotations

from app.engines.adaptive_edge.completion import completion_program_status, software_complete
from app.engines.adaptive_edge.execution_gate import evaluate_execution_gate
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus


def test_software_slice_is_complete_and_production_stays_blocked():
    board = {item.name: item for item in completion_program_status(
        cache_bar_days=0, cache_bar_rows=0, cache_li_valid=0
    )}
    assert software_complete(tuple(board.values())) is True
    assert board["execution_path_composed"].complete is True
    assert board["full_strategy_replay"].complete is True
    assert board["pnl_reconciliation"].complete is True
    assert board["listed_instrument_fail_closed"].complete is True
    assert board["entry_conjunction_f110"].complete is True
    assert board["oos_claim_requires_a197"].complete is True
    assert board["production_gate_blocked"].complete is True
    assert board["formulas_locked"].complete is True
    assert board["a197_corpus"].complete is False
    assert board["f113_numeric_admission"].complete is False
    assert board["f114_portfolio_formula"].complete is False
    assert board["walk_forward_oos"].complete is False
    assert board["production_authorized"].complete is False
    assert evaluate_execution_gate().authorized is False
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED


def test_bars_only_cache_cannot_meet_a197():
    board = {item.name: item for item in completion_program_status(
        cache_bar_days=134, cache_bar_rows=50_244, cache_li_valid=3_374
    )}
    assert board["a197_corpus"].complete is False
    assert "li_bars<=3374" in board["a197_corpus"].detail
    assert software_complete(tuple(board.values())) is True
