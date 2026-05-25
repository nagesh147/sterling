"""Historical replay + live evaluation for the Triple SuperTrend strategy.

`run_backtest` replays bar-by-bar with realistic execution:
  * entries arm on the signal bar and fill on the *next* bar's open,
  * a slippage gate rejects fills that gap beyond `max_slippage`,
  * unfilled pending entries expire after 2 bars,
  * the full exit-priority ladder runs every bar,
  * `ProtectionState` halts/scales trading (daily loss, circuit breaker,
    black-swan, drawdown scaling, dynamic mode switching).

`evaluate_live` runs the same pipeline at the last closed bar and packages a
rich snapshot for the UI dashboard.
"""
from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

from app.schemas.market import Candle
from app.engines.triple_st.config import (
    TripleSTConfig,
    AssetClass,
    MODE_TABLE,
    classify_asset,
    ASSET_TABLE,
)
from app.engines.triple_st.features import compute_features, HTFContext, BTCContext, Features
from app.engines.triple_st import engine as eng
from app.engines.triple_st.engine import ProtectionState, build_trade_plan
from app.engines.triple_st.exits import Position, step_position, cooldown_bars, Fill
from app.engines.triple_st.schemas import (
    StrategyEvaluation, STLineView, QualityView, FilterView, RegimeView, TradePlanView,
    TripleSTBacktestResult, BacktestStats, BacktestTrade, EquityPoint,
)
from app.engines.triple_st.config import ST_CONFIGS


# ─────────────────────────────────────────────────────────────────────────────
# Shared setup
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_asset_class(cfg: TripleSTConfig, feat: Features) -> AssetClass:
    if cfg.asset_type != AssetClass.AUTO:
        return cfg.asset_type
    # Use the median ATR% over the series for a stable per-symbol classification.
    valid = feat.atr_percent[feat.atr_percent > 0]
    atr_pct = float(np.median(valid)) if valid.size else 2.0
    return classify_asset(atr_pct)


def _regime_label(r: eng.RegimeArrays, i: int) -> str:
    if r.is_choppy[i]:
        return "choppy"
    if r.is_compressed[i]:
        return "compressed"
    if r.is_high_vol[i]:
        return "high_vol"
    if r.is_trending[i]:
        return "trending"
    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# Backtest
# ─────────────────────────────────────────────────────────────────────────────


def run_backtest(
    underlying: str,
    candles_1h: List[Candle],
    candles_4h: Optional[List[Candle]],
    btc_candles_1h: Optional[List[Candle]],
    cfg: TripleSTConfig,
    lookback_days: int,
    fee_pct: float = 0.05,
) -> TripleSTBacktestResult:
    asset_class = AssetClass.LARGE
    trades: List[BacktestTrade] = []
    equity_curve: List[EquityPoint] = []

    if not candles_1h or len(candles_1h) < cfg.warmup_bars + 10:
        return _empty_result(underlying, lookback_days, cfg, asset_class, len(candles_1h or []))

    # First pass with a default volume-MA period just to classify the asset,
    # then recompute features with the resolved (asset-dependent) period.
    feat = compute_features(candles_1h, ASSET_TABLE[AssetClass.LARGE].vol_ma_period)
    asset_class = _resolve_asset_class(cfg, feat)
    asset = ASSET_TABLE[asset_class]
    # Recompute with the resolved volume-MA period (asset-dependent).
    feat = compute_features(candles_1h, asset.vol_ma_period)

    regime = eng.build_regime(feat, asset)
    cons = eng.build_consensus(feat, min_confirm=2)   # loosest; per-mode gate later
    htf = HTFContext.build(candles_4h) if candles_4h else None
    btc = BTCContext.build(btc_candles_1h) if btc_candles_1h else None

    prot = ProtectionState(cfg=cfg, equity=cfg.account_equity)
    equity_curve.append(EquityPoint(ts=int(feat.ts[cfg.warmup_bars]), equity=round(prot.equity, 2)))

    pos: Optional[Position] = None
    pending: Optional[dict] = None      # {"signal_bar", "dir"}
    cooldown_until = 0
    open_fills: List[Fill] = []

    # Fresh-flip tracking: enter only near the bar where the (mode-gated)
    # consensus first arms in a direction — trend-following entries belong at the
    # *start* of a trend, not mid-run. Re-entering an established trend mid-way is
    # what drove ~80% of trades straight into the stop.
    FRESH_WINDOW = 3
    prev_gated = 0
    flip_bar = -999

    n = feat.n
    for i in range(cfg.warmup_bars, n):
        day_key = int(feat.ts[i]) // 86_400_000
        btc_move = btc.daily_move_pct(int(feat.ts[i])) if btc else 0.0

        # Track consensus arming flips at the active mode's confirmation count.
        _mc = MODE_TABLE[prot.current_mode].min_confirm
        gd = int(cons.direction[i]) if int(cons.agree_count[i]) >= _mc else 0
        if gd != 0 and gd != prev_gated:
            flip_bar = i
        prev_gated = gd

        # ── manage an open position ──
        if pos is not None and not pos.closed:
            mode = MODE_TABLE[prot.current_mode]
            fills = step_position(pos, feat, regime, cons, i, mode, asset, cfg, fee_pct)
            open_fills.extend(fills)
            if pos.closed:
                trades.append(_finalize_trade(pos, open_fills))
                pnl_usd = sum(f.pnl_usd for f in open_fills)
                pnl_r = pnl_usd / pos.risk_usd if pos.risk_usd > 0 else 0.0
                prot.register_trade(pnl_usd, pnl_r, i)
                equity_curve.append(EquityPoint(ts=int(feat.ts[i]), equity=round(prot.equity, 2)))
                last_reason = open_fills[-1].reason if open_fills else "stop_loss"
                cooldown_until = i + cooldown_bars(last_reason, asset)
                pos, open_fills = None, []
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
                    pos = _open_position(feat, regime, i, pending["dir"], cfg, asset, prot)
                    pending = None
                    open_fills = []
                    continue
                # else keep pending until expiry

        # ── arm a new entry when flat, off cooldown, and allowed ──
        if pos is None and pending is None and i >= cooldown_until:
            ok, _why = prot.can_trade(i, day_key, btc_move)
            if ok:
                mode = MODE_TABLE[prot.current_mode]
                sig = eng.evaluate_at(
                    feat, regime, cons, i, cfg, asset, mode, htf, btc,
                    quality_threshold=prot.effective_quality_threshold(),
                )
                fresh = (i - flip_bar) <= FRESH_WINDOW and gd == sig.direction
                if sig.entry_ok and sig.direction != 0 and fresh:
                    pending = {"signal_bar": i, "dir": sig.direction}

    stats = _compute_stats(trades, equity_curve, cfg.account_equity)
    return TripleSTBacktestResult(
        underlying=underlying, lookback_days=lookback_days,
        bars_evaluated=n - cfg.warmup_bars, config=cfg, asset_class=asset_class,
        stats=stats, trades=trades, equity_curve=equity_curve,
        timestamp_ms=int(time.time() * 1000),
    )


def _open_position(feat, regime, i, direction, cfg, asset, prot) -> Position:
    mode = MODE_TABLE[prot.current_mode]
    plan = build_trade_plan(feat, regime, i, direction, cfg, asset, mode,
                            size_mult=prot.size_multiplier())
    # Use the actual fill (this bar's open) as the entry reference.
    entry = float(feat.open[i])
    long = direction == 1
    stop = entry - plan.r_distance if long else entry + plan.r_distance
    tp = entry + (plan.take_profit - plan.entry) if long else entry - (plan.entry - plan.take_profit)
    partials = []
    for r_mult, frac in mode.partials:
        p = entry + r_mult * plan.r_distance if long else entry - r_mult * plan.r_distance
        partials.append((p, frac))
    return Position(
        direction=direction, entry=entry, entry_bar=i, entry_ts=int(feat.ts[i]),
        size_units=plan.size_units, initial_sl=stop, current_sl=stop, take_profit=tp,
        r_distance=plan.r_distance, risk_usd=plan.risk_usd, partials=partials,
        mode_name=prot.current_mode.value,
    )


def _finalize_trade(pos: Position, fills: List[Fill]) -> BacktestTrade:
    pnl_usd = sum(f.pnl_usd for f in fills)
    wsum = sum(f.price * f.frac for f in fills)
    fsum = sum(f.frac for f in fills) or 1.0
    avg_exit = wsum / fsum
    return BacktestTrade(
        direction="long" if pos.direction == 1 else "short",
        entry_ts=pos.entry_ts,
        exit_ts=fills[-1].timestamp_ms,
        entry_price=round(pos.entry, 4), exit_price=round(avg_exit, 4),
        bars_held=pos.bars_held, pnl_usd=round(pnl_usd, 2),
        pnl_r=round(pnl_usd / pos.risk_usd, 3) if pos.risk_usd > 0 else 0.0,
        exit_reasons=[f.reason for f in fills], mode=pos.mode_name,
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


def _empty_result(underlying, lookback_days, cfg, asset_class, n) -> TripleSTBacktestResult:
    return TripleSTBacktestResult(
        underlying=underlying, lookback_days=lookback_days, bars_evaluated=0,
        config=cfg, asset_class=asset_class,
        stats=_compute_stats([], [], cfg.account_equity), trades=[], equity_curve=[],
        timestamp_ms=int(time.time() * 1000),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live evaluation
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_live(
    underlying: str,
    candles_1h: List[Candle],
    candles_4h: Optional[List[Candle]],
    btc_candles_1h: Optional[List[Candle]],
    cfg: TripleSTConfig,
    prot: Optional[ProtectionState] = None,
) -> StrategyEvaluation:
    """Evaluate the strategy at the last closed bar and build a UI snapshot."""
    if not candles_1h or len(candles_1h) < cfg.warmup_bars + 2:
        return _warming_eval(underlying, cfg, candles_1h)

    feat = compute_features(candles_1h, ASSET_TABLE[AssetClass.LARGE].vol_ma_period)
    asset_class = _resolve_asset_class(cfg, feat)
    asset = ASSET_TABLE[asset_class]
    feat = compute_features(candles_1h, asset.vol_ma_period)

    regime = eng.build_regime(feat, asset)
    cons = eng.build_consensus(feat, min_confirm=2)
    htf = HTFContext.build(candles_4h) if candles_4h else None
    btc = BTCContext.build(btc_candles_1h) if btc_candles_1h else None

    if prot is None:
        prot = ProtectionState(cfg=cfg, equity=cfg.account_equity)
    mode = MODE_TABLE[prot.current_mode]

    i = feat.n - 1
    eff_thr = prot.effective_quality_threshold()
    # Strict auto-arm signal (gated by the mode's min_confirm + all filters).
    sig = eng.evaluate_at(feat, regime, cons, i, cfg, asset, mode, htf, btc, quality_threshold=eff_thr)

    day_key = int(feat.ts[i]) // 86_400_000
    btc_move = btc.daily_move_pct(int(feat.ts[i])) if btc else 0.0
    can_trade, block_reason = prot.can_trade(i, day_key, btc_move)

    st_views = [
        STLineView(period=ST_CONFIGS[k][0], multiplier=ST_CONFIGS[k][1],
                   value=round(float(feat.st_lines[k][i]), 4), trend=int(feat.st_trends[k][i]))
        for k in range(len(ST_CONFIGS))
    ]

    # Display + manual-execution use the consensus *lean* (2/3 majority), so a
    # directional setup with a good quality score can be acted on by the operator
    # even when it hasn't strictly armed (e.g. only 2/3 STs agree, or one filter
    # is off-side). The strict `entry_ok` flag still drives the "ARMED" badge.
    lean = int(cons.direction[i])
    if lean != 0:
        qb = eng.lean_quality_score(feat, regime, cons, i, lean, htf)
        flt = eng.evaluate_filters(feat, regime, i, lean, cfg, asset, htf, btc)
        plan = build_trade_plan(feat, regime, i, lean, cfg, asset, mode, size_mult=prot.size_multiplier())
        trade_plan = TradePlanView(**plan.__dict__)
        q_pass = (not cfg.use_quality_score) or (qb.total >= eff_thr)
    else:
        qb = sig.quality
        flt = []
        trade_plan = None
        q_pass = False

    executable = bool(trade_plan is not None and can_trade)
    dd_pct = (prot.peak_equity - prot.equity) / max(1.0, prot.peak_equity) * 100.0
    dir_str = "long" if lean == 1 else "short" if lean == -1 else "none"

    # Reason: prefer the strict signal's wording when armed; otherwise explain
    # what's missing so the operator knows it's a discretionary (manual) trade.
    if not can_trade:
        reason = block_reason
    elif sig.entry_ok:
        reason = sig.reason
    elif lean != 0:
        off = [f.name for f in flt if not f.passed]
        bits = []
        if int(cons.agree_count[i]) < mode.min_confirm:
            bits.append(f"{int(cons.agree_count[i])}/3 ST (need {mode.min_confirm})")
        if not q_pass:
            bits.append(f"Q {qb.total:.0f}<{eff_thr:.0f}")
        if off:
            bits.append("filters: " + ", ".join(off))
        reason = "manual only — " + ("; ".join(bits) if bits else "armed") if not sig.entry_ok else sig.reason
    else:
        reason = sig.reason

    return StrategyEvaluation(
        underlying=underlying, timestamp_ms=int(feat.ts[i]), close=float(feat.close[i]),
        effective_mode=prot.current_mode, asset_class=asset_class,
        direction=dir_str, raw_long=lean == 1, raw_short=lean == -1, arrow=sig.arrow,
        consensus_count=int(cons.agree_count[i]), supertrends=st_views,
        quality=QualityView(
            consensus=qb.consensus, volume=qb.volume, htf=qb.htf,
            regime=qb.regime, momentum=qb.momentum, bonus=qb.bonus,
            total=round(qb.total, 1), threshold=eff_thr, passed=q_pass,
        ),
        filters=[FilterView(name=f.name, passed=f.passed, detail=f.detail) for f in flt],
        regime=RegimeView(
            is_compressed=bool(regime.is_compressed[i]), is_high_vol=bool(regime.is_high_vol[i]),
            is_trending=bool(regime.is_trending[i]), is_choppy=bool(regime.is_choppy[i]),
            post_squeeze=bool(regime.post_squeeze[i]), adx=round(float(feat.adx[i]), 1),
            chop=round(float(feat.chop[i]), 1), bb_ratio=round(float(regime.bb_ratio[i]), 3),
            label=_regime_label(regime, i),
        ),
        entry_ok=bool(sig.entry_ok and can_trade), executable=executable,
        can_trade=can_trade, block_reason=block_reason, reason=reason, trade_plan=trade_plan,
        equity=round(prot.equity, 2), drawdown_pct=round(dd_pct, 2),
        consecutive_losses=prot.consecutive_losses, size_multiplier=round(prot.size_multiplier(), 3),
        effective_quality_threshold=eff_thr, config=cfg, warming_up=False,
    )


def _warming_eval(underlying, cfg, candles_1h) -> StrategyEvaluation:
    close = float(candles_1h[-1].close) if candles_1h else 0.0
    ts = int(candles_1h[-1].timestamp_ms) if candles_1h else int(time.time() * 1000)
    return StrategyEvaluation(
        underlying=underlying, timestamp_ms=ts, close=close,
        effective_mode=cfg.mode, asset_class=AssetClass.LARGE,
        direction="none", raw_long=False, raw_short=False, arrow=False,
        consensus_count=0, supertrends=[],
        quality=QualityView(consensus=0, volume=0, htf=0, regime=0, momentum=0, bonus=0,
                            total=0, threshold=float(cfg.quality_threshold), passed=False),
        filters=[], regime=RegimeView(is_compressed=False, is_high_vol=False, is_trending=False,
                                      is_choppy=False, post_squeeze=False, adx=0, chop=50,
                                      bb_ratio=1.0, label="warmup"),
        entry_ok=False, executable=False, can_trade=False, block_reason="warming up",
        reason=f"need ≥{cfg.warmup_bars + 2} bars", trade_plan=None,
        equity=cfg.account_equity, drawdown_pct=0.0, consecutive_losses=0,
        size_multiplier=1.0, effective_quality_threshold=float(cfg.quality_threshold),
        config=cfg, warming_up=True,
    )
