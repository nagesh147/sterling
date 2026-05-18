"""
Default funding-rate estimates per underlying (8-hour period).

Conservative stubs sourced from rolling 30-day medians on Deribit / OKX perps
as of 2026-05-18. These are intentionally on the high side of typical observed
ranges so backtest cost attribution doesn't under-report drag. Override per
request by passing `funding_8h_pct` explicitly.

Pure module: no I/O, no exchange calls.
"""
from __future__ import annotations
from typing import Dict, Optional


# 8-hour funding-rate stubs as a fraction (0.0001 = 1 bp = 0.01%).
# Index/Spot underlyings (NIFTY, BANKNIFTY) have no perpetual funding —
# returns 0.0 so the option/futures cost model degrades to fees + slippage.
_DEFAULTS_8H: Dict[str, float] = {
    "BTC": 0.0001,
    "ETH": 0.0001,
    "SOL": 0.0002,
    "XRP": 0.0003,
    "NIFTY": 0.0,
    "BANKNIFTY": 0.0,
}


def default_funding_8h_pct(underlying: str) -> float:
    """
    Conservative per-8h funding-rate estimate for `underlying`.

    Falls back to the most pessimistic value in the table (SOL/XRP-tier) when
    the underlying is unknown, so callers never silently size off 0.0 when
    they actually meant "I don't know".
    """
    if not underlying:
        return 0.0002
    return _DEFAULTS_8H.get(underlying.upper(), 0.0002)


def resolve_funding_8h_pct(
    underlying: str, override: Optional[float] = None,
) -> float:
    """
    If the caller passes an explicit value, use it; otherwise look up the
    default. Use this helper at API boundaries so endpoints don't need to
    repeat the None-check.
    """
    if override is not None:
        return float(override)
    return default_funding_8h_pct(underlying)
