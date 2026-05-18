"""
Issue 13 — Triple-barrier labelling (López de Prado, Advances in Financial ML, §3).

Pure module — no model training, no sklearn dependency. Generates per-event
labels {-1, 0, +1}:

  +1  → upper barrier (profit-take) hit first
  -1  → lower barrier (stop-loss) hit first
   0  → vertical barrier (max_hold_bars) hit first

This is the surface a future ML layer will consume. We intentionally do NOT
add xgboost / sklearn here — that would commit us to a model before we've
validated the labels are predictive.

Reads from the event ledger format produced by
`app.engines.backtest.event_ledger.EventLedger`. Each labelling input is a
"candidate" event carrying at least `bar_idx`, `direction`, and `payload`
with feature snapshots.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.schemas.market import Candle


@dataclass(frozen=True)
class BarrierParams:
    pt_mult: float = 2.0           # profit-take = pt_mult × volatility (ATR-like)
    sl_mult: float = 1.0           # stop-loss   = sl_mult × volatility
    max_hold_bars: int = 24        # vertical barrier
    vol_lookback: int = 14         # bars used for the volatility estimate


@dataclass
class LabelledEvent:
    bar_idx: int
    label: int                     # +1 / -1 / 0
    horizon_bars: int              # how many bars until a barrier was hit
    barrier_hit: str               # "pt" / "sl" / "vert"
    entry_price: float
    realized_return: float         # signed return at the barrier
    features: Dict[str, Any] = field(default_factory=dict)


def _atr_like_vol(candles: Sequence[Candle], lookback: int) -> np.ndarray:
    """
    Rolling Garman-style volatility estimate per bar. Returns 0 where the
    window has insufficient bars so callers can fall back to a constant.
    """
    if not candles:
        return np.array([], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows  = np.array([c.low  for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)
    n = len(closes)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - lookback + 1)
        if i - lo + 1 < 2:
            continue
        tr_arr = np.maximum.reduce([
            highs[lo:i + 1] - lows[lo:i + 1],
            np.abs(highs[lo:i + 1] - np.roll(closes[lo:i + 1], 1)),
            np.abs(lows[lo:i + 1]  - np.roll(closes[lo:i + 1], 1)),
        ])
        out[i] = float(np.mean(tr_arr[1:]))  # skip first roll artifact
    return out


def triple_barrier_labels(
    candidates: Sequence[Dict[str, Any]],
    candles: Sequence[Candle],
    *,
    params: Optional[BarrierParams] = None,
) -> List[LabelledEvent]:
    """
    Compute triple-barrier labels for each candidate event.

    `candidates` is a list of dicts produced by EventLedger (use
    `events_as_dicts()` and filter on `kind == "candidate"` or `"entry_fill"`).
    Each must carry `bar_idx` (int) and at minimum a `payload.direction`
    ("long" or "short").

    Returns one LabelledEvent per input. Events whose horizon would exceed the
    available data (i.e. the vertical barrier extends past the candle stream)
    are still returned with `label=0, barrier_hit="vert", horizon_bars=<actual>`.
    """
    p = params or BarrierParams()
    vol = _atr_like_vol(list(candles), p.vol_lookback)
    n = len(candles)
    out: List[LabelledEvent] = []
    for ev in candidates:
        bar_idx = int(ev.get("bar_idx", -1))
        if bar_idx < 0 or bar_idx >= n:
            continue
        direction_raw = (
            (ev.get("payload") or {}).get("direction")
            or ev.get("direction")
            or "long"
        )
        direction = 1 if str(direction_raw).lower() == "long" else -1
        entry_price = float(candles[bar_idx].close)
        v = float(vol[bar_idx]) if bar_idx < len(vol) and vol[bar_idx] > 0 else entry_price * 0.01
        pt_dist = p.pt_mult * v
        sl_dist = p.sl_mult * v

        label = 0
        hit = "vert"
        horizon = p.max_hold_bars
        realized = 0.0
        last_bar = min(n - 1, bar_idx + p.max_hold_bars)
        for k in range(bar_idx + 1, last_bar + 1):
            c = candles[k]
            move_up = (c.high - entry_price) * direction      # signed up-move for direction
            move_dn = (entry_price - c.low) * direction       # signed down-move for direction
            if direction == 1:
                hit_pt = c.high >= entry_price + pt_dist
                hit_sl = c.low  <= entry_price - sl_dist
            else:
                hit_pt = c.low  <= entry_price - pt_dist
                hit_sl = c.high >= entry_price + sl_dist
            if hit_pt and hit_sl:
                # Both touched in the same bar → assume stop fires first (conservative)
                label = -1
                hit = "sl"
                horizon = k - bar_idx
                realized = -sl_dist / entry_price * direction
                break
            if hit_pt:
                label = 1
                hit = "pt"
                horizon = k - bar_idx
                realized = pt_dist / entry_price * direction
                break
            if hit_sl:
                label = -1
                hit = "sl"
                horizon = k - bar_idx
                realized = -sl_dist / entry_price * direction
                break
        else:
            # Vertical barrier
            end_price = float(candles[last_bar].close)
            realized = (end_price - entry_price) / entry_price * direction
            horizon = last_bar - bar_idx
            label = 0

        out.append(LabelledEvent(
            bar_idx=bar_idx,
            label=label,
            horizon_bars=horizon,
            barrier_hit=hit,
            entry_price=entry_price,
            realized_return=float(realized),
            features=dict((ev.get("payload") or {}).get("features") or {}),
        ))
    return out


def label_distribution(events: Sequence[LabelledEvent]) -> Dict[str, int]:
    """Helper for tests: count {-1, 0, +1} occurrences."""
    out = {"pt": 0, "sl": 0, "vert": 0, "n": len(events)}
    for e in events:
        if e.label == 1:
            out["pt"] += 1
        elif e.label == -1:
            out["sl"] += 1
        else:
            out["vert"] += 1
    return out
