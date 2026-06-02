"""Reconstruct genuine historical IV surfaces from the forward IV recorder.

Validation method 2 (real-only/forward) does NOT calibrate to a single live
snapshot — it replays the option surfaces the `delta_iv_recorder` persisted to
`option_iv_ticks` over time. Each recorder flush (every ~60s) becomes one real
`SurfaceSnapshot`; the options simulator then prices trades through the surface
that was actually live at the time.

Until the recorder has accrued history this returns few/no surfaces, which is
the honest "futures only" result for method 2.
"""
from __future__ import annotations

import logging
import time as _time
from collections import defaultdict
from typing import Optional

import pandas as pd

from study.surface_snapshot import SurfaceSnapshot

log = logging.getLogger(__name__)


def _dte(expiry, capture_ts: float) -> Optional[int]:
    """Days-to-expiry of `expiry` (any parseable form) as of `capture_ts`
    (epoch seconds). Returns None when unparseable or already expired."""
    try:
        exp = pd.to_datetime(expiry)
        cap = pd.to_datetime(capture_ts, unit="s")
    except Exception:
        return None
    days = (exp - cap).days
    return int(days) if days >= 0 else None


def reconstruct_surfaces(
    ticks: list[dict],
    underlying: str,
    *,
    bucket_seconds: int = 120,
) -> list[SurfaceSnapshot]:
    """Group recorded `option_iv_ticks` into per-capture real SurfaceSnapshots.

    Ticks within `bucket_seconds` of each other are treated as one capture.
    Each surface carries the measured ATM-IV curve (DTE → IV, from near-ATM
    contracts) and 25Δ skew. Captures with no usable ATM IV are dropped.
    Returned oldest-first.
    """
    if not ticks:
        return []

    buckets: dict[int, list[dict]] = defaultdict(list)
    for t in ticks:
        ts = t.get("ts")
        if ts is None:
            continue
        buckets[int(ts // bucket_seconds) * bucket_seconds].append(t)

    surfaces: list[SurfaceSnapshot] = []
    for cap_ts in sorted(buckets):
        rows = buckets[cap_ts]
        per_dte: dict[int, list[float]] = defaultdict(list)
        put_25: list[float] = []
        call_25: list[float] = []
        for t in rows:
            iv = t.get("mark_iv")
            delta = t.get("delta")
            if not iv or iv <= 0 or delta is None:
                continue
            ad = abs(delta)
            d = _dte(t.get("expiry"), cap_ts)
            if d is not None and 0.35 <= ad <= 0.65:
                per_dte[d].append(iv)
            if 0.20 <= ad <= 0.30:
                if t.get("opt_type") == "put":
                    put_25.append(iv)
                elif t.get("opt_type") == "call":
                    call_25.append(iv)

        atm_iv = {d: sum(ivs) / len(ivs) for d, ivs in per_dte.items()}
        if not atm_iv:
            continue
        skew = None
        if put_25 and call_25:
            skew = round(sum(put_25) / len(put_25) - sum(call_25) / len(call_25), 4)

        surfaces.append(SurfaceSnapshot(
            underlying=underlying,
            spot=0.0,                      # sim uses the per-bar spot from OHLCV
            timestamp_ms=int(cap_ts * 1000),
            snapshot_date=_time.strftime("%Y-%m-%d", _time.gmtime(cap_ts)),
            atm_iv=atm_iv,
            skew_25d=skew,
            vrp=None,
            realized_vol_30d=None,
            spread_median_pct=0.0,
            regime_label="real",
            regime_provisional=False,
            chain_json="[]",
        ))

    return surfaces


def earliest_capture_ts(surfaces: list[SurfaceSnapshot]) -> Optional[float]:
    """Epoch-seconds timestamp of the first recorded surface (the start of the
    forward window), or None if there are no surfaces."""
    if not surfaces:
        return None
    return min(s.timestamp_ms for s in surfaces) / 1000.0
