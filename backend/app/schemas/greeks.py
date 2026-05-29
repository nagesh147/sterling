"""Greeks schemas — Pydantic models for serialising option Greeks across
the API and into persistent storage.

Lives in a dedicated schema module (rather than under engines/risk/) so it
can be imported by `PaperPosition` and the API layer without dragging in
scipy/numpy via the math-bearing greeks_budget module.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GreeksSnapshot(BaseModel):
    """A point-in-time snapshot of an option's Greeks.

    Persisted on PaperPosition for entry-time Greeks (so we can compare to
    current Greeks at any later point — drift, theta burn, etc.) and
    returned from the portfolio Greeks aggregator for live read-outs.

    Fields default to 0 so a partially-populated snapshot (e.g. an
    adapter that only supplied delta+vega+theta) is still valid; missing
    fields are filled by `enrich_with_greeks()` from BSM. `spot` and `iv`
    record the market state at the time of the snapshot so callers can
    re-derive Greeks if needed.
    """
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0       # per day
    rho: float = 0.0
    # Market state at snapshot time (for back-derivation / drift analysis)
    spot: Optional[float] = None
    iv: Optional[float] = None       # decimal, e.g. 0.65 for 65% IV
    dte: Optional[int] = None
    timestamp_ms: int = 0
