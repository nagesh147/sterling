"""Honest options backtest for the Kite Triple-SuperTrend engine (workstream H).

Three data modes, all replaying the SAME signal logic the live engine uses
(Triple-SuperTrend full-alignment entries, trail-target exit):

  * ``synthetic`` — run the ST on the underlying's real multi-year candles. Each
    bar the option premium is priced with Black-Scholes (underlying + a fixed IV
    assumption + theta decay toward expiry). Full history, but the premium is
    MODELED — surfaced as an explicit caveat. This is the only mode that can test
    the strategy over real market history (expired strikes' premium is unfetchable).

  * ``real`` — run the ST directly on an actual fetched option-premium candle
    series (what live "derivatives" mode does). True prices, but limited to a
    currently-listed contract → short lookback, small-sample.

  * ``both`` — run synthetic over history AND real on the live contract, and report
    how far the BS model drifts from the real premium (calibration overlay).

Costs are modeled with a real Indian F&O-options charge schedule (STT on sell
premium, brokerage, exchange txn, GST, SEBI, stamp) so net results are honest.

Pure-ish: the engine functions take candle arrays and return result dicts. The
service layer fetches candles and calls in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.services.kite_engine.greeks import bs_price


# ── Indian options cost model ────────────────────────────────────────────────
@dataclass
class OptionCosts:
    """Per-leg charge schedule for NSE/BSE F&O *options*, as fractions of premium
    turnover unless noted. Defaults track the common 2026 retail schedule; the UI
    can override. STT applies to the SELL side only (on premium)."""
    brokerage_per_order: float = 20.0      # ₹ flat per order (typical discount broker)
    stt_sell_pct: float = 0.000625         # 0.0625% of sell premium turnover
    exchange_txn_pct: float = 0.00035      # ~0.035% of premium turnover (NSE options)
    gst_pct: float = 0.18                  # on (brokerage + exchange txn)
    sebi_pct: float = 0.000001             # ₹10 per crore
    stamp_pct: float = 0.00003             # 0.003% on buy side
    slippage_pct: float = 0.01             # 1% of premium per side (wide OTM spreads)

    def round_trip(self, entry_premium: float, exit_premium: float, qty: int) -> float:
        """Total charges (₹) for a buy-then-sell of ``qty`` units."""
        buy_turnover = entry_premium * qty
        sell_turnover = exit_premium * qty
        brokerage = self.brokerage_per_order * 2
        stt = sell_turnover * self.stt_sell_pct
        exch = (buy_turnover + sell_turnover) * self.exchange_txn_pct
        gst = (brokerage + exch) * self.gst_pct
        sebi = (buy_turnover + sell_turnover) * self.sebi_pct
        stamp = buy_turnover * self.stamp_pct
        slip = (buy_turnover + sell_turnover) * self.slippage_pct
        return brokerage + stt + exch + gst + sebi + stamp + slip


@dataclass
class BacktestTrade:
    entry_ms: int
    exit_ms: int
    direction: str          # long-call / long-put
    entry_premium: float
    exit_premium: float
    qty: int
    gross_pnl: float
    costs: float
    net_pnl: float
    bars_held: int
    exit_reason: str


@dataclass
class BacktestStats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    gross_pnl: float = 0.0
    total_costs: float = 0.0
    net_pnl: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    return_pct: float = 0.0
    final_capital: float = 0.0


@dataclass
class BacktestRun:
    mode: str
    caveat: str
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    stats: BacktestStats = field(default_factory=BacktestStats)


def _stats_from_trades(trades: List[BacktestTrade], starting_capital: float) -> tuple:
    """Compute summary stats + equity curve from a trade list."""
    stats = BacktestStats(final_capital=starting_capital)
    equity = [starting_capital]
    if not trades:
        return stats, equity

    cap = starting_capital
    peak = starting_capital
    max_dd = 0.0
    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [t.net_pnl for t in trades if t.net_pnl <= 0]
    rets = []
    for t in trades:
        prev = cap
        cap += t.net_pnl
        equity.append(cap)
        rets.append((cap - prev) / prev if prev > 0 else 0.0)
        peak = max(peak, cap)
        if peak > 0:
            max_dd = max(max_dd, (peak - cap) / peak)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    stats.trades = len(trades)
    stats.wins = len(wins)
    stats.losses = len(losses)
    stats.win_rate = len(wins) / len(trades) if trades else 0.0
    stats.gross_pnl = round(sum(t.gross_pnl for t in trades), 2)
    stats.total_costs = round(sum(t.costs for t in trades), 2)
    stats.net_pnl = round(sum(t.net_pnl for t in trades), 2)
    stats.profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else 0.0)
    stats.expectancy = round(stats.net_pnl / len(trades), 2)
    stats.avg_win = round(np.mean(wins), 2) if wins else 0.0
    stats.avg_loss = round(np.mean(losses), 2) if losses else 0.0
    stats.max_drawdown = round(max_dd * 100, 2)
    if len(rets) > 1 and np.std(rets) > 0:
        stats.sharpe = round(float(np.mean(rets) / np.std(rets) * np.sqrt(252)), 3)
    stats.final_capital = round(cap, 2)
    stats.return_pct = round((cap - starting_capital) / starting_capital * 100, 2)
    return stats, [round(e, 2) for e in equity]


def replay_premium_series(
    *,
    timestamps_ms: List[int],
    premium_open: List[float],
    premium_high: List[float],
    premium_low: List[float],
    premium_close: List[float],
    cfg: TripleSupertrendConfig,
    trail_target: str,
    qty: int,
    costs: OptionCosts,
    starting_capital: float,
    direction_label: str = "long",
) -> BacktestRun:
    """Replay the ST on a PREMIUM series (the 'real' mode, and the inner loop the
    'synthetic' mode reuses on its modeled premium series). BUY on a fresh up-
    transition of the premium's own SuperTrend; exit when the trail flips down.
    """
    o = np.asarray(premium_open, float)
    h = np.asarray(premium_high, float)
    l = np.asarray(premium_low, float)
    c = np.asarray(premium_close, float)
    n = len(c)
    trades: List[BacktestTrade] = []
    if n <= cfg.warmup + 2:
        run = BacktestRun(mode="", caveat="")
        run.stats, run.equity_curve = _stats_from_trades(trades, starting_capital)
        return run

    r = compute_regime(o, h, l, c, cfg)
    longs, _ = entry_transitions(r)          # premium up-transition = BUY
    trend = r.trend(trail_target)            # exit when this flips against us

    i = 0
    while i < n:
        if not longs[i]:
            i += 1
            continue
        # enter at this bar's close (premium)
        entry_i = i
        entry_px = float(c[entry_i])
        # walk forward to the first bar the trail flips down (or series end)
        exit_i = n - 1
        reason = "series end"
        for j in range(entry_i + 1, n):
            if trend[j] == -1:
                exit_i = j
                reason = "trail flip"
                break
        exit_px = float(c[exit_i])
        gross = (exit_px - entry_px) * qty
        ch = costs.round_trip(entry_px, exit_px, qty)
        trades.append(BacktestTrade(
            entry_ms=int(timestamps_ms[entry_i]), exit_ms=int(timestamps_ms[exit_i]),
            direction=direction_label, entry_premium=round(entry_px, 2),
            exit_premium=round(exit_px, 2), qty=qty,
            gross_pnl=round(gross, 2), costs=round(ch, 2), net_pnl=round(gross - ch, 2),
            bars_held=exit_i - entry_i, exit_reason=reason))
        i = exit_i + 1   # no overlapping positions

    run = BacktestRun(mode="", caveat="")
    run.trades = trades
    run.stats, run.equity_curve = _stats_from_trades(trades, starting_capital)
    return run


def synthesize_premium(
    *,
    underlying_close: List[float],
    strike: float,
    iv: float,
    dte_days_start: float,
    bars_per_day: float,
    option_type: str,
) -> List[float]:
    """Model an option premium path from the underlying close path via Black-
    Scholes, decaying DTE one bar at a time (captures theta). Returns a premium
    close series aligned to ``underlying_close``."""
    out = []
    for k, spot in enumerate(underlying_close):
        dte = max(0.0, dte_days_start - k / max(bars_per_day, 1e-9))
        out.append(bs_price(spot=float(spot), strike=float(strike), dte_days=dte,
                            iv=float(iv), option_type=option_type))
    return out


def run_synthetic(
    *,
    timestamps_ms: List[int],
    u_open: List[float], u_high: List[float], u_low: List[float], u_close: List[float],
    cfg: TripleSupertrendConfig,
    trail_target: str,
    iv: float,
    dte_days: float,
    bars_per_day: float,
    moneyness_offset_pct: float,
    qty: int,
    costs: OptionCosts,
    starting_capital: float,
) -> BacktestRun:
    """Synthetic mode: ST on the UNDERLYING decides direction/entries; the option
    premium each bar is modeled with BS. For each entry we pick an ATM(+offset)
    call (bull) or put (bear) and price its premium path forward to the exit."""
    o = np.asarray(u_open, float)
    h = np.asarray(u_high, float)
    l = np.asarray(u_low, float)
    c = np.asarray(u_close, float)
    n = len(c)
    trades: List[BacktestTrade] = []
    if n <= cfg.warmup + 2:
        run = BacktestRun(mode="synthetic", caveat="")
        run.stats, run.equity_curve = _stats_from_trades(trades, starting_capital)
        return run

    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    trend = r.trend(trail_target)

    i = 0
    while i < n:
        is_long = longs[i]
        is_short = shorts[i]
        if not (is_long or is_short):
            i += 1
            continue
        opt_type = "CE" if is_long else "PE"
        spot0 = float(c[i])
        # ATM strike shifted by the moneyness offset (signed by direction).
        sign = 1.0 if is_long else -1.0
        strike = round(spot0 * (1.0 + sign * moneyness_offset_pct / 100.0), 0)
        # exit bar = first flip of the chosen trail against the position
        want = 1 if is_long else -1
        exit_i = n - 1
        reason = "series end"
        for j in range(i + 1, n):
            if trend[j] != want:
                exit_i = j
                reason = "trail flip"
                break
        # model premium at entry and exit
        held = exit_i - i
        entry_dte = dte_days
        exit_dte = max(0.0, dte_days - held / max(bars_per_day, 1e-9))
        entry_px = bs_price(spot=spot0, strike=strike, dte_days=entry_dte, iv=iv, option_type=opt_type)
        exit_px = bs_price(spot=float(c[exit_i]), strike=strike, dte_days=exit_dte, iv=iv, option_type=opt_type)
        gross = (exit_px - entry_px) * qty
        ch = costs.round_trip(entry_px, exit_px, qty)
        trades.append(BacktestTrade(
            entry_ms=int(timestamps_ms[i]), exit_ms=int(timestamps_ms[exit_i]),
            direction="long-call" if is_long else "long-put",
            entry_premium=round(entry_px, 2), exit_premium=round(exit_px, 2), qty=qty,
            gross_pnl=round(gross, 2), costs=round(ch, 2), net_pnl=round(gross - ch, 2),
            bars_held=held, exit_reason=reason))
        i = exit_i + 1

    run = BacktestRun(
        mode="synthetic",
        caveat=("Premium is MODELED (Black-Scholes, fixed IV "
                f"{iv:.0%}, theta decay) — not real fills. Tests the SIGNAL over real "
                "underlying history; not a substitute for live-contract premium."))
    run.trades = trades
    run.stats, run.equity_curve = _stats_from_trades(trades, starting_capital)
    return run
