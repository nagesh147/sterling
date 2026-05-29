"""DTE selection respecting the 2× hold-time rule:
   DTE ≥ 2 × expected_hold_days  AND  DTE ∈ [profile.dte_min, profile.dte_max].

When multiple chain-available expiries qualify, prefer the closest to
profile.dte_preferred — strategy authors set this knob deliberately to
match their typical hold (scalping ~1d, triple-ST ~14d, etc).

Returns the chosen DTE/expiry tuple + the list of contracts on that
expiry; caller (strike_picker) ranks within that subset.
"""
from __future__ import annotations

from typing import Optional

from app.engines.derivatives.schemas import StrategyDerivativesProfile
from app.schemas.market import OptionSummary


def _expected_hold_days(profile: StrategyDerivativesProfile, override_minutes: Optional[int]) -> float:
    minutes = override_minutes if override_minutes is not None else profile.expected_hold_minutes
    return max(0.0, minutes / (24 * 60))


def candidate_expiries(
    chain: list[OptionSummary],
    profile: StrategyDerivativesProfile,
    expected_hold_minutes: Optional[int] = None,
) -> dict[tuple[int, str], list[OptionSummary]]:
    """Group chain by (dte, expiry_date) keeping only expiries that pass
    the DTE rule. Result is sorted by closeness to profile.dte_preferred.
    """
    hold_days = _expected_hold_days(profile, expected_hold_minutes)
    min_dte_for_hold = int(2 * hold_days)
    effective_min = max(profile.dte_min, min_dte_for_hold)

    by_expiry: dict[tuple[int, str], list[OptionSummary]] = {}
    for o in chain:
        if o.dte < effective_min or o.dte > profile.dte_max:
            continue
        key = (int(o.dte), str(o.expiry_date))
        by_expiry.setdefault(key, []).append(o)

    # Sort keys by distance from preferred; tie-break: smaller DTE first
    # (less theta drag for swing options).
    if not by_expiry:
        return {}
    preferred = profile.dte_preferred
    sorted_keys = sorted(
        by_expiry.keys(),
        key=lambda k: (abs(k[0] - preferred), k[0]),
    )
    return {k: by_expiry[k] for k in sorted_keys}


def pick_expiry(
    chain: list[OptionSummary],
    profile: StrategyDerivativesProfile,
    expected_hold_minutes: Optional[int] = None,
) -> Optional[tuple[int, str, list[OptionSummary]]]:
    """Return (dte, expiry_date, contracts_at_that_expiry) for the
    preferred expiry, or None if the chain has no contracts meeting the
    profile + 2× hold rule."""
    grouped = candidate_expiries(chain, profile, expected_hold_minutes)
    if not grouped:
        return None
    (dte, expiry), contracts = next(iter(grouped.items()))
    return dte, expiry, contracts
