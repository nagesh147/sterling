"""Exact §35 entry-gate predicates.

The gate only combines already-validated upstream inputs. It does not invent
thresholds, probabilities, liquidity limits, slippage limits, or risk limits.
"""
from __future__ import annotations


def buy_ce_gate(
    *,
    data_ok: bool,
    directional_edge_ok: bool,
    ev_ce: float,
    conservative_ev_ce: float,
    liquidity_ok: bool,
    slippage_ok: bool,
    risk_ok: bool,
) -> bool:
    """§35 BUY_CE gate: every stated condition must hold."""
    return (
        data_ok
        and directional_edge_ok
        and ev_ce > 0
        and conservative_ev_ce > 0
        and liquidity_ok
        and slippage_ok
        and risk_ok
    )


def buy_pe_gate(
    *,
    data_ok: bool,
    directional_edge_ok: bool,
    ev_pe: float,
    conservative_ev_pe: float,
    liquidity_ok: bool,
    slippage_ok: bool,
    risk_ok: bool,
) -> bool:
    """§35 BUY_PE gate: analogous PE conditions."""
    return (
        data_ok
        and directional_edge_ok
        and ev_pe > 0
        and conservative_ev_pe > 0
        and liquidity_ok
        and slippage_ok
        and risk_ok
    )
