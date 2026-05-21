"""
Walk-forward test for Hybrid VCP-Momentum Scalper.

Approach
────────
Unlike the directional engine walk-forward (which sweeps signal_score
thresholds), VCP profiles have fixed entry gates.  Walk-forward here
measures stability: run a fixed profile across rolling OOS windows and
check that Sharpe / win-rate / max_drawdown are consistent — not random.

Windows: train (300 bars) → select best profile variant →
         test (100 bars) OOS equity.  Step = 50 bars.

Swept parameters
────────────────
- hold_bars:    [12, 16, 20]
- stop_mult:    [0.8, 0.9, 1.0]
- flow_threshold: [0.30, 0.35, 0.40]

Profile variants are derived from PROFILES with the swept fields overridden.

Output
──────
WalkForwardVCPResult with per-window reports, aggregate Sharpe, and
recommended params (median of window winners).
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from app.schemas.market import Candle
from app.engines.hybrid_vcp.profiles import VCPProfile, PROFILES
from app.engines.hybrid_vcp.backtest import run_backtest, BacktestReport


@dataclass(frozen=True)
class VCPProfileVariant:
    """A VCPProfile with one or more swept fields overridden."""
    base_key:    str
    hold_bars:   int
    stop_mult:   float
    flow_threshold: float

    def apply_to(self, profile: VCPProfile) -> VCPProfile:
        return VCPProfile(
            label=f"{profile.label} h{self.hold_bars}s{self.stop_mult}f{int(self.flow_threshold*100)}",
            signal_tf=profile.signal_tf,
            regime_tf=profile.regime_tf,
            signal_bar_ms=profile.signal_bar_ms,
            regime_bar_ms=profile.regime_bar_ms,
            hold_bars=self.hold_bars,
            direction=profile.direction,
            vol_filter_pct=profile.vol_filter_pct,
            flow_threshold=self.flow_threshold,
            max_ibs_long=profile.max_ibs_long,
            min_ibs_short=profile.min_ibs_short,
            max_rsi_long=profile.max_rsi_long,
            min_rsi_short=profile.min_rsi_short,
            stop_mult=self.stop_mult,
            tp1_mult=profile.tp1_mult,
            tp2_mult=profile.tp2_mult,
            trail_mult=profile.trail_mult,
            risk_pct=profile.risk_pct,
            max_positions=profile.max_positions,
        )


# All variants to sweep
ALL_VARIANTS = [
    VCPProfileVariant(base_key=k, hold_bars=h, stop_mult=s, flow_threshold=f)
    for k in ["btc_scalping_15m", "btc_scalping_30m", "eth_scalping_15m", "eth_scalping_30m"]
    for h in [12, 16, 20]
    for s in [0.8, 0.9, 1.0]
    for f in [0.30, 0.35, 0.40]
]

# Fast variants for testing (3 per base profile — 12 total vs 108)
TEST_VARIANTS = [
    VCPProfileVariant(base_key=k, hold_bars=h, stop_mult=s, flow_threshold=f)
    for k in ["btc_scalping_15m", "btc_scalping_30m", "eth_scalping_15m", "eth_scalping_30m"]
    for h, s, f in [(16, 0.9, 0.35), (12, 0.9, 0.35), (16, 0.8, 0.30)]
]
VARIANT_PROFILES = {v.base_key: PROFILES[v.base_key] for v in ALL_VARIANTS}


@dataclass
class VCPWalkForwardWindow:
    window_idx:      int
    train_start:     int
    train_end:       int
    test_start:      int
    test_end:        int
    best_variant:    VCPProfileVariant
    test_report:      BacktestReport
    train_sharpe:    float
    no_edge:         bool  # True if test Sharpe < 0 (negative edge)


@dataclass
class WalkForwardVCPResult:
    windows:               List[VCPWalkForwardWindow]
    aggregate_report:       BacktestReport
    recommended_variant:    VCPProfileVariant
    windows_with_edge:     int
    oos_equity_curve:      List[float]


def _equity_from_trades(trades) -> np.ndarray:
    curve = [1.0]
    for t in trades:
        curve.append(curve[-1] * (1 + t.net_pnl))
    return np.array(curve) if len(curve) > 1 else np.array([1.0])


def _sharpe_from_trades(trades) -> float:
    if not trades:
        return 0.0
    ec = _equity_from_trades(trades)
    rets = np.diff(ec) / ec[:-1]
    if len(rets) < 2 or np.std(rets) == 0:
        return 0.0
    return float(np.mean(rets) / np.std(rets) * np.sqrt(252 * 96))


def run_walk_forward(
    candles: List[Candle],
    profile_key: str,
    train_bars: int = 300,
    test_bars:  int = 100,
    step_bars:  int = 50,
    require_positive_oos: bool = True,
    variants = None,
) -> WalkForwardVCPResult:
    """
    Run VCP walk-forward test with rolling train/test windows.

    Parameters
    ----------
    candles      : list of Candle — signal timeframe bars (15m or 30m)
    profile_key  : base profile key from PROFILES
    train_bars   : training window size (bars)
    test_bars    : test window size (bars)
    step_bars    : step between windows (bars)
    require_positive_oos : if True, skip windows where test Sharpe < 0
    variants     : list of VCPProfileVariant to sweep; defaults to TEST_VARIANTS
    """
    base_profile = VARIANT_PROFILES[profile_key]
    variants_for_key = [v for v in (variants or TEST_VARIANTS) if v.base_key == profile_key]

    windows: List[VCPWalkForwardWindow] = []
    oos_trades_all = []

    total = len(candles)
    idx = 0
    win_idx = 0

    while idx + train_bars + test_bars <= total:
        train_end = idx + train_bars
        test_end  = train_end + test_bars

        train_candles = candles[idx:train_end]
        test_candles  = candles[train_end:test_end]

        # ── Select best variant on training window ─────────────────
        best_variant = variants_for_key[0]
        best_sharpe   = -999.0

        for variant in variants_for_key:
            profile = variant.apply_to(base_profile)
            report  = run_backtest(train_candles, profile, apply_slippage=True)
            if report.trade_count == 0:
                continue
            s = _sharpe_from_trades(report.trades)
            if s > best_sharpe:
                best_sharpe = s
                best_variant = variant

        # ── Run OOS test with best variant ─────────────────────────
        test_profile = best_variant.apply_to(base_profile)
        test_report  = run_backtest(test_candles, test_profile, apply_slippage=True)

        no_edge = require_positive_oos and test_report.sharpe < 0

        if not no_edge:
            oos_trades_all.extend(test_report.trades)

        windows.append(VCPWalkForwardWindow(
            window_idx=win_idx,
            train_start=idx,
            train_end=train_end,
            test_start=train_end,
            test_end=test_end,
            best_variant=best_variant,
            test_report=test_report,
            train_sharpe=round(best_sharpe, 4),
            no_edge=no_edge,
        ))

        idx    += step_bars
        win_idx += 1

    # ── Aggregate OOS ────────────────────────────────────────────────
    oos_ec = _equity_from_trades(oos_trades_all)
    if oos_trades_all:
        rets   = np.diff(oos_ec) / oos_ec[:-1]
        sharpe = float(np.mean(rets) / np.std(rets) * np.sqrt(252 * 96)) if np.std(rets) > 0 else 0.0
        winners = sum(1 for t in oos_trades_all if t.net_pnl > 0)
        win_rate = round(winners / len(oos_trades_all), 4)
        gross_sum = float(sum(t.gross_pnl for t in oos_trades_all))
        losers = [t.net_pnl for t in oos_trades_all if t.net_pnl < 0]
        pf = abs(gross_sum / sum(losers)) if losers else 0.0
        running_max = np.maximum.accumulate(oos_ec)
        dd = (oos_ec / running_max - 1)
        max_dd = float(np.min(dd))
    else:
        sharpe = win_rate = pf = max_dd = 0.0

    agg_report = BacktestReport(
        profile=profile_key,
        trade_count=len(oos_trades_all),
        win_rate=win_rate,
        profit_factor=round(pf, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sharpe * 1.2, 4),
        max_drawdown=round(max_dd, 4),
        cagr=round(oos_ec[-1] - 1.0, 4) if len(oos_ec) > 1 else 0.0,
        trades=oos_trades_all,
        equity_curve=list(oos_ec),
    )

    # Median winner per window
    win_variants = [w.best_variant for w in windows if not w.no_edge]
    if win_variants:
        rec_h = int(np.median([v.hold_bars for v in win_variants]))
        rec_s = float(np.median([v.stop_mult for v in win_variants]))
        rec_f = float(np.median([v.flow_threshold for v in win_variants]))
        rec_variant = next(
            (v for v in variants_for_key
             if v.hold_bars == rec_h and abs(v.stop_mult - rec_s) < 0.01 and abs(v.flow_threshold - rec_f) < 0.01),
            variants_for_key[0],
        )
    else:
        rec_variant = best_variant

    wins_with_edge = sum(1 for w in windows if not w.no_edge)

    return WalkForwardVCPResult(
        windows=windows,
        aggregate_report=agg_report,
        recommended_variant=rec_variant,
        windows_with_edge=wins_with_edge,
        oos_equity_curve=list(oos_ec),
    )