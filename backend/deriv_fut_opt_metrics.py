"""FUTURES (linear) vs OPTIONS (Black-Scholes modeled) metrics on real data.

Reuses the project's OWN code as the single source of truth:
  * signal logic + resample  -> app.engines.edge.strategies   (same as comprehensive_backtest.py)
  * Black-Scholes option P&L  -> app.engines.backtest.bs_pricing (vectorized here, validated vs the scalar fn)

Data: backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet (real 1m OHLCV + precomputed ATR).
Capital: $500.  Long-only (matches the long-only signals).

FUTURES leg = real linear P&L on the underlying (exit/entry-1) with round-trip fee — identical
to comprehensive_backtest.py. This is the futures/perp candidate.

OPTIONS leg = MODELED. There is NO options chain in the DB, so each trade is repriced as a long
ATM option (call, since signals are long-only) via Black-Scholes with IV = the underlying's own
trailing realized vol. Same entry/exit bars as the futures leg => apples-to-apples. Real crypto
options trade ABOVE realized vol with wide bid/ask, so these option numbers are OPTIMISTIC.

win_rate / profit_factor / expectancy are per-trade-return based => sizing-independent and directly
comparable between legs. The $ capital curve uses the stated sizing for each leg.
"""
from __future__ import annotations

import asyncio
import glob
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.engines.edge.strategies import SIGNAL_FNS, resample      # noqa: E402
from app.engines.backtest.bs_pricing import bs_price               # noqa: E402  (validation only)
from app.engines.backtest.iv_surface_fit import IVSurface          # noqa: E402
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter # noqa: E402
from app.services.exchanges.instrument_registry import get_instrument    # noqa: E402

warnings.filterwarnings("ignore")

STARTING_CAPITAL = 500.0
FEE_ROUND_TRIP = 0.001          # 0.1% futures round trip (Delta India taker ~0.05%/side)
MAX_HOLD_BARS = 200

PROFILES = {
    "Scalping":   {"atr_sl": 1.0, "atr_tp": 2.0},
    "Intraday":   {"atr_sl": 2.0, "atr_tp": 3.5},
    "Aggressive": {"atr_sl": 1.5, "atr_tp": 4.5},
}
# Options on sub-15m are theta/spread-dominated and not meaningfully tradeable => focus on >=15m.
TIMEFRAMES = [("15min", "15m"), ("30min", "30m"), ("1h", "1h"), ("4h", "4h")]
BAR_MIN = {"15m": 15, "30m": 30, "1h": 60, "4h": 240}
BARS_PER_YEAR = {"15m": 35_040, "30m": 17_520, "1h": 8_760, "4h": 2_190}
STRATEGIES = ["ma_crossover", "mean_reversion", "breakout", "price_action", "smc"]

# --- options-leg assumptions (stated, not hidden) ---
DTE_ENTRY = 7                   # buy a 7-DTE ATM option at each entry
IV_WINDOW = 100                 # trailing bars for realized-vol -> IV
OPT_SPREAD = 0.03               # 3% of premium round-trip (bid/ask + slippage)
OPT_PREMIUM_ALLOC = 0.10        # premium spent per trade = 10% of equity (=> max loss 10%/trade)
RISK_FREE = 0.0


# --------------------------------------------------------------------------
# Trade simulator — captures entry/exit so BOTH legs use identical trades
# --------------------------------------------------------------------------
def simulate_capture(df, signals, sl_mult, tp_mult):
    close = df["close"].to_numpy(np.float64)
    high = df["high"].to_numpy(np.float64)
    low = df["low"].to_numpy(np.float64)
    atr = df["atr"].to_numpy(np.float64)
    n = len(close)
    e_px, x_px, held = [], [], []
    sig_idx = np.flatnonzero(signals)
    sp = 0
    while sp < len(sig_idx):
        i = int(sig_idx[sp]); sp += 1
        if i >= n - 2 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = close[i]
        sl = entry - sl_mult * atr[i]
        tp = entry + tp_mult * atr[i]
        end = min(i + MAX_HOLD_BARS, n - 1)
        exit_price = close[end]; exit_idx = end
        for j in range(i + 1, end + 1):
            if low[j] <= sl:
                exit_price = sl; exit_idx = j; break
            if high[j] >= tp:
                exit_price = tp; exit_idx = j; break
        e_px.append(entry); x_px.append(exit_price)
        held.append(exit_idx - i)
        while sp < len(sig_idx) and sig_idx[sp] <= exit_idx:
            sp += 1
    return (np.asarray(e_px), np.asarray(x_px),
            np.asarray(held, dtype=np.float64))


# --------------------------------------------------------------------------
# Vectorized Black-Scholes ATM-call P&L (validated against repo bs_price)
# --------------------------------------------------------------------------
def _norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def bs_call_price_vec(spot, strike, dte_days, iv):
    T = np.maximum(dte_days, 0.0) / 365.0
    out = np.zeros_like(spot, dtype=np.float64)
    ok = (T > 0) & (iv > 0) & (spot > 0) & (strike > 0)
    if ok.any():
        s, k, t, v = spot[ok], strike[ok], T[ok], iv[ok]
        sq = np.sqrt(t)
        d1 = (np.log(s / k) + 0.5 * v * v * t) / (v * sq)
        d2 = d1 - v * sq
        out[ok] = s * _norm_cdf(d1) - k * _norm_cdf(d2)   # r = 0
    # intrinsic at/after expiry
    exp = ~ok
    out[exp] = np.maximum(spot[exp] - strike[exp], 0.0)
    return np.maximum(out, 0.0)


def option_returns(entry_px, exit_px, held_bars, iv_surface, bar_min):
    """Per-trade return on premium for a long ATM call, same entries/exits."""
    strike = entry_px
    days_held = held_bars * bar_min / 1440.0
    dte_exit = np.maximum(DTE_ENTRY - days_held, 0.0)
    
    iv0 = iv_surface.predict(strike, entry_px, np.full_like(entry_px, DTE_ENTRY))
    iv1 = iv_surface.predict(strike, exit_px, dte_exit)
    
    p0 = bs_call_price_vec(entry_px, strike, np.full_like(entry_px, DTE_ENTRY), iv0)
    p1 = bs_call_price_vec(exit_px, strike, dte_exit, iv1)
    
    valid = p0 > 1e-8
    ret = np.full_like(entry_px, np.nan)
    ret[valid] = (p1[valid] - p0[valid]) / p0[valid]
    ret = ret - OPT_SPREAD                       # bid/ask + slippage on premium
    ret = np.maximum(ret, -1.0)                  # long option: can't lose > premium
    return ret[~np.isnan(ret)]


# --------------------------------------------------------------------------
# Metrics (sizing-independent win_rate/pf/expectancy; capital curve per sizing)
# --------------------------------------------------------------------------
def metrics(rets, fractional_alloc=None):
    n = len(rets)
    if n == 0:
        return dict(trades=0, win_rate=0, pf=0, expectancy=0, avg_win=0, avg_loss=0,
                    net_return=0, end_capital=STARTING_CAPITAL, pnl_usd=0, max_dd=0)
    wins = rets[rets > 0]; losses = rets[rets < 0]
    gp = float(wins.sum()); gl = float(-losses.sum())
    pf = gp / gl if gl > 0 else (99.99 if gp > 0 else 0.0)
    wr = wins.size / n
    aw = float(wins.mean()) if wins.size else 0.0
    al = float(-losses.mean()) if losses.size else 0.0
    if fractional_alloc is None:           # futures: full-notional compounding (repo convention)
        eq = STARTING_CAPITAL * np.cumprod(1 + rets)
    else:                                  # options: spend `alloc` of equity on premium each trade
        eq = np.empty(n); c = STARTING_CAPITAL
        for k in range(n):
            c = c * (1 + fractional_alloc * rets[k]); eq[k] = c
    peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min())
    return dict(trades=n, win_rate=wr, pf=pf,
                expectancy=wr * aw - (1 - wr) * al, avg_win=aw, avg_loss=al,
                net_return=eq[-1] / STARTING_CAPITAL - 1.0,
                end_capital=eq[-1], pnl_usd=eq[-1] - STARTING_CAPITAL, max_dd=max_dd)


async def fetch_all_chains(symbols):
    adapter = DeltaIndiaAdapter(api_key="", api_secret="")
    res = {}
    for sym in symbols:
        base_sym = sym.replace("USD", "")
        inst = get_instrument(base_sym)
        if inst:
            try:
                res[sym] = await adapter.get_option_chain(inst)
            except Exception as e:
                print(f"Fetch {sym} options failed: {e}")
                res[sym] = []
    await adapter.close()
    return res


def load_symbol(path):
    df = pd.read_parquet(path, columns=["time", "open", "high", "low", "close",
                                        "volume", "volatility_atr"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.rename(columns={"volatility_atr": "atr"}).set_index("time").sort_index()


def validate_bs():
    """Prove the vectorized BS matches the repo's scalar bs_price."""
    s = np.array([100.0, 50000.0]); k = s.copy()
    v = np.array([0.6, 0.8]); d = np.array([7.0, 7.0])
    mine = bs_call_price_vec(s, k, d, v)
    repo = np.array([bs_price(100.0, 100.0, 7, 0.6, "call"),
                     bs_price(50000.0, 50000.0, 7, 0.8, "call")])
    assert np.allclose(mine, repo, rtol=1e-6), (mine, repo)
    print(f"[validate] vectorized BS == repo bs_price  {mine.round(4)} ✓")


def main():
    validate_bs()
    
    t0 = time.time()
    files = sorted(glob.glob("vector_store_1m_*.parquet"))
    assert files, "no vector_store parquets in cwd"
    
    symbols_to_fetch = [os.path.basename(f).split("_")[-1].replace(".parquet", "") for f in files]
    print(f"Fetching option chains for IV surface fitting: {symbols_to_fetch}...")
    chains = asyncio.run(fetch_all_chains(symbols_to_fetch))
    
    rows = []
    for f in files:
        sym = os.path.basename(f).split("_")[-1].replace(".parquet", "")
        df1 = load_symbol(f)
        spot = df1["close"].iloc[-1]
        
        surface = IVSurface()
        opts = chains.get(sym, [])
        if opts:
            surface.fit([o.strike for o in opts], [o.dte for o in opts], [o.mark_iv for o in opts], spot)
            
            from app.services import db
            db.init()
            if surface.coeffs is not None:
                db.record_surface_params(sym, surface.coeffs.tolist(), time.time())

            atm_iv = surface.predict(spot, spot, DTE_ENTRY)
            print(f"[{sym}] {len(df1):,} 1m rows | Fitted Live {DTE_ENTRY}d ATM IV: {atm_iv*100:.1f}%")
        else:
            print(f"[{sym}] {len(df1):,} 1m rows | WARNING: No options chain fetched, using fallback flat 60% IV")
            
        for rule, tf in TIMEFRAMES:
            dft = resample(df1, rule)
            for strat in STRATEGIES:
                sigs = SIGNAL_FNS[strat](dft)
                for pname, pcfg in PROFILES.items():
                    epx, xpx, held = simulate_capture(
                        dft, sigs, pcfg["atr_sl"], pcfg["atr_tp"])
                    fut = (xpx / epx - 1.0 - FEE_ROUND_TRIP) if len(epx) else np.array([])
                    fm = metrics(fut)
                    oret = option_returns(epx, xpx, held, surface, BAR_MIN[tf]) if len(epx) else np.array([])
                    om = metrics(oret, fractional_alloc=OPT_PREMIUM_ALLOC)
                    rows.append(dict(symbol=sym, tf=tf, strategy=strat, profile=pname,
                                     **{f"fut_{k}": v for k, v in fm.items()},
                                     **{f"opt_{k}": v for k, v in om.items()}))
            print(f"   {tf} done ({time.time()-t0:.0f}s)")
    res = pd.DataFrame(rows)
    res.to_csv("deriv_fut_opt_results.csv", index=False)
    report(res)
    print(f"[done] {len(res)} configs in {time.time()-t0:.0f}s -> deriv_fut_opt_results.csv")


def report(res):
    out = []
    P = out.append
    P("=" * 118)
    P("FUTURES (real linear) vs OPTIONS (Black-Scholes MODELED long ATM call) — $500, real data, vectorized")
    P("=" * 118)
    P(f"Universe: BTC/ETH/SOL  TFs: 15m/30m/1h/4h  Data: 1m vector store (~2024→2026)  Fee(fut): {FEE_ROUND_TRIP*100:.2f}% rt")
    P(f"Options : long ATM call, {DTE_ENTRY} DTE, IV=Real-time Surface Fit (Term-Structure + Skew), {OPT_SPREAD*100:.0f}% spread, "
      f"{OPT_PREMIUM_ALLOC*100:.0f}% premium/trade  [MODELED — optimistic, no historical chain]")
    P("")
    valid = res[res["fut_trades"] >= 30].copy()
    P(f"Configs: {len(res)} total, {len(valid)} with >=30 trades (rankings use these)")
    P("")

    cols = ("symbol", "tf", "strategy", "profile")
    def line(r):
        return (f"{r.symbol:4s} {r.tf:4s} {r.strategy:13s} {r.profile:10s} | "
                f"F: n={int(r.fut_trades):4d} wr={r.fut_win_rate*100:4.1f}% pf={r.fut_pf:5.2f} "
                f"ret={r.fut_net_return*100:+7.1f}% dd={r.fut_max_dd*100:5.1f}% ${r.fut_end_capital:7.0f} | "
                f"O: wr={r.opt_win_rate*100:4.1f}% pf={r.opt_pf:5.2f} "
                f"ret={r.opt_net_return*100:+7.1f}% dd={r.opt_max_dd*100:6.1f}% ${r.opt_end_capital:6.0f}")

    P("── Top 12 configs by FUTURES end-capital (>=30 trades) ──")
    for r in valid.sort_values("fut_end_capital", ascending=False).head(12).itertuples():
        P(line(r))
    P("")
    P("── Top 12 configs by OPTIONS end-capital (>=30 trades) ──")
    for r in valid.sort_values("opt_end_capital", ascending=False).head(12).itertuples():
        P(line(r))
    P("")

    def rollup(by):
        g = valid.groupby(by)
        agg = g.agg(n=("fut_trades", "median"),
                    fut_wr=("fut_win_rate", "median"), fut_pf=("fut_pf", "median"),
                    fut_ret=("fut_net_return", "median"), fut_end=("fut_end_capital", "median"),
                    opt_wr=("opt_win_rate", "median"), opt_pf=("opt_pf", "median"),
                    opt_ret=("opt_net_return", "median"), opt_end=("opt_end_capital", "median"))
        return agg
    for by, title in [("strategy", "STRATEGY"), ("tf", "TIMEFRAME"), ("profile", "PROFILE")]:
        P(f"── Median by {title} (>=30 trades) ──")
        P(f"{'':14s}  med_n | FUT wr%   pf   ret%   $end | OPT wr%   pf    ret%   $end")
        for ix, r in rollup(by).iterrows():
            P(f"{str(ix):14s} {r.n:6.0f} | {r.fut_wr*100:5.1f} {r.fut_pf:5.2f} {r.fut_ret*100:+6.1f} {r.fut_end:6.0f} |"
              f" {r.opt_wr*100:5.1f} {r.opt_pf:5.2f} {r.opt_ret*100:+7.1f} {r.opt_end:6.0f}")
        P("")

    # pooled portfolio: trade every >=30-trade config's per-trade returns on one book
    P("── POOLED (all >=30-trade configs traded as one book) ──")
    P(f"FUTURES: median win {valid.fut_win_rate.median()*100:.1f}%  median PF {valid.fut_pf.median():.2f}  "
      f"profitable configs {int((valid.fut_pnl_usd>0).sum())}/{len(valid)}")
    P(f"OPTIONS: median win {valid.opt_win_rate.median()*100:.1f}%  median PF {valid.opt_pf.median():.2f}  "
      f"profitable configs {int((valid.opt_pnl_usd>0).sum())}/{len(valid)}")
    P("=" * 118)
    P("CAVEATS: options leg is Black-Scholes MODELED (no historical chain; IV=Current live fitted IV surface; real")
    P("spreads/IV-premium make it worse). Long-only. Survivorship (current listings). Decision-support only.")
    P("=" * 118)
    text = "\n".join(out)
    print(text)
    open("deriv_fut_opt_report.txt", "w").write(text + "\n")


if __name__ == "__main__":
    main()
