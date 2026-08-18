"""Research implementation of the V1.0 entry-decision gate.

The source permits BUY_CE/BUY_PE only when data, directional edge, positive
EV, positive conservative EV, liquidity, slippage, and risk gates all pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntryDecision(str, Enum):
    NO_TRADE = "NO_TRADE"
    BUY_CE = "BUY_CE"
    BUY_PE = "BUY_PE"


@dataclass(frozen=True)
class F110Evidence:
    data_ok: bool
    directional_edge_ok: bool
    expected_ev: float | None
    conservative_ev: float | None
    liquidity_ok: bool
    slippage_ok: bool
    risk_ok: bool


def evaluate_entry(option_type: str, evidence: F110Evidence) -> EntryDecision:
    option = option_type.upper()
    if option not in {"CE", "PE"}:
        return EntryDecision.NO_TRADE
    if not evidence.data_ok or not evidence.directional_edge_ok:
        return EntryDecision.NO_TRADE
    if evidence.expected_ev is None or evidence.conservative_ev is None:
        return EntryDecision.NO_TRADE
    if evidence.expected_ev <= 0 or evidence.conservative_ev <= 0:
        return EntryDecision.NO_TRADE
    if not evidence.liquidity_ok or not evidence.slippage_ok or not evidence.risk_ok:
        return EntryDecision.NO_TRADE
    return EntryDecision.BUY_CE if option == "CE" else EntryDecision.BUY_PE
