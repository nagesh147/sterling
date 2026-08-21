"""Expiry and strike selection.

Both selectors take the *listed* contracts as input and never synthesise a
contract from string formatting. The observed bot resolved real instrument keys
(``BSE_FO|1141595``) out of a loaded instrument master, and a fabricated key is
an order that either rejects or -- worse -- hits a contract nobody chose.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Sequence

from .models import InstrumentRef, OptionPairRef


def select_expiry(
    listed: Sequence[str],
    *,
    policy: str,
    today: date,
    explicit: str = "",
) -> str:
    """Pick one expiry from the listed set (ISO ``YYYY-MM-DD`` strings).

    ``SAME_DAY`` is strict: if today is not a listed expiry it raises rather than
    sliding to the next one. Silently trading a different expiry than configured
    changes the strategy's risk profile completely -- a same-day ATM straddle and
    a next-week ATM straddle are not the same instrument.
    """
    values = sorted({str(e).strip() for e in listed if str(e).strip()})
    if not values:
        raise ValueError("no listed expiries available")

    iso_today = today.isoformat()

    if policy == "EXPLICIT":
        if not explicit:
            raise ValueError("EXPLICIT expiry policy requires an explicit expiry")
        if explicit not in values:
            raise ValueError(f"explicit expiry {explicit} is not listed")
        return explicit

    if policy == "SAME_DAY":
        if iso_today not in values:
            raise ValueError(f"no contract expires today ({iso_today}); listed: {values[:4]}")
        return iso_today

    future = [v for v in values if v >= iso_today]
    if not future:
        raise ValueError("all listed expiries are in the past")

    if policy == "NEAREST":
        return future[0]
    if policy == "NEXT":
        later = [v for v in future if v > iso_today]
        if not later:
            raise ValueError("no expiry after today is listed")
        return later[0]

    raise ValueError(f"unknown expiry policy: {policy}")


def select_atm_strike(underlying_ltp: float, available_strikes: Iterable[float]) -> float:
    """Nearest listed strike to the underlying, tie-broken to the lower strike.

    Uses the actual listed strikes rather than assuming a step size, because
    strike spacing is not constant across an index option chain. The tie-break is
    fixed and documented so replay is deterministic: at an exact midpoint the
    lower strike always wins.
    """
    if underlying_ltp is None or underlying_ltp <= 0:
        raise ValueError("underlying_ltp must be positive")
    strikes = sorted({float(s) for s in available_strikes if float(s) > 0})
    if not strikes:
        raise ValueError("no available strikes")
    return min(strikes, key=lambda k: (abs(k - float(underlying_ltp)), k))


def resolve_pair(
    *,
    underlying: str,
    underlying_ltp: float,
    contracts: Sequence[InstrumentRef],
    expiry: str,
    underlying_instrument_id: str = "",
) -> OptionPairRef:
    """Resolve the ATM CE/PE pair for one expiry from listed contracts.

    Requires *both* legs at the chosen strike. A strike with only one listed leg
    is not tradable by this strategy -- the signal is a comparison.
    """
    same_expiry = [c for c in contracts if c.expiry == expiry]
    if not same_expiry:
        raise ValueError(f"no contracts listed for expiry {expiry}")

    ce_by_strike = {c.strike: c for c in same_expiry if c.option_type == "CE"}
    pe_by_strike = {c.strike: c for c in same_expiry if c.option_type == "PE"}
    both = sorted(set(ce_by_strike) & set(pe_by_strike))
    if not both:
        raise ValueError(f"no strike has both a CE and a PE for expiry {expiry}")

    strike = select_atm_strike(underlying_ltp, both)
    return OptionPairRef(
        underlying=underlying,
        expiry=expiry,
        strike=strike,
        ce=ce_by_strike[strike],
        pe=pe_by_strike[strike],
        underlying_instrument_id=underlying_instrument_id,
    )
