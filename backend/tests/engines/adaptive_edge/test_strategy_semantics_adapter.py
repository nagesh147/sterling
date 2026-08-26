from __future__ import annotations

from app.engines.adaptive_edge.f109_option_selection import F109Candidate
from app.engines.adaptive_edge.f110_entry_gate import EntryDecision, F110Evidence
from app.engines.adaptive_edge.f111_exit_gate import ExitDecision, F111State
from app.engines.adaptive_edge.strategy_semantics_adapter import ResearchStrategySemanticsAdapter


def candidate(symbol: str, net: float, option_type: str = "CE") -> F109Candidate:
    return F109Candidate(symbol, option_type, 24500, "ATM", net + 2, 2, 100, 1000, 1, 1, 500, 2, 200, 0.9)


def evidence() -> F110Evidence:
    return F110Evidence(True, True, 10, 5, True, True, True)


def test_adapter_composes_f109_and_f110_without_execution_authorization() -> None:
    result = ResearchStrategySemanticsAdapter().select_entry(
        [candidate("NIFTY26AUG24500CE", 8), candidate("NIFTY26AUG24400CE", 12)], evidence()
    )
    assert result.decision is EntryDecision.BUY_CE
    assert result.selected_option_symbol == "NIFTY26AUG24400CE"
    assert result.expected_net_ev == 12


def test_adapter_fails_closed_when_entry_evidence_fails() -> None:
    result = ResearchStrategySemanticsAdapter().select_entry(
        [candidate("X", 8)], F110Evidence(True, True, 10, 0, True, True, True)
    )
    assert result.decision is EntryDecision.NO_TRADE
    assert result.selected_option_symbol is None


def test_adapter_composes_f111_exit_without_submitting_an_order() -> None:
    result = ResearchStrategySemanticsAdapter().evaluate_exit(
        F111State(False, 0, False, False, False)
    )
    assert result.decision is ExitDecision.EXIT
