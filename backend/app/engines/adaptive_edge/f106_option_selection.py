"""Research-only F-106 option candidate selector."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class OptionCandidate:
    instrument: str
    side: str
    expected_gross_ev: float
    execution_cost: float
    expected_net_ev: float
    risk: float
    liquidity: float
    expected_slippage: float
    confidence: float
    data_quality: float


@dataclass(frozen=True)
class OptionSelectionPolicy:
    min_liquidity: float
    max_slippage: float
    max_risk: float
    min_data_quality: float


@dataclass(frozen=True)
class OptionSelection:
    instrument: str | None
    reason: str


def select_option(
    candidates: tuple[OptionCandidate, ...],
    *,
    direction: str,
    policy: OptionSelectionPolicy,
) -> OptionSelection:
    """Select the highest validated net-EV option for an existing direction."""
    if direction not in {"BUY_CE", "BUY_PE"}:
        return OptionSelection(None, "no_directional_entry")
    if any(not isfinite(value) for candidate in candidates for value in _values(candidate)):
        raise ValueError("F-106 candidate contains non-finite values")

    eligible = []
    for candidate in candidates:
        if candidate.side != direction:
            continue
        if candidate.liquidity < policy.min_liquidity:
            continue
        if candidate.expected_slippage > policy.max_slippage:
            continue
        if candidate.risk < 0 or candidate.risk > policy.max_risk:
            continue
        if candidate.data_quality < policy.min_data_quality:
            continue
        if candidate.execution_cost < 0:
            continue
        if abs(candidate.expected_net_ev - (candidate.expected_gross_ev - candidate.execution_cost)) > 1e-9:
            raise ValueError("expected_net_ev must equal gross EV minus execution cost")
        eligible.append(candidate)

    if not eligible:
        return OptionSelection(None, "no_eligible_instrument")

    # Stable deterministic tie-break: net EV, confidence, instrument name.
    selected = max(eligible, key=lambda c: (c.expected_net_ev, c.confidence, c.instrument))
    return OptionSelection(selected.instrument, "selected_max_net_ev")


def _values(candidate: OptionCandidate) -> tuple[float, ...]:
    return (
        candidate.expected_gross_ev,
        candidate.execution_cost,
        candidate.expected_net_ev,
        candidate.risk,
        candidate.liquidity,
        candidate.expected_slippage,
        candidate.confidence,
        candidate.data_quality,
    )
