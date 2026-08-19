"""F-109 research selection over a listed universe only.

A34: do not invent ATM/ITM strikes or future-listed contracts.
O* = argmax expected_net_value among listed, eligible contracts.
Deterministic tie-break: instrument_id. Registry stays LOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


class InstrumentSelectionError(ValueError):
    """Raised when no listed contract can be selected fail-closed."""


@dataclass(frozen=True)
class ListedOptionCandidate:
    instrument_id: str
    option_type: str
    strike: float
    expiry: str
    expected_net_value: float
    available_at: str
    listed: bool = True
    liquidity_ok: bool = True
    spread_ok: bool = True
    data_ok: bool = True


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise InstrumentSelectionError("candidate available_at must include timezone")
    return parsed


def select_listed_instrument(
    candidates: Sequence[ListedOptionCandidate],
    *,
    decision_time: str,
    option_type: str,
) -> ListedOptionCandidate:
    if option_type not in {"CE", "PE"}:
        raise InstrumentSelectionError("option_type must be CE or PE")
    if not candidates:
        raise InstrumentSelectionError("empty_listed_universe")
    decision_dt = _parse(decision_time)
    eligible: list[ListedOptionCandidate] = []
    for candidate in candidates:
        available = _parse(candidate.available_at)
        if available > decision_dt:
            raise InstrumentSelectionError("lookahead_listed_quote")
        if not candidate.listed:
            continue
        if candidate.option_type != option_type:
            continue
        if not (candidate.liquidity_ok and candidate.spread_ok and candidate.data_ok):
            continue
        if candidate.expected_net_value <= 0:
            continue
        if not candidate.instrument_id or candidate.strike <= 0 or not candidate.expiry:
            raise InstrumentSelectionError("incomplete_listed_identity")
        eligible.append(candidate)
    if not eligible:
        raise InstrumentSelectionError("no_eligible_listed_contract")
    return max(eligible, key=lambda item: (item.expected_net_value, item.instrument_id))
