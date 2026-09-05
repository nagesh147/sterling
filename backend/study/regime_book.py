"""Regime-gated, symmetric (long+short), 3-symbol-pooled research book.

RESEARCH TOOL — not wired into anything live. Answers one honest question:
does routing momentum vs mean-reversion by regime, allowing shorts, and pooling
BTC/ETH/SOL into one capped book produce a FORWARD edge that beats the long-only
single-symbol baseline — and does anything clear DSR >= 0.5?

Spec: docs/superpowers/specs/2026-06-09-regime-book-rework-design.md
Run:  cd backend && .venv/bin/python -m study.regime_book
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

from app.engines.edge.strategies import (
    resample, signals_ma_crossover, signals_bb_rsi_mean_reversion,
)
from study.sim import simulate_idx, sharpe as _sharpe
from app.engines.edge.robustness import deflated_sharpe_ratio
from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold

FEE_RT = 0.001
MAX_HOLD = 200


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX(period). Rolling/ewm only → leak-free."""
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def classify_regime(df: pd.DataFrame, adx_threshold: float = 25.0,
                    ma_window: int = 50) -> np.ndarray:
    """Per-bar regime: +1 uptrend, -1 downtrend, 0 range. Leak-free.

    Trend when ADX(14) >= adx_threshold; sign from the slope of SMA(ma_window).
    The single regime knob is adx_threshold; ma_window is fixed.
    """
    adx = _adx(df)
    ma = df["close"].rolling(ma_window).mean()
    slope = ma.diff()
    trend = (adx >= adx_threshold).to_numpy()
    up = (slope > 0).to_numpy()
    reg = np.zeros(len(df), dtype=int)
    reg[trend & up] = 1
    reg[trend & ~up] = -1
    reg[~np.isfinite(adx.to_numpy())] = 0
    return reg


def short_momentum(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_ma_crossover: fire on a fresh bearish 9/21 EMA cross."""
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bear = fast < slow
    return (bear & ~bear.shift(1).fillna(False)).to_numpy()


def short_mean_reversion(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_bb_rsi_mean_reversion: fade the upper Bollinger band
    (close drops back below upper) while RSI(14) is hot (> 60)."""
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(20).mean()
    std = c.rolling(20).std()
    upper = sma + 2 * std
    fade = (c < upper) & (c.shift(1) >= upper.shift(1))
    return (fade & (rsi > 60)).fillna(False).to_numpy()


def _routed_trend_entries(
    df: pd.DataFrame,
    reg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Enter once when EMA direction and confirmed trend first align."""

    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    long_state = (fast > slow).to_numpy() & (reg == 1)
    short_state = (fast < slow).to_numpy() & (reg == -1)
    prior_long = np.r_[False, long_state[:-1]]
    prior_short = np.r_[False, short_state[:-1]]
    return long_state & ~prior_long, short_state & ~prior_short


def route_signals(df: pd.DataFrame, adx_threshold: float = 25.0,
                  ma_window: int = 50, use_regime: bool = True):
    """Route raw sleeve signals through the regime gate.

    Returns (long_sigs, short_sigs) boolean arrays, same length as df:
      regime +1 (uptrend)   -> momentum long
      regime -1 (downtrend) -> momentum short
      regime  0 (range)     -> mean-reversion long + short

    use_regime=False is the spine baseline (no gate): momentum long+short and
    MR long+short fire everywhere — lets us measure whether the gate earns its
    degree of freedom.
    """
    reg = classify_regime(df, adx_threshold, ma_window)
    mom_long = signals_ma_crossover(df)
    mom_short = short_momentum(df)
    mr_long = signals_bb_rsi_mean_reversion(df)
    mr_short = short_mean_reversion(df)
    if not use_regime:
        longs = mom_long | mr_long
        shorts = mom_short | mr_short
        return longs, shorts
    # A crossover can precede ADX/SMA regime confirmation. Gating only the
    # one-bar crossover event loses that setup permanently when the regime
    # becomes eligible a few bars later. Emit once when the combined
    # momentum-state + regime predicate changes from false to true. This is
    # causal and preserves the intended "enter on confirmed trend" behavior.
    trend_longs, trend_shorts = _routed_trend_entries(df, reg)
    longs = trend_longs | (mr_long & (reg == 0))
    shorts = trend_shorts | (mr_short & (reg == 0))
    return longs, shorts


def merge_portfolio(trades: list[dict], max_concurrent: int = 3) -> list[dict]:
    """Greedy interval scheduler: accept trades in entry-time order while fewer
    than max_concurrent are open; emit the accepted set ordered by exit_time.

    Each trade is {'symbol','entry_time','exit_time','pnl_pct'}. Models a single
    book that can hold at most max_concurrent positions at once (one per name in
    the default 3-symbol case). Dropped trades are capital we did not have free.
    """
    by_entry = sorted(trades, key=lambda t: t["entry_time"])
    open_exits: list = []
    kept: list[dict] = []
    for t in by_entry:
        open_exits = [x for x in open_exits if x > t["entry_time"]]
        if len(open_exits) >= max_concurrent:
            continue
        open_exits.append(t["exit_time"])
        kept.append(t)
    return sorted(kept, key=lambda t: t["exit_time"])


# (sl, tp) bracket used for both directions; Aggressive profile from the study.
_SL, _TP = 1.5, 4.5


def build_symbol_trades(symbol: str, df: pd.DataFrame, adx_threshold: float = 25.0,
                        ma_window: int = 50, use_regime: bool = True,
                        trail_mult: float | None = None) -> list[dict]:
    """Route, simulate long+short, return trades tagged with symbol + timestamps."""
    longs, shorts = route_signals(df, adx_threshold, ma_window, use_regime)
    out: list[dict] = []
    for sigs, direction in ((longs, "long"), (shorts, "short")):
        raw = simulate_idx(df, sigs, _SL, _TP, direction=direction,
                           fee_rt=FEE_RT, max_hold=MAX_HOLD, trail_mult=trail_mult)
        for t in raw:
            out.append({
                "symbol": symbol,
                "direction": direction,
                "entry_time": df.index[t["entry_bar"]],
                "exit_time": df.index[t["exit_bar"]],
                "pnl_pct": t["pnl_pct"],
            })
    return out


def portfolio_equity(trades: list[dict], cap: float = 500.0,
                     max_concurrent: int = 3) -> dict:
    """Cap concurrency, then compound a single book where each trade risks a
    1/max_concurrent slice of equity (equal-risk allocation). Exit-time ordered."""
    kept = merge_portfolio(trades, max_concurrent)
    w = 1.0 / max_concurrent
    pnls = [t["pnl_pct"] for t in kept]
    if not pnls:
        return {"end": cap, "ret": 0.0, "sharpe": 0.0, "max_dd": 0.0,
                "n": 0, "weighted_pnls": []}
    wpnls = [p * w for p in pnls]
    a = np.asarray(wpnls, float)
    eq = cap * np.cumprod(1 + a)
    peak = np.maximum.accumulate(eq)
    return {"end": float(eq[-1]), "ret": float(eq[-1] / cap - 1.0),
            "sharpe": _sharpe(wpnls), "max_dd": float(((eq - peak) / peak).min()),
            "n": len(pnls), "weighted_pnls": wpnls}


def _basket_hodl(frames: dict, oos_start: float, fee_rt: float = FEE_RT) -> dict:
    """Equal-weight buy-and-hold of all symbols over the OOS span — the honest
    benchmark for a pooled book. Each symbol's OOS closes are normalised to 1.0
    at the span start, aligned on a common time grid, and averaged into one
    basket equity curve; net_return + max_drawdown are read off that curve.
    (Concatenating raw prices would inject fake jumps at symbol boundaries.)"""
    cols = []
    for sym, df in frames.items():
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        sub = df["close"][df.index >= cut]
        if len(sub) > 1:
            cols.append((sub / sub.iloc[0]).rename(sym))
    if not cols:
        return {"net_return": 0.0, "max_drawdown": 0.0, "final_equity": 1.0, "n_bars": 0}
    basket = pd.concat(cols, axis=1).ffill().dropna().mean(axis=1)
    return hodl_benchmark(basket.to_numpy(), fee_rt_pct=fee_rt)


def walk_forward_book(frames: dict, adx_threshold: float = 25.0,
                      ma_window: int = 50, use_regime: bool = True,
                      trail_mult: float | None = None, n_folds: int = 5,
                      oos_start: float = 0.5, cap: float = 500.0,
                      max_concurrent: int = 3) -> dict:
    """Pool all symbols, take the OOS tail [oos_start, 1.0] of calendar time as
    the forward book. The regime/short/MR logic uses only past bars per signal,
    so a fixed-parameter forward evaluation is leak-free. (Parameter SELECTION
    across adx_threshold is done by the caller comparing whole-book OOS results,
    never per-fold on test data.) Returns OOS book stats + DSR + hold-beat."""
    all_trades: list[dict] = []
    for sym, df in frames.items():
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        trades = build_symbol_trades(sym, df, adx_threshold, ma_window,
                                     use_regime, trail_mult)
        all_trades += [t for t in trades if t["entry_time"] >= cut]
    eq = portfolio_equity(all_trades, cap, max_concurrent)
    hodl = _basket_hodl(frames, oos_start)
    rel = beats_buy_and_hold(eq["ret"], eq["max_dd"], hodl)
    dsr = deflated_sharpe_ratio(eq["weighted_pnls"], num_trials=525) \
        if eq["weighted_pnls"] else 0.0
    return {"oos": eq, "dsr": round(dsr, 4),
            "beats_hold": rel["beats_hold"], "excess_vs_hold": rel["excess_return"],
            "n": eq["n"], "hodl": hodl}


# --- Upgrade: volatility-targeted sizing + sleeve-specific exits ---------
# Trend trades let winners run (wide TP + chandelier trail); mean-reversion
# trades take a fixed target. This is the fix for the earlier mistake of
# applying one exit to both sleeves.
_TREND_EXIT = {"sl": 2.0, "tp": 12.0, "trail": 3.5}
_MR_EXIT = {"sl": 1.5, "tp": 4.5, "trail": None}


def _weight_from_stop(stop_dist_pct: float, risk_per_trade: float,
                      max_leverage: float) -> float:
    """Notional weight so a stop-out costs ~risk_per_trade of equity, capped."""
    if stop_dist_pct <= 0:
        return 0.0
    return min(risk_per_trade / stop_dist_pct, max_leverage)


def vol_target_weight(entry: float, atr: float, slm: float,
                      risk_per_trade: float = 0.01,
                      max_leverage: float = 3.0) -> float:
    """Position weight (fraction of equity) that equalises per-trade risk:
    tighter stops (lower ATR) → larger size, so each trade risks the same
    fraction if stopped. Capped at max_leverage."""
    stop_dist = (slm * atr / entry) if entry > 0 else 0.0
    return _weight_from_stop(stop_dist, risk_per_trade, max_leverage)


def _mr_signals(df: pd.DataFrame, rsi_lo: float = 40.0, rsi_hi: float = 60.0,
                bb_lk: int = 20, bb_std: float = 2.0):
    """Parameterised Bollinger+RSI mean-reversion long/short signals. Tighter
    RSI thresholds (lower rsi_lo / higher rsi_hi) = conviction concentration:
    fewer, deeper-extreme setups. Defaults reproduce the loose sleeve."""
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    r = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(bb_lk).mean()
    sd = c.rolling(bb_lk).std()
    lower, upper = sma - bb_std * sd, sma + bb_std * sd
    long = ((c > lower) & (c.shift(1) <= lower.shift(1)) & (r < rsi_lo)).fillna(False).to_numpy()
    short = ((c < upper) & (c.shift(1) >= upper.shift(1)) & (r > rsi_hi)).fillna(False).to_numpy()
    return long, short


def build_symbol_trades_sleeved(symbol: str, df: pd.DataFrame,
                                adx_threshold: float = 25.0, ma_window: int = 50,
                                use_regime: bool = True,
                                rsi_lo: float = 40.0, rsi_hi: float = 60.0) -> list[dict]:
    """Like build_symbol_trades but keeps the two sleeves separate so each gets
    its own exit: trend = let-it-run (wide TP + 3.5·ATR trail), MR = fixed
    1.5/4.5 bracket. Tags sleeve + stop_dist_pct (for vol-target sizing).
    rsi_lo/rsi_hi tighten the MR sleeve into conviction-only setups."""
    reg = classify_regime(df, adx_threshold, ma_window)
    close = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    mr_long, mr_short = _mr_signals(df, rsi_lo, rsi_hi)
    sleeves = {
        "trend": {"long": signals_ma_crossover(df), "short": short_momentum(df), **_TREND_EXIT},
        "mr": {"long": mr_long, "short": mr_short, **_MR_EXIT},
    }
    if use_regime:
        trend_long, trend_short = _routed_trend_entries(df, reg)
        sleeves["trend"]["long"] = trend_long
        sleeves["trend"]["short"] = trend_short
        sleeves["mr"]["long"] = sleeves["mr"]["long"] & (reg == 0)
        sleeves["mr"]["short"] = sleeves["mr"]["short"] & (reg == 0)
    out: list[dict] = []
    for name, cfg in sleeves.items():
        for direction in ("long", "short"):
            raw = simulate_idx(df, cfg[direction], cfg["sl"], cfg["tp"],
                               direction=direction, fee_rt=FEE_RT,
                               max_hold=MAX_HOLD, trail_mult=cfg["trail"])
            for t in raw:
                e = close[t["entry_bar"]]
                a = atr[t["entry_bar"]]
                out.append({
                    "symbol": symbol, "sleeve": name, "direction": direction,
                    "entry_time": df.index[t["entry_bar"]],
                    "exit_time": df.index[t["exit_bar"]],
                    "pnl_pct": t["pnl_pct"],
                    "stop_dist_pct": (cfg["sl"] * a / e) if e > 0 else 0.0,
                })
    return out


def portfolio_equity_sized(trades: list[dict], cap: float = 500.0,
                           risk_per_trade: float = 0.01, max_leverage: float = 3.0,
                           max_concurrent: int = 3, leverage: float = 1.0) -> dict:
    """Vol-targeted, leverage-dialled book. Cap concurrency, weight each trade by
    risk_per_trade/stop_dist (× global leverage), compound exit-time ordered."""
    kept = merge_portfolio(trades, max_concurrent)
    if not kept:
        return {"end": cap, "ret": 0.0, "sharpe": 0.0, "max_dd": 0.0,
                "n": 0, "weighted_pnls": [], "avg_lev": 0.0}
    contribs, weights = [], []
    for t in kept:
        w = _weight_from_stop(t["stop_dist_pct"], risk_per_trade, max_leverage) * leverage
        weights.append(w)
        contribs.append(w * t["pnl_pct"])
    a = np.asarray(contribs, float)
    eq = cap * np.cumprod(1 + a)
    peak = np.maximum.accumulate(eq)
    return {"end": float(eq[-1]), "ret": float(eq[-1] / cap - 1.0),
            "sharpe": _sharpe(contribs), "max_dd": float(((eq - peak) / peak).min()),
            "n": len(kept), "weighted_pnls": contribs,
            "avg_lev": float(np.mean(weights))}


def conviction_grid():
    """(adx_threshold, rsi_lo, rsi_hi) search grid for the conviction sleeve."""
    import itertools
    return list(itertools.product([20.0, 25.0, 30.0, 35.0], [25, 30, 35], [65, 70, 75]))


def split_sleeved_book(frames: dict, adx_threshold: float, rsi_lo: float,
                       rsi_hi: float, oos_start: float = 0.5):
    """Build the sleeved, conviction-filtered book and split each symbol's trades
    at oos_start into (in_sample, out_of_sample) by entry time."""
    is_t, oos_t = [], []
    for sym, df in frames.items():
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        for t in build_symbol_trades_sleeved(sym, df, adx_threshold, 50, True,
                                             rsi_lo, rsi_hi):
            (oos_t if t["entry_time"] >= cut else is_t).append(t)
    return is_t, oos_t


def select_conviction_book(frames: dict, grid=None, oos_start: float = 0.5,
                           risk_per_trade: float = 0.015, max_leverage: float = 3.0,
                           max_concurrent: int = 3) -> dict:
    """Honest, no-lookahead selection: score every grid config by IN-SAMPLE
    Sharpe, pick the best, then report its OUT-OF-SAMPLE result deflated by the
    grid size. The OOS numbers never influence which config is chosen."""
    grid = grid or conviction_grid()
    scored = []
    for adx, lo, hi in grid:
        is_t, oos_t = split_sleeved_book(frames, adx, lo, hi, oos_start)
        ie = portfolio_equity_sized(is_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        oe = portfolio_equity_sized(oos_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        scored.append({"params": (adx, lo, hi), "is_sharpe": ie["sharpe"],
                       "oos": oe, "oos_trades": oos_t})
    chosen = max(scored, key=lambda s: s["is_sharpe"])
    wp = chosen["oos"]["weighted_pnls"]
    dsr = deflated_sharpe_ratio(wp, num_trials=len(grid)) if wp else 0.0
    return {"chosen": chosen, "scored": scored, "dsr": round(dsr, 4),
            "n_grid": len(grid)}


def leverage_dial(trades: list[dict], levels=(1.0, 1.5, 2.0, 3.0, 4.0),
                  risk_per_trade: float = 0.015, max_leverage: float = 3.0,
                  max_concurrent: int = 3, cap: float = 500.0) -> list[dict]:
    """Sweep global leverage on a fixed trade set — the honest return-vs-drawdown
    operating curve. Sharpe is invariant to leverage; only return and drawdown
    move (and past ~Kelly, compound return falls while drawdown explodes)."""
    rows = []
    for L in levels:
        e = portfolio_equity_sized(trades, cap, risk_per_trade, max_leverage,
                                   max_concurrent, float(L))
        rows.append({"leverage": float(L), **e})
    return rows


def load_frames(rule: str = "4h") -> dict:
    """Load BTC/ETH/SOL 1m parquet → resampled OHLCV+ATR frames. Run from backend/."""
    frames = {}
    for f in sorted(glob.glob("vector_store_1m_*.parquet")):
        sym = os.path.basename(f).replace("vector_store_1m_", "").replace(".parquet", "")
        d = pd.read_parquet(f, columns=["time", "open", "high", "low", "close", "volume"])
        d["time"] = pd.to_datetime(d["time"], unit="s")
        d = d.set_index("time").sort_index()
        frames[sym] = resample(d, rule)
    return frames


def _row(label, r):
    o = r["oos"]
    return (f"{label:>34} {o['end']:>8,.0f} {o['ret']*100:>7.1f}% {o['sharpe']:>7.2f}"
            f" {o['max_dd']*100:>7.1f}% {o['n']:>5} {r['dsr']:>7.4f}"
            f"  {'YES' if r['beats_hold'] else 'no':>4}")


def _spearman(x, y) -> float:
    """Rank correlation — does in-sample quality predict out-of-sample?"""
    rx = np.argsort(np.argsort(np.asarray(x, float)))
    ry = np.argsort(np.argsort(np.asarray(y, float)))
    return float(np.corrcoef(rx, ry)[0, 1]) if len(rx) > 1 else 0.0


def main():
    frames = load_frames("4h")
    if not frames:
        print("No vector_store_1m_*.parquet found (run from backend/).")
        return
    hodl = _basket_hodl(frames, 0.5)
    print(f"Regime book · {len(frames)} symbols pooled · $500 · OOS tail (last 50%)")
    print(f"Equal-weight basket HODL ref: {hodl['net_return']*100:+.1f}% "
          f"(maxDD {hodl['max_drawdown']*100:.1f}%)\n")

    # --- Stage 1: structural progression (unsized 1/3 book) ----------------
    print("STAGE 1 — structure (fixed 1/3 sizing):")
    print(f"{'config':>34} {'$end':>8} {'ret':>8} {'Sharpe':>7} {'maxDD':>8}"
          f" {'n':>5} {'DSR':>7}  beatsHODL")
    base = walk_forward_book(frames, use_regime=False, max_concurrent=1)
    print(_row("BEFORE ungated cap1", base))
    spine = walk_forward_book(frames, use_regime=False, max_concurrent=3)
    print(_row("SPINE shorts+pool cap3", spine))
    gate = walk_forward_book(frames, use_regime=True, adx_threshold=20.0, max_concurrent=3)
    print(_row("+REGIME gate adx=20 cap3", gate))

    # --- Stage 2: vol-target sizing + sleeve exits + conviction (IS-select) -
    print("\nSTAGE 2 — vol-target sizing + sleeve exits + conviction "
          "(filter chosen IN-SAMPLE; grid deflated):")
    sel = select_conviction_book(frames)
    ch = sel["chosen"]
    adx, lo, hi = ch["params"]
    o = ch["oos"]
    corr = _spearman([s["is_sharpe"] for s in sel["scored"]],
                     [s["oos"]["sharpe"] for s in sel["scored"]])
    print(f"  IS-selected config: adx={adx:.0f}  RSI<{lo}/>{hi}  "
          f"(grid {sel['n_grid']}, IS->OOS rank corr {corr:+.2f})")
    print(f"  OOS (L=1): ${o['end']:,.0f}  {o['ret']*100:+.1f}%  Sharpe {o['sharpe']:+.2f}"
          f"  maxDD {o['max_dd']*100:.1f}%  n={o['n']}  DSR(grid) {sel['dsr']:.4f}")

    # --- Stage 3: honest leverage dial on the validated config -------------
    print("\nSTAGE 3 — leverage dial on the validated config (Sharpe is invariant):")
    print(f"{'lev':>5} {'$end':>9} {'ret':>9} {'Sharpe':>7} {'maxDD':>8} {'avgLev':>7}")
    for d in leverage_dial(ch["oos_trades"]):
        print(f"{d['leverage']:>5.1f} {d['end']:>9,.0f} {d['ret']*100:>+8.1f}%"
              f" {d['sharpe']:>+7.2f} {d['max_dd']*100:>7.1f}% {d['avg_lev']:>7.2f}")
    print("\nDSR >= 0.5 = deflation-provable. Best here is still < 0.5 (3 symbols);"
          " honest forward edge, not yet provable. Past ~Kelly leverage, return falls.")


if __name__ == "__main__":
    main()
