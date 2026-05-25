"""Historical replay + live evaluation for the daily SMA/EMA + RSI/ADX strategy.

`run_backtest` replays bar-by-bar over daily candles with realistic execution:
  * a signal arms on the (closed) daily bar and fills on the *next* bar's open,
  * a slippage gate rejects fills that gap beyond `max_slippage`,
  * unfilled pending entries expire after 2 bars,
  * each open bar runs the exit ladder (ATR stop → RSI/ADX signal flip),
  * equity compounds off realised P&L so the curve reflects real growth.

`evaluate_live` runs the same pipeline at the last *closed* daily bar and
packages a snapshot for the UI dashboard.
"""
from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

from app.schemas.market import Candle
from app.engines.triple_st.config import TripleSTConfig
from app.engines.triple_st.features import compute_features, resample_to_daily, Features
from app.engines.triple_st import engine as eng
from app.engines.triple_st.engine import build_trade_plan, evaluate_at, warmup_ok
from app.engines.triple_st.exits import Position, step_position, Fill
from app.engines.triple_st.schemas import (
    StrategyEvaluation, TradePlanView,
    TripleSTBacktestResult, BacktestStats, BacktestTrade, EquityPoint,
)


MAX_LEVERAGE = 25.0


# ─────────────────────────────────────────────────────────────────────────────
# Backtest
# ─────────────────────────────────────────────────────────────────────────────


def run_backtest(
    underlying: str,
    candles: List[Candle],
    cfg: TripleSTConfig,
    lookback_days: int,
    fee_pct: float = 0.05,
) -> TripleSTBacktestResult:
    """Replay the strategy over `candles` (resampled to daily)."""
    daily = resample_to_daily(candles)
    trades: List[BacktestTrade] = []
    equity_curve: List[EquityPoint] = []

    if len(daily) < cfg.warmup_bars + 5:
        return _empty_result(underlying, lookback_days, cfg, len(daily))

    feat = compute_features(daily, cfg)
    n = feat.n

    equity = cfg.account_equity
    equity_curve.append(EquityPoint(ts=int(feat.ts[cfg.warmup_bars]), equity=round(equity, 2)))

    pos: Optional[Position] = None
    pending: Optional[dict] = None      # {"signal_bar", "dir"}

    for i in range(cfg.warmup_bars, n):
        # ── manage an open position ──
        if pos is not None and not pos.closed:
            fill = step_position(pos, feat, i, cfg, fee_pct)
            if fill is not None:
                trades.append(_finalize_trade(pos, fill))
                equity += fill.pnl_usd
                equity_curve.append(EquityPoint(ts=int(feat.ts[i]), equity=round(equity, 2)))
                pos = None
            continue

        # ── execute a pending entry on this bar's open ──
        if pending is not None:
            age = i - pending["signal_bar"]
            if age > 2:
                pending = None                       # expired
            else:
                ref_close = float(feat.close[pending["signal_bar"]])
                open_px = float(feat.open[i])
                slip = abs(open_px - ref_close) / ref_close * 100.0 if ref_close > 0 else 999
                if slip <= cfg.max_slippage:
                    pos = _open_position(feat, i, pending["dir"], cfg, equity)
                    pending = None
                    continue
                # else keep pending until expiry

        # ── arm a new entry when flat ──
        if pos is None and pending is None and warmup_ok(feat, i, cfg):
            sig = evaluate_at(feat, i, cfg)
            if sig.direction != 0:
                pending = {"signal_bar": i, "dir": sig.direction}

    stats = _compute_stats(trades, equity_curve, cfg.account_equity)
    return TripleSTBacktestResult(
        underlying=underlying, lookback_days=lookback_days,
        bars_evaluated=n - cfg.warmup_bars, config=cfg,
        stats=stats, trades=trades, equity_curve=equity_curve,
        timestamp_ms=int(time.time() * 1000),
    )


def _open_position(feat: Features, i: int, direction: int, cfg: TripleSTConfig, equity: float) -> Position:
    """Size off the *running* equity (compounding), fill at this bar's open."""
    entry = float(feat.open[i])
    atr = max(float(feat.atr[i]), entry * 1e-4)
    stop_dist = cfg.sl_atr_mult * atr
    long = direction == 1
    stop = entry - stop_dist if long else entry + stop_dist

    risk_usd = equity * (cfg.risk_percent / 100.0)
    size_units = risk_usd / stop_dist if stop_dist > 0 else 0.0
    notional = size_units * entry
    margin_budget = max(1.0, equity * (cfg.max_position_pct / 100.0))
    leverage = notional / margin_budget
    if leverage > MAX_LEVERAGE:
        scale = MAX_LEVERAGE / leverage
        size_units *= scale
        risk_usd = size_units * stop_dist            # actual risk after the cap

    return Position(
        direction=direction, entry=entry, entry_bar=i, entry_ts=int(feat.ts[i]),
        size_units=size_units, stop_loss=stop, r_distance=stop_dist, risk_usd=risk_usd,
    )


def _finalize_trade(pos: Position, fill: Fill) -> BacktestTrade:
    return BacktestTrade(
        direction="long" if pos.direction == 1 else "short",
        entry_ts=pos.entry_ts, exit_ts=fill.timestamp_ms,
        entry_price=round(pos.entry, 4), exit_price=round(fill.price, 4),
        bars_held=pos.bars_held, pnl_usd=round(fill.pnl_usd, 2),
        pnl_r=round(fill.pnl_usd / pos.risk_usd, 3) if pos.risk_usd > 0 else 0.0,
        exit_reason=fill.reason,
    )


def _compute_stats(trades, equity_curve, start_equity) -> BacktestStats:
    if not trades:
        final = equity_curve[-1].equity if equity_curve else start_equity
        return BacktestStats(
            total_trades=0, wins=0, losses=0, win_rate=0.0, avg_win_r=0.0,
            avg_loss_r=0.0, expectancy_r=0.0, profit_factor=0.0,
            max_drawdown_pct=0.0, sharpe=0.0, total_return_pct=0.0,
            long_trades=0, short_trades=0, avg_bars_held=0.0, final_equity=round(final, 2),
        )
    rs = np.array([t.pnl_r for t in trades])
    pnls = np.array([t.pnl_usd for t in trades])
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gross_win = float(pnls[pnls > 0].sum())
    gross_loss = float(abs(pnls[pnls <= 0].sum()))

    eq = np.array([p.equity for p in equity_curve])
    peak = np.maximum.accumulate(eq)
    max_dd = float(np.max((peak - eq) / peak)) * 100.0 if eq.size else 0.0
    sharpe = float(rs.mean() / rs.std() * np.sqrt(len(rs))) if rs.std() > 0 else 0.0
    final = float(eq[-1]) if eq.size else start_equity

    return BacktestStats(
        total_trades=len(trades),
        wins=int((rs > 0).sum()), losses=int((rs <= 0).sum()),
        win_rate=round(float((rs > 0).mean()), 4),
        avg_win_r=round(float(wins.mean()), 3) if wins.size else 0.0,
        avg_loss_r=round(float(losses.mean()), 3) if losses.size else 0.0,
        expectancy_r=round(float(rs.mean()), 3),
        profit_factor=round(gross_win / gross_loss, 3) if gross_loss > 0 else float(gross_win > 0) * 99.9,
        max_drawdown_pct=round(max_dd, 2), sharpe=round(sharpe, 3),
        total_return_pct=round((final - start_equity) / start_equity * 100.0, 2),
        long_trades=sum(1 for t in trades if t.direction == "long"),
        short_trades=sum(1 for t in trades if t.direction == "short"),
        avg_bars_held=round(float(np.mean([t.bars_held for t in trades])), 1),
        final_equity=round(final, 2),
    )


def _empty_result(underlying, lookback_days, cfg, n) -> TripleSTBacktestResult:
    return TripleSTBacktestResult(
        underlying=underlying, lookback_days=lookback_days, bars_evaluated=0,
        config=cfg, stats=_compute_stats([], [], cfg.account_equity),
        trades=[], equity_curve=[], timestamp_ms=int(time.time() * 1000),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live evaluation
# ─────────────────────────────────────────────────────────────────────────────


def _last_closed_bar(feat: Features) -> int:
    """Index of the last fully-closed daily bar (drops a forming current day)."""
    i = feat.n - 1
    today = int(time.time() * 1000) // 86_400_000
    if feat.n >= 2 and int(feat.ts[i]) // 86_400_000 >= today:
        i -= 1
    return i


def evaluate_live(
    underlying: str,
    candles: List[Candle],
    cfg: TripleSTConfig,
) -> StrategyEvaluation:
    """Evaluate the strategy at the last closed daily bar and build a UI snapshot."""
    daily = resample_to_daily(candles)
    if len(daily) < cfg.warmup_bars + 2:
        return _warming_eval(underlying, cfg, daily)

    feat = compute_features(daily, cfg)
    i = _last_closed_bar(feat)
    sig = evaluate_at(feat, i, cfg)
    ready = warmup_ok(feat, i, cfg)

    direction = sig.direction if ready else 0
    dir_str = "long" if direction == 1 else "short" if direction == -1 else "none"

    trade_plan: Optional[TradePlanView] = None
    if direction != 0:
        plan = build_trade_plan(feat, i, direction, cfg)
        trade_plan = TradePlanView(**plan.__dict__)

    reason = sig.reason if ready else f"warming up — need ≥{cfg.warmup_bars} daily bars"

    return StrategyEvaluation(
        underlying=underlying, timestamp_ms=int(feat.ts[i]), close=sig.close,
        timeframe=cfg.timeframe, direction=dir_str,
        sma=round(sig.sma, 4), ema=round(sig.ema, 4),
        rsi=round(sig.rsi, 2), adx=round(sig.adx, 2),
        above_sma=sig.above_sma, above_ema=sig.above_ema, rsi_gt_adx=sig.rsi_gt_adx,
        long_ok=sig.long_ok, short_ok=sig.short_ok,
        entry_ok=bool(direction != 0), executable=bool(trade_plan is not None),
        can_trade=True, block_reason="", reason=reason, trade_plan=trade_plan,
        equity=round(cfg.account_equity, 2), config=cfg, warming_up=not ready,
    )


def _warming_eval(underlying, cfg, daily) -> StrategyEvaluation:
    close = float(daily[-1].close) if daily else 0.0
    ts = int(daily[-1].timestamp_ms) if daily else int(time.time() * 1000)
    return StrategyEvaluation(
        underlying=underlying, timestamp_ms=ts, close=close, timeframe=cfg.timeframe,
        direction="none", sma=0.0, ema=0.0, rsi=0.0, adx=0.0,
        above_sma=False, above_ema=False, rsi_gt_adx=False, long_ok=False, short_ok=False,
        entry_ok=False, executable=False, can_trade=False, block_reason="warming up",
        reason=f"need ≥{cfg.warmup_bars + 2} daily bars", trade_plan=None,
        equity=round(cfg.account_equity, 2), config=cfg, warming_up=True,
    )
