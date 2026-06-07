"""
Comprehensive edge-discovery backtest.

For every (symbol x timeframe x strategy x profile) combination, simulate a
realistic bar-by-bar SL/TP exit on $500 starting capital, with round-trip
fees, and rank by net edge.

Inputs:  backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet
Outputs: BACKTEST_EDGE_REPORT.md  (top configs + full matrix)
"""

from __future__ import annotations

import glob
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

# Make the `app` package importable when run as `python backend/comprehensive_backtest.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Single source of truth — the live edge feed imports the same functions.
from app.engines.edge.strategies import SIGNAL_FNS, resample  # noqa: E402
from app.engines.edge.registry import PROFILE_CONFIG as PROFILES # noqa: E402
from app.engines.edge.robustness import run_robustness_gate # noqa: E402
from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold # noqa: E402

warnings.filterwarnings("ignore")

STARTING_CAPITAL = 500.0
FEE_ROUND_TRIP = 0.001  # 0.1% (Delta India taker ~0.05% per side)
MAX_HOLD_BARS = 200      # time-stop if no SL/TP hit

TIMEFRAMES = [("1min", "1m"), ("5min", "5m"), ("15min", "15m"),
              ("30min", "30m"), ("1h", "1h"), ("4h", "4h")]

# Annualization factor (bars per year per TF) for Sharpe
BARS_PER_YEAR = {
    "1m": 525_600, "5m": 105_120, "15m": 35_040,
    "30m": 17_520, "1h": 8_760,   "4h": 2_190,
}

STRATEGIES = list(SIGNAL_FNS.keys())


# Signal generators + resample now live in app/engines/edge/strategies.py
# (imported above) so the live edge feed runs identical logic.


# ---------------------------------------------------------------------------
# Bar-by-bar SL/TP simulator (sequential, no overlapping positions)
# ---------------------------------------------------------------------------

def simulate(df: pd.DataFrame, signals: np.ndarray,
             risk_config: dict, 
             profile_name: str = "Intraday",
             max_hold: int = MAX_HOLD_BARS) -> dict:
    """
    Return dictionary with rich trade metadata. Supports Trailing and Scale-Out.
    Long-only. Skips signals that fire while a position is open.
    """
    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    atr = df["atr"].to_numpy(dtype=np.float64)
    n = len(close)
    
    trades = []
    equity_curve = np.zeros(n)
    position = 0
    entry_idx = -1
    
    sl_mult = risk_config.get("sl_mult", 2.0)
    tp_mult = risk_config.get("tp_mult", 3.5)
    
    trailing_sl = None
    partial_closed = False
    partial_ret = 0.0
    
    # We iterate only where ATR is valid
    # To optimize, we can jump to the next signal instead of scanning every bar when flat
    i = 0
    while i < n:
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            i += 1
            continue
            
        if position == 0:
            if signals[i]:
                # New entry
                entry_price = close[i]
                atr_val = atr[i]
                sl = entry_price - sl_mult * atr_val
                tp = entry_price + tp_mult * atr_val
                trailing_sl = sl
                entry_idx = i
                position = 1
                partial_closed = False
            # Always advance when flat — a no-signal bar must not stall the loop
            # (previously fell through both branches → infinite loop).
            i += 1
            continue

        if position == 1:
            # === TRAILING LOGIC ===
            if "Trailing" in profile_name:
                trail_mult = risk_config.get("trail_mult", 1.5)
                new_trail = high[i] - trail_mult * atr[i]
                trailing_sl = max(trailing_sl, new_trail)
                sl = trailing_sl
                
            # === SCALE OUT LOGIC ===
            scale_out_enabled = "Scale_Out" in profile_name
            scale_target_r = risk_config.get("scale_target_r", 1.0)
            
            if scale_out_enabled and not partial_closed:
                scale_level = entry_price + scale_target_r * atr[entry_idx]
                if high[i] >= scale_level:
                    # Close 50% at this level
                    partial_ret = (scale_level / entry_price) - 1.0 - 0.001
                    # Move SL to breakeven for remainder
                    sl = entry_price
                    partial_closed = True
            
            # === EXIT CHECKS ===
            exit_price = None
            if low[i] <= sl:
                exit_price = sl
            elif high[i] >= tp:
                exit_price = tp
            elif (i - entry_idx) >= max_hold:
                exit_price = close[i]
                
            if exit_price is not None:
                final_ret = (exit_price / entry_price) - 1.0 - 0.001
                if partial_closed:
                    total_ret = 0.5 * partial_ret + 0.5 * final_ret
                else:
                    total_ret = final_ret
                    
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': i,
                    'entry': entry_price,
                    'exit': exit_price,
                    'return': float(total_ret),
                    'bars_held': i - entry_idx,
                    'partial_exit': partial_closed,
                    'profile': profile_name
                })
                position = 0
                partial_closed = False
                trailing_sl = None
                equity_curve[i] = total_ret
            
            i += 1
            
    return {
        'trades': trades,
        'returns': np.array([t['return'] for t in trades], dtype=np.float64),
        'return_stream': equity_curve,
        'cumulative_equity': np.cumsum(equity_curve)
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def metrics(sim_result: dict, tf_label: str,
            starting_capital: float = STARTING_CAPITAL) -> dict:
    returns = sim_result['returns']
    trades_meta = sim_result['trades']
    n = len(returns)
    
    if n == 0:
        return dict(trades=0, win_rate=0.0, pf=0.0, sharpe=0.0,
                    expectancy=0.0, gross_profit=0.0, gross_loss=0.0,
                    net_return=0.0, end_capital=starting_capital,
                    pnl_usd=0.0, max_dd=0.0, avg_bars_held=0.0)
                    
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gp_pct = float(wins.sum()) if wins.size else 0.0
    gl_pct = float(-losses.sum()) if losses.size else 0.0
    pf = gp_pct / gl_pct if gl_pct > 0 else (99.99 if gp_pct > 0 else 0.0)
    win_rate = wins.size / n
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(-losses.mean()) if losses.size else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    cum = float(np.prod(1 + returns))
    end_cap = starting_capital * cum
    
    if returns.std(ddof=1) > 0 and n > 1:
        sharpe = float(np.sqrt(252) * returns.mean() / returns.std(ddof=1))
    else:
        sharpe = 0.0
        
    equity = starting_capital * np.cumprod(1 + returns)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min())
    
    avg_bars_held = float(np.mean([t['bars_held'] for t in trades_meta]))
    
    return dict(
        trades=n, win_rate=win_rate, pf=pf, sharpe=sharpe,
        expectancy=expectancy,
        gross_profit=starting_capital * gp_pct,
        gross_loss=starting_capital * gl_pct,
        net_return=cum - 1.0,
        end_capital=end_cap,
        pnl_usd=end_cap - starting_capital,
        max_dd=max_dd,
        avg_bars_held=avg_bars_held
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def load_symbol(path: str) -> pd.DataFrame:
    cols = ["time", "symbol", "open", "high", "low", "close",
            "volume", "volatility_atr"]
    df = pd.read_parquet(path, columns=cols)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()
    return df


def main() -> None:
    t0 = time.time()
    files = sorted(glob.glob("backend/vector_store_1m_*.parquet"))
    assert files, "No parquet files found under backend/"
    print(f"[load] {len(files)} symbols")

    rows = []
    # Multiple-testing trial count for the deflated Sharpe = the ENTIRE search
    # grid we mined to pick winners (symbols × timeframes × strategies ×
    # profiles), not just strategy×profile. Deflating by the full grid is the
    # honest (conservative) choice — you tested every one of these hypotheses.
    total_trials = len(files) * len(TIMEFRAMES) * len(STRATEGIES) * len(PROFILES)
    for f in files:
        symbol = os.path.basename(f).split("_")[-1].replace(".parquet", "")
        print(f"[{symbol}] loading {f}")
        df_1m = load_symbol(f)
        # Pre-resample all timeframes once per symbol
        tf_data = {}
        for rule, label in TIMEFRAMES:
            tf_data[label] = resample(df_1m, rule)
            print(f"  {label}: {len(tf_data[label]):>10,} bars")
        for tf_label in [t[1] for t in TIMEFRAMES]:
            df_tf = tf_data[tf_label]
            # Passive buy-and-hold over the SAME window — the benchmark every
            # config must beat to have earned its complexity + fee drag. It is
            # identical for all (strategy, profile) on this (symbol, tf), so
            # compute it once here.
            hodl = hodl_benchmark(df_tf["close"].to_numpy(dtype=np.float64),
                                  fee_rt_pct=FEE_ROUND_TRIP)
            for strat in STRATEGIES:
                sigs = SIGNAL_FNS[strat](df_tf)
                for prof_name, prof_cfg in PROFILES.items():
                    sim_result = simulate(df_tf, sigs,
                                          prof_cfg,
                                          profile_name=prof_name)
                    m = metrics(sim_result, tf_label)

                    robust_metrics = run_robustness_gate(
                        sim_result['trades'],
                        sim_result['return_stream'],
                        num_trials=total_trials
                    )
                    rel = beats_buy_and_hold(m["net_return"], m["max_dd"], hodl)

                    rows.append({
                        "symbol": symbol, "tf": tf_label, "strategy": strat,
                        "profile": prof_name, **m, **robust_metrics,
                        "hodl_net_return": hodl["net_return"],
                        "hodl_max_dd": hodl["max_drawdown"],
                        "excess_vs_hold": rel["excess_return"],
                        "beats_hold": rel["beats_hold"],
                    })
            print(f"  {tf_label} done")

    res = pd.DataFrame(rows)
    res.to_csv("backtest_edge_results.csv", index=False)
    print(f"\n[done] {len(res)} configs evaluated in {time.time()-t0:.1f}s")
    print(f"[csv]  backtest_edge_results.csv")

    # ----- Build report
    write_report(res)


def df_to_md(df: pd.DataFrame) -> str:
    """Tabulate-free markdown table for a DataFrame with named index."""
    idx_name = df.index.name or ""
    cols = [idx_name] + list(df.columns)
    head = "| " + " | ".join(str(c) for c in cols) + " |\n"
    head += "|" + "|".join(["---"] * len(cols)) + "|\n"
    lines = []
    for ix, row in df.iterrows():
        vals = [str(ix)] + [f"{v:.4f}" if isinstance(v, (int, float, np.floating))
                            else str(v) for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return head + "\n".join(lines)


def fmt_strat(s: str) -> str:
    return {
        "ma_crossover":  "MA Crossover",
        "mean_reversion": "Mean Reversion",
        "breakout":      "Breakout",
        "price_action":  "Price Action",
        "smc":           "SMC FVG",
        "vwap_cross":    "VWAP Cross",
        "bb_rsi_reversion": "BB RSI Mean Reversion",
    }.get(s, s.replace("_", " ").title())


def hold_section(valid: pd.DataFrame) -> str:
    """Strategy-vs-buy-and-hold: the benchmark the original study omitted.

    A config 'beats hold' only if it returned MORE than passively holding the
    same asset over the same window AND drew down LESS. Holding is fully
    invested; strategies are in-market only part of the time — this is the
    honest opportunity-cost comparison.
    """
    if "beats_hold" not in valid.columns or valid.empty:
        return ""
    n = len(valid)
    winners = valid[valid["beats_hold"]].sort_values("excess_vs_hold", ascending=False)
    out = ["## 🪙 Strategy vs. Buy-and-Hold (the missing benchmark)\n\n",
           f"**{len(winners)} of {n}** configs (≥30 trades) beat buy-and-hold on "
           "BOTH return and drawdown. Everything else is a worse way to hold the asset.\n\n"]
    if winners.empty:
        out.append("> No configuration beat buy-and-hold on a risk-adjusted basis — "
                   "the apparent 'edge' is long-only beta.\n\n")
        return "".join(out)
    head = ("| # | Strategy (TF) | Symbol | Profile | Strat Net | HODL Net | Excess | "
            "Strat MaxDD | HODL MaxDD |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    body = []
    for i, r in enumerate(winners.head(20).itertuples(), 1):
        body.append(
            f"| {i} | {fmt_strat(r.strategy)} ({r.tf}) | {r.symbol} | {r.profile} | "
            f"{r.net_return*100:+.1f}% | {r.hodl_net_return*100:+.1f}% | "
            f"{r.excess_vs_hold*100:+.1f}% | {r.max_dd*100:.1f}% | {r.hodl_max_dd*100:.1f}% |")
    out.append(head + "\n".join(body) + "\n\n")
    return "".join(out)


def section(df: pd.DataFrame, title: str, n: int = 20) -> str:
    head = (
        "| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | "
        "Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | "
        "Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = []
    for i, r in enumerate(df.head(n).itertuples(), 1):
        oos_str = f"{r.oos_sharpe:.2f}" if r.oos_sharpe > -100 else "-∞"
        body.append(
            f"| {i} | {fmt_strat(r.strategy)} ({r.tf}) | {r.symbol} | {r.profile} | "
            f"{r.trades} | {r.win_rate*100:.1f}% | {r.pf:.2f} | "
            f"{r.expectancy*100:.3f}% | {r.sharpe:.2f} | {oos_str} | {r.p_loss*100:.1f}% | {r.p_sup*100:.1f}% | {r.dsr:.2f} | {r.max_dd*100:.1f}% | "
            f"${r.gross_profit:.2f} | ${r.gross_loss:.2f} | {r.net_return*100:+.1f}% | "
            f"${r.pnl_usd:+.2f} |"
        )
    return f"## {title}\n\n{head}" + "\n".join(body) + "\n\n"


def write_report(res: pd.DataFrame) -> None:
    # Filter to configs with enough trades for any conclusion to mean something
    valid = res[res["trades"] >= 30].copy()
    deg = res[res["trades"] < 30].copy()

    out = ["# Sterling Edge-Discovery Backtest\n",
           f"_Generated {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_  ",
           f"_Capital: ${STARTING_CAPITAL:.0f}  Fees: {FEE_ROUND_TRIP*100:.2f}% round-trip  "
           f"Max hold: {MAX_HOLD_BARS} bars  Data: 2023-12-29 → 2026-05-30_\n\n",
           "## Methodology\n",
           "- **Data**: 1-minute OHLCV from `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet`, "
           "resampled to 1m / 5m / 15m / 30m / 1h / 4h.\n",
           "- **Strategies (long-only)**: MA Crossover (EMA 9/21), Mean Reversion (RSI(14) cross up from <30), "
           "Breakout (20-bar Donchian high), Price Action (bullish engulfing), SMC FVG (bullish fair-value gap).\n",
           "- **Profiles**: SL/TP risk style applied as ATR multiples — "
           "**Scalping** SL 1.0 × ATR / TP 2.0 × ATR · **Intraday** SL 2.0 / TP 3.5 · **Aggressive** SL 1.5 / TP 4.5.\n",
           "- **Exits**: bar-by-bar first-touch SL/TP simulation; time-stop after "
           f"{MAX_HOLD_BARS} bars if neither hit. Fee {FEE_ROUND_TRIP*100:.2f}% round-trip.\n",
           "- **Capital**: $500 nominal per trade, single-shot sequential (no overlapping positions). "
           "PnL compounds. Sharpe uses √252 scaling on per-trade returns.\n",
           f"- **Configs evaluated**: {len(res)} ({len(valid)} with ≥30 trades). "
           f"Results CSV: `backtest_edge_results.csv`.\n\n",
           "---\n\n"]

    if valid.empty:
        out.append("> No configurations produced ≥30 trades. See degenerate set below.\n")
    else:
        # Best by raw PnL
        by_pnl = valid.sort_values("pnl_usd", ascending=False)
        out.append(section(by_pnl, "🏆 Top 20 by Bottom-Line PnL (Compounded $500)", 20))

        # Best by Sharpe
        by_sharpe = valid.sort_values("sharpe", ascending=False)
        out.append(section(by_sharpe, "📈 Top 15 by Sharpe (Risk-Adjusted Edge)", 15))

        # Best by Profit Factor
        by_pf = valid[valid["pf"] < 50].sort_values("pf", ascending=False)
        out.append(section(by_pf, "💰 Top 15 by Profit Factor", 15))

        # Best by Expectancy
        by_exp = valid.sort_values("expectancy", ascending=False)
        out.append(section(by_exp, "🎯 Top 15 by Expectancy per Trade", 15))

        # The Winner — must rank top by all three of {PnL, Sharpe, PF}
        merged = valid.copy()
        merged["rank_pnl"] = merged["pnl_usd"].rank(ascending=False, method="min")
        merged["rank_sharpe"] = merged["sharpe"].rank(ascending=False, method="min")
        merged["rank_pf"] = merged["pf"].rank(ascending=False, method="min")
        merged["composite_rank"] = (merged["rank_pnl"] + merged["rank_sharpe"]
                                    + merged["rank_pf"]) / 3
        winner = merged.sort_values("composite_rank").head(10)
        out.append(section(winner, "🥇 Composite Winner (avg rank of PnL + Sharpe + PF)", 10))

        # The benchmark the original study omitted.
        out.append(hold_section(valid))

        # Per-symbol best
        for sym in sorted(valid["symbol"].unique()):
            sub = valid[valid["symbol"] == sym].sort_values("pnl_usd", ascending=False)
            out.append(section(sub, f"Best by {sym}", 5))

        # Per-profile aggregates
        out.append("## Profile Roll-Up (median across configs with ≥30 trades)\n\n")
        agg = (valid.groupby("profile")[["trades", "win_rate", "pf", "sharpe",
                                         "expectancy", "net_return", "pnl_usd",
                                         "max_dd"]]
               .median().round(4))
        out.append(df_to_md(agg) + "\n\n")

        # Per-strategy aggregates
        out.append("## Strategy Roll-Up (median across configs with ≥30 trades)\n\n")
        agg = (valid.groupby("strategy")[["trades", "win_rate", "pf", "sharpe",
                                          "expectancy", "net_return", "pnl_usd",
                                          "max_dd"]]
               .median().round(4))
        agg.index = [fmt_strat(s) for s in agg.index]
        agg.index.name = "strategy"
        out.append(df_to_md(agg) + "\n\n")

        # Per-timeframe aggregates
        out.append("## Timeframe Roll-Up (median across configs with ≥30 trades)\n\n")
        agg = (valid.groupby("tf")[["trades", "win_rate", "pf", "sharpe",
                                    "expectancy", "net_return", "pnl_usd",
                                    "max_dd"]]
               .median().round(4))
        out.append(df_to_md(agg) + "\n\n")

    if not deg.empty:
        out.append("---\n\n")
        out.append(f"## Degenerate / Low-Sample Configs ({len(deg)} skipped from rankings)\n\n")
        out.append("Configs that fired fewer than 30 trades. Reported for completeness.\n\n")
        # Just show count distribution
        cnt = deg.groupby(["tf", "strategy"]).size().unstack(fill_value=0)
        out.append(df_to_md(cnt) + "\n")

    with open("BACKTEST_EDGE_REPORT.md", "w") as f:
        f.write("".join(out))
    print("[report] BACKTEST_EDGE_REPORT.md")


if __name__ == "__main__":
    main()
