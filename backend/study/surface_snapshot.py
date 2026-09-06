"""The options-surface slice the study simulators price through.

This module used to also CAPTURE the surface: it pulled the full Delta India
option chain, wrote it out as a JSON fixture and read a regime label off
`app.engines.derivatives_native`. All of that went with the crypto surface, and
so did this file — which broke `import study` outright, and with it every
retained Kite study script, because `study/__init__.py` still re-exported the
capture function.

What the retained modules actually need is the container, not the capture:
`forward_surface` builds these out of recorded `option_iv_ticks`, and
`options_sim` and `gate_audit` read fields off one. So the dataclass stays and
the Delta-specific capture does not come back.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SurfaceSnapshot:
    """One calibratable surface slice, at one moment.

    `spot` is 0.0 for a surface rebuilt from recorded ticks — the simulator uses
    the per-bar spot from OHLCV rather than the one stamped here — and
    `regime_label` is "real" for those, to separate a replayed surface from a
    modelled one.
    """
    underlying: str
    spot: float
    timestamp_ms: int
    snapshot_date: str            # YYYY-MM-DD (for labelling)
    atm_iv: dict[int, float]      # DTE → ATM IV
    skew_25d: float | None        # put IV − call IV at |delta| ≈ 0.25
    vrp: float | None             # ATM_IV(30d) / realized_vol_30d
    realized_vol_30d: float | None
    spread_median_pct: float
    regime_label: str             # "cheap" | "fair" | "rich" | "real" | "unknown"
    regime_provisional: bool
    chain_json: str               # serialized full chain (list[dict])
