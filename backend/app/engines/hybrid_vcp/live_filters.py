"""
Hybrid VCP-Momentum Scalper — Strategy V2
Live-mode microstructure filters: real OBI from L2 orderbook, real CVD from
recent_trade WebSocket channel. Not used in backtest.

These run as a FINAL confirmation gate before order placement in live mode.
If real data is unavailable or a gap is detected, fall back to the proxy version
from microstructure.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class RealOBI:
    """Real OBI from l2_orderbook WebSocket channel."""
    bid_qty:    float
    ask_qty:    float
    imbalance: float   # (bid - ask) / (bid + ask), positive = buy pressure
    ref_spread: float  # rolling 1h average spread for blow-out detection


@dataclass(frozen=True)
class RealCVD:
    """Real CVD from recent_trade WebSocket channel."""
    cvd:        float   # cumulative delta (buy vol - sell vol)
    cvd_rate:   float  # delta per unit time (for acceleration)


@dataclass(frozen=True)
class LiveMicroState:
    """Combined live microstructure snapshot."""
    obi:        Optional[RealOBI]
    cvd:        Optional[RealCVD]
    timestamp_ms: int
    seq_no:     int     # WebSocket sequence number for gap detection


@dataclass(frozen=True)
class LiveFilterConfig:
    obi_threshold:     float = 0.27   # |imbalance| must exceed this
    cvd_threshold:   float = 0.0    # CVD must be aligned with direction
    spread_blow_out_x: float = 1.5   # veto if current spread > 1.5× 1h mean
    seq_gap_tolerance: int   = 5     # veto if seq_no gap > this


@dataclass(frozen=True)
class LiveFilterDecision:
    passed:    bool
    code:      str
    reason:    str
    obi_val:   float
    cvd_val:   float


def evaluate_live_filters(
    state:   LiveMicroState,
    direction: int,          # +1 long, -1 short
    config:  Optional[LiveFilterConfig] = None,
) -> LiveFilterDecision:
    """
    Evaluate real OBI + CVD as final entry confirmation gate.

    Returns (passed, code, reason) — veto if any check fails.
    Falls back to proxy if state.obi or state.cvd is None.
    """
    cfg = config or LiveFilterConfig()

    if state.obi is None or state.cvd is None:
        return LiveFilterDecision(True, "proxy_fallback", "real_data_unavailable", 0.0, 0.0)

    obi_val = float(state.obi.imbalance)
    cvd_val = float(state.cvd.cvd)

    # Hostile check: for long entry, want positive imbalance
    # For short entry, want negative imbalance
    hostile = -obi_val if direction == 1 else obi_val
    if hostile > cfg.obi_threshold:
        return LiveFilterDecision(
            False, "live_obi_hostile",
            f"obi {obi_val:+.3f} hostile to {'long' if direction==1 else 'short'}",
            obi_val, cvd_val,
        )

    # CVD alignment: for long want positive CVD, for short want negative
    cvd_hostile = -cvd_val if direction == 1 else cvd_val
    if cvd_hostile > abs(cfg.cvd_threshold):
        return LiveFilterDecision(
            False, "live_cvd_opposing",
            f"cvd {cvd_val:.2f} opposes {'long' if direction==1 else 'short'}",
            obi_val, cvd_val,
        )

    # Spread blow-out check
    if state.obi.ref_spread > 0 and state.obi.imbalance != 0:
        spread_ratio = abs(state.obi.imbalance / state.obi.ref_spread) \
                       if state.obi.ref_spread != 0 else 0.0
        if spread_ratio > cfg.spread_blow_out_x:
            return LiveFilterDecision(
                False, "live_spread_blowout",
                f"spread ratio {spread_ratio:.1f}× exceeds {cfg.spread_blow_out_x}×",
                obi_val, cvd_val,
            )

    return LiveFilterDecision(
        True, "live_passed",
        f"obi={obi_val:+.3f} cvd={cvd_val:.2f}",
        obi_val, cvd_val,
    )


def obi_from_orderbook(
    bids: List[tuple[float, float]],   # [(price, qty), ...]
    asks: List[tuple[float, float]],   # [(price, qty), ...]
    levels: int = 10,
) -> float:
    """
    Compute weighted OBI from top-N levels of orderbook.

    bid_qty = Σ qty_i / (1 + i*0.2)  — nearer levels weighted more
    ask_qty = Σ qty_i / (1 + i*0.2)
    imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)
    """
    bid_vol = sum(q * (1.0 / (1 + i * 0.2)) for i, (_, q) in enumerate(bids[:levels]))
    ask_vol = sum(q * (1.0 / (1 + i * 0.2)) for i, (_, q) in enumerate(asks[:levels]))
    total = bid_vol + ask_vol
    return (bid_vol - ask_vol) / total if total > 0 else 0.0


def cvd_from_trades(
    trades: List[tuple[float, str]],   # [(size, "buy"|"sell"), ...]
) -> float:
    """Compute cumulative CVD from trade list."""
    cvd = 0.0
    for size, side in trades:
        if side == "buy":
            cvd += float(size)
        elif side == "sell":
            cvd -= float(size)
    return cvd