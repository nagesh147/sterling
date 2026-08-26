"""Research-only adapter between recovered strategy semantics and E2E boundaries.

This module deliberately does not replace ``e2e.run_e2e`` or the execution
 gate. It composes F-109/F-110/F-111 as a research decision surface so the
strategy contracts can be tested without granting production authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .f109_option_selection import F109Candidate, select_f109
from .f110_entry_gate import EntryDecision, F110Evidence, evaluate_entry
from .f111_exit_gate import ExitDecision, F111State, evaluate_exit


@dataclass(frozen=True)
class StrategyEntryResult:
    decision: EntryDecision
    selected_option_symbol: str | None
    expected_net_ev: float | None


@dataclass(frozen=True)
class StrategyExitResult:
    decision: ExitDecision


class ResearchStrategySemanticsAdapter:
    """Compose recovered strategy semantics without crossing execution gates."""

    def select_entry(
        self,
        candidates: Iterable[F109Candidate],
        evidence: F110Evidence,
    ) -> StrategyEntryResult:
        selected = select_f109(candidates)
        if selected is None:
            return StrategyEntryResult(EntryDecision.NO_TRADE, None, None)
        decision = evaluate_entry(selected.option_type, evidence)
        if decision is EntryDecision.NO_TRADE:
            return StrategyEntryResult(decision, None, None)
        return StrategyEntryResult(decision, selected.option_symbol, selected.expected_net_ev)

    def evaluate_exit(self, state: F111State) -> StrategyExitResult:
        return StrategyExitResult(evaluate_exit(state))
