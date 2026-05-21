"""
Hybrid VCP-Momentum Scalper — Strategy V2
Microstructure proxies: CVD_proxy, OBI_proxy, flow_score, divergence.

These are OHLCV-only approximations. Real OBI (L2 orderbook) and CVD (tick
data) are used in live mode via live_filters.py and act as an additional
confirmation gate. Backtest results are conservative — real microstructure
adds alpha in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray


# ──────────────────────────────────────────────────────────────────────────────
# CVD Proxy
# ──────────────────────────────────────────────────────────────────────────────

def cvd_proxy(
    opens:  NDArray[np.float64],
    highs:  NDArray[np.float64],
    lows:   NDArray[np.float64],
    closes: NDArray[np.float64],
    volume: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    Cumulative Volume Delta proxy.

    delta_per_bar = volume × (close - open) / (high - low)
    Positive → buy pressure; Negative → sell pressure.

    Uses safe divisor to avoid div-by-zero.
    """
    tr = highs - lows
    safe_tr = np.where(tr > 0, tr, 1e-9)
    delta = volume * (closes - opens) / safe_tr
    return np.nancumsum(delta)


def cvd_proxy_bar(
    opens:  NDArray[np.float64],
    highs:  NDArray[np.float64],
    lows:   NDArray[np.float64],
    closes: NDArray[np.float64],
    volume: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Per-bar CVD proxy (not cumulative)."""
    tr = highs - lows
    safe_tr = np.where(tr > 0, tr, 1e-9)
    return volume * (closes - opens) / safe_tr


# ──────────────────────────────────────────────────────────────────────────────
# OBI Proxy
# ──────────────────────────────────────────────────────────────────────────────

def obi_proxy(
    highs:  NDArray[np.float64],
    lows:   NDArray[np.float64],
    closes: NDArray[np.float64],
    volume: NDArray[np.float64],
    vol_sma20: NDArray[np.float64],
) -> NDArray[np.float64]:
    """
    Order Flow Imbalance proxy derived from candle internals.

    close_location = (close - low) / (high - low)   → 0 = low, 1 = high
    (2 × close_location - 1)  → -1 to +1
    scaled by relative volume → volume / vol_sma_20

    Positive → buy-side pressure; Negative → sell-side pressure.
    """
    range_ = highs - lows
    safe_range = np.where(range_ > 0, range_, 1e-9)
    close_loc = (closes - lows) / safe_range
    imbalance = (2.0 * close_loc) - 1.0  # range [-1, +1]
    vol_ratio = np.where(vol_sma20 > 0, volume / vol_sma20, 0.0)
    return imbalance * vol_ratio


# ──────────────────────────────────────────────────────────────────────────────
# Flow Score
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FlowState:
    """Snapshot of microstructure state for a bar or window."""
    obi_proxy: float       # current OBI proxy value
    cvd_bar:    float       # current bar CVD proxy
    cvd_5_sum:  float       # sum of last 5 bars CVD proxy
    abs_cvd:    float       # |cvd_bar| for momentum
    flow_score: float       # combined [0, 1] score


def flow_score(
    obi_proxy: NDArray[np.float64],
    cvd_bar:   NDArray[np.float64],
    *,
    cvd_window:    int = 5,
    obi_weight:    float = 0.6,
    cvd_weight:    float = 0.4,
) -> NDArray[np.float64]:
    """
    Combined order-flow score per bar: [0, 1].

    flow_score = obi_proxy_normalised × obi_weight
               + |cvd_momentum| normalised × cvd_weight

    obi_proxy is already roughly [-1, +1]; normalise to [0, 1].
    cvd_momentum uses the 5-bar rolling sum direction magnitude.
    """
    n = len(obi_proxy)
    if n == 0:
        return np.zeros(0)

    # Normalise OBI proxy to [0, 1]
    obi_norm = np.clip((obi_proxy + 1.0) / 2.0, 0.0, 1.0)

    # CVD momentum: 5-bar rolling sum of sign-weighted bars
    cvd_5 = np.zeros(n)
    for i in range(cvd_window - 1, n):
        cvd_5[i] = float(np.sum(cvd_bar[i - cvd_window + 1:i + 1]))

    # Normalise CVD momentum to [0, 1]
    cvd_norm = np.clip(np.abs(cvd_5) / (np.abs(cvd_5).max() + 1e-9), 0.0, 1.0)

    return np.clip(obi_norm * obi_weight + cvd_norm * cvd_weight, 0.0, 1.0)


# ──────────────────────────────────────────────────────────────────────────────
# Divergence Detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_divergence(
    prices:    NDArray[np.float64],
    cvd_proxy: NDArray[np.float64],
    direction: int,
    window:     int = 5,
) -> NDArray[np.bool_]:
    """
    Detect price-CVD divergence.

    direction = +1 (long entry):
      Price breaks high BUT cvd_proxy is flat/negative → DIVERGENCE
    direction = -1 (short entry):
      Price breaks low BUT cvd_proxy is flat/positive → DIVERGENCE

    Returns boolean array per bar: True = divergence detected.
    """
    n = len(prices)
    divergence = np.zeros(n, dtype=np.bool_)

    if n <= window:
        return divergence

    for i in range(window, n):
        recent_prices = prices[i - window:i + 1]
        recent_cvd    = cvd_proxy[i - window:i + 1]

        price_broke_high = prices[i] >= float(np.max(recent_prices[:-1]))
        price_broke_low  = prices[i] <= float(np.min(recent_prices[:-1]))
        cvd_stalled = float(np.mean(recent_cvd)) <= 0.0

        if direction == 1 and price_broke_high and cvd_stalled:
            divergence[i] = True
        elif direction == -1 and price_broke_low and cvd_stalled:
            divergence[i] = True

    return divergence


@dataclass(frozen=True)
class MicroConfirmation:
    flow_score:    float   # [0, 1]
    has_divergence: bool
    obi_val:        float
    cvd_val:        float


def micro_confirmation_at(
    obi_proxy:    NDArray[np.float64],
    cvd_bar:      NDArray[np.float64],
    cvd_proxy:    NDArray[np.float64],
    closes:        NDArray[np.float64],
    direction:     int,
    idx:           int,
    flow_thresh:   float = 0.35,
    cvd_window:    int = 5,
) -> MicroConfirmation:
    """
    Per-bar microstructure confirmation check for live/backtest use.

    Args:
        idx: current bar index to evaluate (not last bar of array).
    Returns MicroConfirmation with flow_score and divergence flag.
    """
    n = len(closes)
    if idx < 0 or idx >= n:
        return MicroConfirmation(0.0, False, 0.0, 0.0)

    fs = flow_score(obi_proxy, cvd_bar, cvd_window=cvd_window)
    fscore = float(fs[idx]) if idx < len(fs) else 0.0

    obi_val = float(obi_proxy[idx]) if idx < len(obi_proxy) else 0.0
    cvd_val = float(cvd_bar[idx])   if idx < len(cvd_bar)     else 0.0

    div = detect_divergence(closes, cvd_proxy, direction, window=cvd_window)
    has_div = bool(div[idx]) if idx < len(div) else False

    return MicroConfirmation(
        flow_score=fscore,
        has_divergence=has_div,
        obi_val=obi_val,
        cvd_val=cvd_val,
    )