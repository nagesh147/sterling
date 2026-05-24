"""STRATEGY STUB — options structure policy removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. `apply_policy` returns a
neutral policy with no allowed structures so the app keeps running empty.

Implement the new policy logic here.
"""
from __future__ import annotations

from typing import Optional

from app.schemas.directional import Direction, PolicyResult, IVRBand


def apply_policy(
    direction: Direction,
    instrument,
    ivr: Optional[float],
) -> PolicyResult:
    """Neutral policy: nothing allowed (no strategy loaded)."""
    return PolicyResult(
        allowed_structures=[],
        ivr=ivr,
        ivr_band=IVRBand.NORMAL,
        preferred_dte_min=0,
        preferred_dte_max=0,
        naked_allowed=False,
        debit_preferred=False,
        avoid_long_premium=False,
    )
