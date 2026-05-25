"""Exit management for the daily SMA/EMA + RSI/ADX strategy.

Exit-priority ladder (per bar):

    1. ATR stop-loss  — intrabar (low ≤ stop for long, high ≥ stop for short)
    2. Signal exit    — on close, when RSI/ADX flips against the position
                        (long exits RSI < ADX, short exits RSI > ADX)

The signal flip is the strategy's primary exit; the ATR stop is a risk-defining
safety net that also anchors position sizing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.triple_st.config import TripleSTConfig
from app.engines.triple_st.engine import should_exit
from app.engines.triple_st.features import Features


@dataclass
class Position:
    direction: int                 # +1 long / -1 short
    entry: float
    entry_bar: int
    entry_ts: int
    size_units: float
    stop_loss: float
    r_distance: float
    risk_usd: float
    bars_held: int = 0
    closed: bool = False


@dataclass
class Fill:
    bar: int
    timestamp_ms: int
    price: float
    reason: str
    pnl_usd: float = 0.0


def _pnl(pos: Position, price: float, fee_pct: float) -> float:
    units = pos.size_units
    gross = pos.direction * (price - pos.entry) * units
    fees = (abs(pos.entry) + abs(price)) * units * (fee_pct / 100.0)
    return gross - fees


def step_position(
    pos: Position,
    feat: Features,
    i: int,
    cfg: TripleSTConfig,
    fee_pct: float = 0.05,
) -> Optional[Fill]:
    """Advance an open position by one bar; return a closing Fill or None."""
    if pos.closed:
        return None

    long = pos.direction == 1
    ts = int(feat.ts[i])
    h, l, c = float(feat.high[i]), float(feat.low[i]), float(feat.close[i])
    pos.bars_held = i - pos.entry_bar

    # ── 1. ATR stop-loss (intrabar) ──
    stop_hit = (l <= pos.stop_loss) if long else (h >= pos.stop_loss)
    if stop_hit:
        pos.closed = True
        return Fill(i, ts, round(pos.stop_loss, 4), "stop_loss", _pnl(pos, pos.stop_loss, fee_pct))

    # ── 2. Signal exit (on close) ──
    if should_exit(feat, i, pos.direction):
        pos.closed = True
        return Fill(i, ts, round(c, 4), "signal_exit", _pnl(pos, c, fee_pct))

    return None
