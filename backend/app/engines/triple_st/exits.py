"""Exit management for the Triple SuperTrend strategy.

Implements the strict exit-priority ladder from the spec (§10) as a single
`step_position` call evaluated once per bar after entry:

    1. Gap protection            2. Volatility-spike emergency
    3. Early-warning reversal     4. Opposite signal
    5. 3-phase time stop          6. Breakeven shift
    7. Trailing stop (ST3, or ST1/ST2 + fail-counter for Momentum)
    8. Partial profits            9. Dynamic SL / TP

The function mutates the `Position` in place (trailing stop, breakeven, partial
bookkeeping) and returns the list of fills produced this bar. When the position
is fully closed it sets `pos.closed = True`.

Intrabar convention: emergencies and signal flips resolve at the bar close;
SL/TP/partials use the bar's high/low. We check the stop *before* favorable
fills in the same bar (conservative — never overstates a winning trade).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.engines.triple_st.config import ModeParams, AssetParams, TripleSTConfig
from app.engines.triple_st.engine import RegimeArrays, ConsensusArrays
from app.engines.triple_st.features import Features


_TRAIL_INDEX = {"ST1": 0, "ST2": 1, "ST3": 2}


@dataclass
class Position:
    direction: int                 # +1 long / -1 short
    entry: float
    entry_bar: int
    entry_ts: int
    size_units: float              # total base-asset units at entry
    initial_sl: float
    current_sl: float
    take_profit: float
    r_distance: float
    risk_usd: float
    partials: List[Tuple[float, float]]   # remaining (price, fraction-of-original)
    mode_name: str
    remaining_frac: float = 1.0
    be_moved: bool = False
    partial1_done: bool = False
    bars_held: int = 0
    extreme: float = 0.0           # best price seen (high for long / low for short)
    trail_fail: int = 0
    closed: bool = False

    def __post_init__(self):
        self.extreme = self.entry


@dataclass
class Fill:
    bar: int
    timestamp_ms: int
    price: float
    frac: float                    # fraction of ORIGINAL size closed
    reason: str
    pnl_usd: float = 0.0


def _pnl(pos: Position, price: float, frac: float, fee_pct: float) -> float:
    units = pos.size_units * frac
    gross = pos.direction * (price - pos.entry) * units
    fees = (abs(pos.entry) + abs(price)) * units * (fee_pct / 100.0)
    return gross - fees


def step_position(
    pos: Position,
    feat: Features,
    regime: RegimeArrays,
    cons: ConsensusArrays,
    i: int,
    mode: ModeParams,
    asset: AssetParams,
    cfg: TripleSTConfig,
    fee_pct: float = 0.05,
) -> List[Fill]:
    """Advance an open position by one bar, returning any fills."""
    fills: List[Fill] = []
    if pos.closed:
        return fills

    long = pos.direction == 1
    ts = int(feat.ts[i])
    o, h, l, c = float(feat.open[i]), float(feat.high[i]), float(feat.low[i]), float(feat.close[i])
    pos.bars_held = i - pos.entry_bar
    pos.extreme = max(pos.extreme, h) if long else min(pos.extreme, l)

    def close_all(price: float, reason: str):
        frac = pos.remaining_frac
        f = Fill(i, ts, round(price, 4), frac, reason, _pnl(pos, price, frac, fee_pct))
        pos.remaining_frac = 0.0
        pos.closed = True
        fills.append(f)

    # ── 1. Gap protection ───────────────────────────────────────────────
    if cfg.use_gap_protection and i > 0 and feat.close[i - 1] > 0:
        gap_pct = (o - feat.close[i - 1]) / feat.close[i - 1] * 100.0
        adverse = gap_pct <= -asset.gap_threshold_pct if long else gap_pct >= asset.gap_threshold_pct
        if adverse:
            close_all(o, "gap_protection")
            return fills

    # ── 2. Volatility-spike emergency ───────────────────────────────────
    if cfg.use_spike_guard and feat.atr50[i] > 0 and feat.atr14[i] > 3.0 * feat.atr50[i]:
        close_all(c, "vol_spike")
        return fills

    # ── 3. Early-warning reversal candle ────────────────────────────────
    body = abs(c - o)
    against = (c < o) if long else (c > o)
    if (against and body > 1.6 * feat.atr14[i]
            and feat.vol_ma[i] > 0 and feat.volume[i] > 2.0 * feat.vol_ma[i]):
        close_all(c, "reversal_candle")
        return fills

    # ── 4. Opposite signal ──────────────────────────────────────────────
    # Symmetric with entry: require the active mode's confirmation count in the
    # opposite direction (consensus arrays are built at the loosest 2/3, so a
    # bare 2/3 flip must NOT eject a position armed on 3/3 — that asymmetry
    # churns tiny losses in chop).
    if int(cons.direction[i]) == -pos.direction and int(cons.agree_count[i]) >= mode.min_confirm:
        close_all(c, "opposite_signal")
        return fills

    # ── 5. 3-phase time stop ────────────────────────────────────────────
    if not pos.be_moved:
        budget = mode.time_stop_pre_be                       # strict
    elif not pos.partial1_done:
        budget = int(mode.time_stop_pre_be * mode.time_stop_post_be)  # lenient
    else:
        budget = 0                                           # disabled after partial 1
    if budget and pos.bars_held >= budget:
        close_all(c, "time_stop")
        return fills

    # ── 6. Breakeven shift — lock a small profit (not raw entry) ─────────
    # Moving to *exact* entry at 0.5R scratched a huge share of trades flat
    # (counted as ~0/loss). Locking +0.15R once the trade is in profit turns
    # those scratches into small wins and lifts the realised win rate.
    BE_LOCK_R = 0.15
    if not pos.be_moved:
        favor = (pos.extreme - pos.entry) if long else (pos.entry - pos.extreme)
        if favor >= mode.be_trigger_r * pos.r_distance:
            pos.be_moved = True
            lock = BE_LOCK_R * pos.r_distance
            pos.current_sl = pos.entry + lock if long else pos.entry - lock

    # ── 7. Trailing stop ────────────────────────────────────────────────
    trail_idx = _TRAIL_INDEX.get(mode.trail_source, 2)
    trail_line = float(feat.st_lines[trail_idx][i])
    trail_trend = int(feat.st_trends[trail_idx][i])
    if mode.momentum_trail:
        # Momentum: trail tight on ST1/ST2 but tolerate up to 2 adverse flips.
        if trail_trend == -pos.direction:
            pos.trail_fail += 1
            if pos.trail_fail >= 2:
                close_all(c, "momentum_trail")
                return fills
        else:
            pos.trail_fail = 0
    if trail_line > 0:
        if long and trail_line < c:
            pos.current_sl = max(pos.current_sl, trail_line)
        elif not long and trail_line > c:
            pos.current_sl = min(pos.current_sl, trail_line)

    # ── 9a. Dynamic stop-loss (checked before favorable fills) ───────────
    sl_hit = (l <= pos.current_sl) if long else (h >= pos.current_sl)
    if sl_hit:
        reason = "breakeven_stop" if pos.be_moved else "stop_loss"
        close_all(pos.current_sl, reason)
        return fills

    # ── 8. Partial profits ──────────────────────────────────────────────
    remaining: List[Tuple[float, float]] = []
    for price, frac in pos.partials:
        touched = (h >= price) if long else (l <= price)
        if touched and pos.remaining_frac > 0:
            take = min(frac, pos.remaining_frac)
            f = Fill(i, ts, round(price, 4), take, "partial", _pnl(pos, price, take, fee_pct))
            pos.remaining_frac -= take
            fills.append(f)
            if not pos.partial1_done:
                pos.partial1_done = True
                # Lock in: ratchet stop to a small locked profit after scale-out.
                pos.be_moved = True
                lock = 0.15 * pos.r_distance
                pos.current_sl = pos.entry + lock if long else pos.entry - lock
        else:
            remaining.append((price, frac))
    pos.partials = remaining

    # ── 9b. Take-profit on the remainder ────────────────────────────────
    if pos.remaining_frac > 0:
        tp_hit = (h >= pos.take_profit) if long else (l <= pos.take_profit)
        if tp_hit:
            close_all(pos.take_profit, "take_profit")
            return fills

    if pos.remaining_frac <= 1e-9:
        pos.closed = True

    return fills


def cooldown_bars(exit_reason: str, asset: AssetParams) -> int:
    """Context-aware cooldown after an exit (bars), scaled by asset class.

    Adverse exits (stops, reversals, spikes) cool down longer than profit
    exits, so the system doesn't immediately re-enter a hostile tape.
    """
    base = {
        "stop_loss": 4, "breakeven_stop": 2, "reversal_candle": 5,
        "vol_spike": 6, "gap_protection": 6, "momentum_trail": 2,
        "opposite_signal": 3, "time_stop": 3, "take_profit": 1,
    }.get(exit_reason, 3)
    return max(1, round(base * asset.cooldown_mult))
