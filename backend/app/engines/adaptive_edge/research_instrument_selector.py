"""Research-only instrument-selection adapter for F-109."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .f109_option_selection import F109Candidate, select_f109


@dataclass(frozen=True)
class SelectedInstrument:
    option_symbol: str
    option_type: str
    strike: float
    moneyness: str
    expected_net_ev: float


class ResearchInstrumentSelector:
    """Adapt F-109 selection into a canonical research instrument object."""

    def select(self, candidates: Iterable[F109Candidate]) -> SelectedInstrument | None:
        selected = select_f109(candidates)
        if selected is None or selected.expected_net_ev is None:
            return None
        return SelectedInstrument(
            option_symbol=selected.option_symbol,
            option_type=selected.option_type,
            strike=selected.strike,
            moneyness=selected.moneyness,
            expected_net_ev=selected.expected_net_ev,
        )
