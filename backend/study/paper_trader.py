"""Paper trader for the validated conviction book — REAL DATA, ISOLATED.

Runs the exact validated conviction regime book (adx=20, RSI<25/>65, vol-target
sizing, sleeve-specific exits) on real Binance bars and keeps a persisted paper
account, so a genuine forward (out-of-sample-in-calendar-time) track record
accumulates run by run. It deliberately does NOT touch the live SterlingEngine:
the book is not deflation-provable (DSR 0.166 < 0.5), so it earns trust by
paper-trading, not by going live.

Design invariant: realized equity over [inception, now] is computed with the
SAME `portfolio_equity_sized` the backtest used, so the paper book can never
drift from what was validated. `walk_positions` only adds the live concept the
backtest lacks — a position that is still OPEN at the latest bar.

Spec/report: docs/regime_book_before_after.md.
Run:  cd backend && .venv/bin/python -m study.paper_trader
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from study.regime_book import (
    classify_regime, signals_ma_crossover, short_momentum, _mr_signals,
    _TREND_EXIT, _MR_EXIT, portfolio_equity_sized, _weight_from_stop,
    FEE_RT, MAX_HOLD,
)

# The validated conviction book: IS-selected config (adx=20, RSI<25/>65),
# vol-target sizing, sleeve-specific exits, 3-coin pool, 1x (conservative) lever.
PAPER_CONFIG = {
    "adx": 20.0, "rsi_lo": 25, "rsi_hi": 65,
    "risk_per_trade": 0.015, "max_leverage": 3.0, "max_concurrent": 3,
    "leverage": 1.0,
    # Conservative flat perp-funding drag applied to every position by hold
    # duration (real per-venue funding needs the funding-rate API — see the
    # production-readiness doc). 1bp / 8h ≈ 3bp/day, charged regardless of side.
    "funding_rate_8h": 0.0001, "bar_hours": 4,
}
PAPER_SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]


def _funding_cost(entry_bar: int, exit_bar: int, bar_hours: float,
                  rate_8h: float) -> float:
    """Flat funding drag for a position held (exit-entry) bars: rate per 8h ×
    hold-hours / 8. Always a cost (conservative)."""
    hold_hours = max(0, (exit_bar - entry_bar)) * bar_hours
    return rate_8h * hold_hours / 8.0


def walk_positions(df, sigs, slm, tpm, direction="long", trail_mult=None,
                   max_hold=200, fee_rt=0.001):
    """Live first-touch SL/TP/trail walker. Like `study.sim.simulate_idx` but
    reports the position that is still OPEN at the last available bar instead of
    force-closing it.

    Returns (closed, open_pos):
      closed   — list of {pnl_pct, entry_bar, exit_bar, status} where status is
                 'sl' | 'tp' | 'time' (max_hold elapsed)
      open_pos — None, or a single {entry_bar, entry_price, sl, tp, trail,
                 unrealized_pnl, status='open'} (sequential book → ≤1 open)
    """
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(close)

    closed: list[dict] = []
    open_pos = None
    idx = np.flatnonzero(sigs)
    sp = 0
    while sp < len(idx):
        i = int(idx[sp])
        sp += 1
        if i >= n - 1 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        e = close[i]
        if direction == "short":
            sl = e + slm * atr[i]
            tp = e - tpm * atr[i]
        else:
            sl = e - slm * atr[i]
            tp = e + tpm * atr[i]

        end = min(i + max_hold, n - 1)
        trail = sl if trail_mult is not None else None
        xp = xi = None
        status = None
        for j in range(i + 1, end + 1):
            if direction == "short":
                stop = trail if trail is not None else sl
                if high[j] >= stop:
                    xp, xi, status = stop, j, "sl"; break
                if low[j] <= tp:
                    xp, xi, status = tp, j, "tp"; break
                if trail is not None:
                    trail = min(trail, low[j] + trail_mult * atr[i])
            else:
                stop = trail if trail is not None else sl
                if low[j] <= stop:
                    xp, xi, status = stop, j, "sl"; break
                if high[j] >= tp:
                    xp, xi, status = tp, j, "tp"; break
                if trail is not None:
                    trail = max(trail, high[j] - trail_mult * atr[i])

        if status is not None:                       # SL or TP hit → closed
            pnl = (xp / e - 1.0 - fee_rt) if direction == "long" \
                else (1.0 - xp / e - fee_rt)
            closed.append({"pnl_pct": pnl, "entry_bar": i, "exit_bar": xi,
                           "status": status})
            while sp < len(idx) and idx[sp] <= xi:
                sp += 1
            continue

        # No SL/TP touch within available bars.
        if (end - i) >= max_hold:                    # max_hold elapsed → time exit
            xp = close[end]
            pnl = (xp / e - 1.0 - fee_rt) if direction == "long" \
                else (1.0 - xp / e - fee_rt)
            closed.append({"pnl_pct": pnl, "entry_bar": i, "exit_bar": end,
                           "status": "time"})
            while sp < len(idx) and idx[sp] <= end:
                sp += 1
            continue

        # Still open at the last bar → mark to market (sequential book stops here).
        mtm = close[n - 1]
        unreal = (mtm / e - 1.0 - fee_rt) if direction == "long" \
            else (1.0 - mtm / e - fee_rt)
        open_pos = {"entry_bar": i, "entry_price": e, "sl": sl, "tp": tp,
                    "trail": trail, "unrealized_pnl": float(unreal),
                    "status": "open"}
        break

    return closed, open_pos


def build_paper_sleeves(symbol: str, df, config: dict):
    """Per-symbol conviction book via `walk_positions`: returns (closed, opens).
    Mirrors regime_book.build_symbol_trades_sleeved (same sleeves, regime gate,
    exits, conviction RSI thresholds) but surfaces live open positions."""
    adx, lo, hi = config["adx"], config["rsi_lo"], config["rsi_hi"]
    reg = classify_regime(df, adx, 50)
    close = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    mr_long, mr_short = _mr_signals(df, lo, hi)
    rate_8h = config.get("funding_rate_8h", 0.0)
    bar_hours = config.get("bar_hours", 4)
    n = len(df)
    sleeves = {
        "trend": {"long": signals_ma_crossover(df) & (reg == 1),
                  "short": short_momentum(df) & (reg == -1), **_TREND_EXIT},
        "mr": {"long": mr_long & (reg == 0),
               "short": mr_short & (reg == 0), **_MR_EXIT},
    }
    closed, opens = [], []
    for name, cfg in sleeves.items():
        for d in ("long", "short"):
            c, op = walk_positions(df, cfg[d], cfg["sl"], cfg["tp"], direction=d,
                                   trail_mult=cfg["trail"], max_hold=MAX_HOLD,
                                   fee_rt=FEE_RT)
            for t in c:
                e, a = close[t["entry_bar"]], atr[t["entry_bar"]]
                fund = _funding_cost(t["entry_bar"], t["exit_bar"], bar_hours, rate_8h)
                closed.append({
                    "symbol": symbol, "sleeve": name, "direction": d,
                    "entry_time": df.index[t["entry_bar"]],
                    "exit_time": df.index[t["exit_bar"]],
                    "pnl_pct": t["pnl_pct"] - fund, "status": t["status"],
                    "stop_dist_pct": (cfg["sl"] * a / e) if e > 0 else 0.0})
            if op is not None:
                e, a = op["entry_price"], atr[op["entry_bar"]]
                fund = _funding_cost(op["entry_bar"], n - 1, bar_hours, rate_8h)
                opens.append({
                    "symbol": symbol, "sleeve": name, "direction": d,
                    "entry_time": df.index[op["entry_bar"]],
                    "entry_price": e, "sl": op["sl"], "tp": op["tp"],
                    "mtm_price": float(close[-1]),
                    "unrealized_pnl": op["unrealized_pnl"] - fund,
                    "stop_dist_pct": (cfg["sl"] * a / e) if e > 0 else 0.0})
    return closed, opens


def paper_book(frames: dict, config: dict, inception, capital: float = 500.0) -> dict:
    """Assemble the paper account from real-data frames. Realized equity is the
    validated `portfolio_equity_sized` over closed trades since inception (so it
    can never drift from the backtest); open positions are marked to market."""
    closed_all, opens_all = [], []
    for sym, df in frames.items():
        c, op = build_paper_sleeves(sym, df, config)
        closed_all += c
        opens_all += op
    closed_since = [t for t in closed_all if t["entry_time"] >= inception]
    realized = portfolio_equity_sized(
        closed_since, capital, config["risk_per_trade"], config["max_leverage"],
        config["max_concurrent"], config["leverage"])

    open_positions = []
    for op in opens_all:
        w = _weight_from_stop(op["stop_dist_pct"], config["risk_per_trade"],
                              config["max_leverage"]) * config["leverage"]
        open_positions.append({**op, "weight": w,
                               "weighted_unrealized": w * op["unrealized_pnl"]})
    open_positions.sort(key=lambda o: o["entry_time"], reverse=True)
    open_positions = open_positions[:config["max_concurrent"]]

    unreal = sum(o["weighted_unrealized"] for o in open_positions)
    total_equity = realized["end"] * (1.0 + unreal)
    return {"realized": realized, "open_positions": open_positions,
            "total_equity": float(total_equity), "n_closed": len(closed_since),
            "inception": inception, "capital": capital}


# --- persistence ---------------------------------------------------------
PAPER_DIR = "data/paper"


def _jsonable(o):
    """Recursively convert pandas/numpy types to JSON-safe primitives."""
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return o


def save_state(book: dict, path: str) -> str:
    """Atomically persist a JSON snapshot (write temp + os.replace) so a crash
    mid-write can never corrupt the account state. Timestamps → ISO strings."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    snap = _jsonable({**book, "updated_at": pd.Timestamp.now(tz="UTC").isoformat()})
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(snap, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)                 # atomic on POSIX
    return path


def load_state(path: str):
    """Load a prior snapshot, or None if absent."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def append_trade_log(closed_since: list, path: str) -> None:
    """Write the full closed-trade ledger (idempotent — full rewrite each run)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not closed_since:
        pd.DataFrame(columns=["entry_time", "exit_time", "symbol", "sleeve",
                              "direction", "status", "pnl_pct"]).to_csv(path, index=False)
        return
    df = pd.DataFrame(closed_since).sort_values("exit_time")
    cols = ["entry_time", "exit_time", "symbol", "sleeve", "direction",
            "status", "pnl_pct", "stop_dist_pct"]
    df[[c for c in cols if c in df.columns]].to_csv(path, index=False)


# --- real-data runner ----------------------------------------------------
def load_paper_frames(symbols, tf="4h", data_dir=None):
    """Load the paper universe (only `symbols`) from a data dir."""
    from study.ohlcv_pipeline import load_universe
    data_dir = data_dir or os.path.join(PAPER_DIR, "ohlcv")
    frames = load_universe(tf, data_dir)
    return {s: frames[s] for s in symbols if s in frames}


def refresh_symbols(symbols, start, interval="4h", data_dir=None):
    """Re-download the latest real bars for the paper symbols from Binance."""
    from study.ohlcv_pipeline import download_symbol
    import pandas as pd
    data_dir = data_dir or os.path.join(PAPER_DIR, "ohlcv")
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    for sym in symbols:
        coin = sym[:-3] if sym.endswith("USD") else sym
        download_symbol(coin, interval, start_ms, data_dir)


def _closed_since(frames, config, inception):
    out = []
    for sym, df in frames.items():
        c, _ = build_paper_sleeves(sym, df, config)
        out += [t for t in c if t["entry_time"] >= inception]
    return sorted(out, key=lambda t: t["exit_time"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Paper-trade the validated conviction book on real data.")
    ap.add_argument("--inception", default="2025-09-07", help="forward track start (post-validation)")
    ap.add_argument("--leverage", type=float, default=1.0)
    ap.add_argument("--capital", type=float, default=500.0)
    ap.add_argument("--no-refresh", action="store_true", help="skip re-downloading bars")
    ap.add_argument("--start", default="2024-06-01", help="history start for the data fetch")
    ap.add_argument("--force", action="store_true", help="trade despite data-integrity issues")
    args = ap.parse_args(argv)

    inception = pd.Timestamp(args.inception)
    config = {**PAPER_CONFIG, "leverage": args.leverage}
    state_path = os.path.join(PAPER_DIR, "state.json")
    log_path = os.path.join(PAPER_DIR, "trades.csv")
    prior = load_state(state_path)

    if not args.no_refresh:
        print(f"Refreshing real bars for {', '.join(PAPER_SYMBOLS)} …")
        refresh_symbols(PAPER_SYMBOLS, args.start)
    frames = load_paper_frames(PAPER_SYMBOLS)
    if not frames:
        print("No paper data — run without --no-refresh first.")
        return

    # PRODUCTION GUARD 1 — never act on a still-forming bar (repaint/lookahead).
    from study.ohlcv_pipeline import drop_forming_bar, validate_universe
    frames = {s: drop_forming_bar(df, "4h") for s, df in frames.items()}
    # PRODUCTION GUARD 2 — refuse to trade on stale / gappy / missing data.
    missing = [s for s in PAPER_SYMBOLS if s not in frames or frames[s].empty]
    issues = validate_universe(frames, "4h", min_bars=300)
    if missing:
        issues.append(f"missing symbols: {', '.join(missing)}")
    if issues:
        print("\n!! DATA INTEGRITY ISSUES:")
        for i in issues:
            print(f"   - {i}")
        if not args.force:
            print("Refusing to trade on bad data (use --force to override). Aborting.")
            return
        print("--force set: proceeding despite issues.")

    book = paper_book(frames, config, inception, args.capital)
    r = book["realized"]
    asof = max(df.index[-1] for df in frames.values())
    cap = args.capital

    print(f"\n=== Conviction book · PAPER (real Binance 4h) · {len(frames)} symbols ===")
    print(f"as-of bar {asof:%Y-%m-%d %H:%M} · inception {inception:%Y-%m-%d} · "
          f"leverage {args.leverage:g}x · start ${cap:.0f}")
    print(f"\nRealized (closed since inception):")
    print(f"  ${r['end']:,.2f}  ({r['ret']*100:+.1f}%)  Sharpe {r['sharpe']:+.2f}"
          f"  maxDD {r['max_dd']*100:.1f}%  trades {r['n']}  avgLev {r['avg_lev']:.2f}")
    print(f"Total incl. open MTM: ${book['total_equity']:,.2f} "
          f"({(book['total_equity']/cap-1)*100:+.1f}%)")

    ops = book["open_positions"]
    print(f"\nOpen positions ({len(ops)}):")
    if ops:
        print(f"  {'symbol':>8} {'sleeve':>6} {'dir':>5} {'entry':>16} "
              f"{'entry@':>10} {'mark@':>10} {'uPnL':>7} {'wt':>5}")
        for o in sorted(ops, key=lambda x: x["entry_time"]):
            print(f"  {o['symbol']:>8} {o['sleeve']:>6} {o['direction']:>5}"
                  f" {o['entry_time']:%Y-%m-%d %H:%M} {o['entry_price']:>10.2f}"
                  f" {o['mtm_price']:>10.2f} {o['unrealized_pnl']*100:>+6.1f}%"
                  f" {o['weight']:>5.2f}")
    else:
        print("  (flat — no live commitments at the latest bar)")

    if prior is not None:
        d_closed = book["n_closed"] - prior.get("n_closed", 0)
        d_eq = book["total_equity"] - prior.get("total_equity", cap)
        print(f"\nSince last run: {d_closed:+d} closed trades, "
              f"${d_eq:+,.2f} equity, prev as-of {prior.get('updated_at','?')[:16]}")

    save_state(book, state_path)
    append_trade_log(_closed_since(frames, config, inception), log_path)
    print(f"\nPersisted → {state_path} · ledger → {log_path}")
    print("Not wired to the live engine. DSR 0.166 < 0.5 — earning trust forward.")


if __name__ == "__main__":
    main()
