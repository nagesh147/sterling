from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class ListedOption:
    strike: float
    option_type: str
    expiry: str
    available_at: str
    symbol: str
    lot_size: int


def classify_moneyness(spot: float, strike: float, option_type: str) -> str:
    if option_type == "CE":
        return "ATM" if strike == spot else ("ITM" if strike < spot else "OTM")
    if option_type == "PE":
        return "ATM" if strike == spot else ("ITM" if strike > spot else "OTM")
    raise ValueError("option_type must be CE or PE")


def require_listed_contract(
    candidates: list[ListedOption],
    *,
    option_type: str,
    expiry: str,
    decision_time: str,
) -> list[ListedOption]:
    selected = [
        option for option in candidates
        if option.option_type == option_type
        and option.expiry == expiry
        and option.available_at <= decision_time
        and option.lot_size > 0
        and option.symbol
    ]
    return sorted(selected, key=lambda option: (option.strike, option.symbol))


def test_f109_uses_listed_contracts_not_synthetic_strikes() -> None:
    candidates = [
        ListedOption(24500, "CE", "2026-08-27", "2026-08-17T09:15:00+05:30", "NIFTY26AUG24500CE", 65),
        ListedOption(24550, "CE", "2026-08-27", "2026-08-17T09:15:00+05:30", "NIFTY26AUG24550CE", 65),
    ]
    result = require_listed_contract(
        candidates,
        option_type="CE",
        expiry="2026-08-27",
        decision_time="2026-08-17T09:20:00+05:30",
    )
    assert [item.symbol for item in result] == ["NIFTY26AUG24500CE", "NIFTY26AUG24550CE"]


def test_f109_direction_determines_option_type() -> None:
    assert classify_moneyness(24520, 24500, "CE") == "ITM"
    assert classify_moneyness(24520, 24500, "PE") == "OTM"


def test_f109_rejects_unknown_option_type() -> None:
    with pytest.raises(ValueError):
        classify_moneyness(24520, 24500, "XX")


def test_f109_excludes_future_chain_data() -> None:
    candidates = [
        ListedOption(24500, "CE", "2026-08-27", "2026-08-17T09:30:00+05:30", "NIFTY26AUG24500CE", 65),
    ]
    result = require_listed_contract(
        candidates,
        option_type="CE",
        expiry="2026-08-27",
        decision_time="2026-08-17T09:20:00+05:30",
    )
    assert result == []


def test_f109_rejects_invalid_lot() -> None:
    candidates = [
        ListedOption(24500, "CE", "2026-08-27", "2026-08-17T09:15:00+05:30", "NIFTY26AUG24500CE", 0),
    ]
    result = require_listed_contract(
        candidates,
        option_type="CE",
        expiry="2026-08-27",
        decision_time="2026-08-17T09:20:00+05:30",
    )
    assert result == []
