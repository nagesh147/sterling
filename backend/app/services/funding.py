"""
Funding-rate resolution.

Funding is a PERPETUAL-SWAP mechanism: longs and shorts pay each other to keep
the perp pinned to the index. NSE has no perpetuals. Its futures carry cost of
carry in the basis, which the price already reflects, and its options carry it
in the premium — neither is a periodic funding payment, and charging one on top
double-counts.

This module used to hold 8-hour funding stubs taken from Deribit/OKX perps
(BTC 1bp, ETH 1bp, SOL 2bp, XRP 3bp). The crypto product surface is gone, and
those entries went with it. What made it a live bug rather than dead data was
the fallback: an UNKNOWN underlying returned 0.0002 — the most pessimistic
crypto tier — and only NIFTY and BANKNIFTY were listed as 0.0. So every NSE
single-stock underlying (RELIANCE, SBIN, TCS, LT, ...) was charged 2bp of
invented funding drag every 8 hours by the backtest cost model, making Indian
results look worse than they were.

The resolution helpers are kept, and still honour an explicit override, so a
caller that genuinely has a funding number (a future non-NSE venue, or a
research scenario) can still pass one.

Pure module: no I/O, no exchange calls.
"""
from __future__ import annotations
from typing import Optional


def default_funding_8h_pct(underlying: str) -> float:
    """Per-8h funding for `underlying`. Always 0.0 — see the module docstring.

    Deliberately not raising: this sits inside cost models that must keep
    producing a number, and 0.0 is the correct one for every instrument this
    build trades.
    """
    return 0.0


def resolve_funding_8h_pct(
    underlying: str, override: Optional[float] = None,
) -> float:
    """
    If the caller passes an explicit value, use it; otherwise the default.
    Use this helper at API boundaries so endpoints don't repeat the None-check.
    """
    if override is not None:
        return float(override)
    return default_funding_8h_pct(underlying)
