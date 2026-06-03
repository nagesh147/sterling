"""Independent real-data grounding for SterlingV2 design.

Does NOT read any existing .md report. Loads the raw parquet vector stores,
characterizes them, counts raw signals, and runs ONE correctly-specified
single-config replay (next-bar-open fills, costs, realized-frequency Sharpe)
to sanity-check whether prior claims survive an honest method.
"""
from __future__ import annotations
import glob, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.engines.edge.strategies import SIGNAL_FNS, resample  # single source of truth

FEE_RT = 0.001          # 0.1% round trip
SLIP = 0.0005           # 5 bps slippage per fill (entry + stop)
SL_MULT, TP_MULT = 2.0, 3.5   # Intraday profile
MAX_HOLD = 200

def load(path):
    df = pd.read_parquet(path, columns=["time","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time").sort_index()

def buyhold_stats(df):
    r = df["close"].pct_change().dropna()
    days = (df.index[-1] - df.index[0]).days
    bh = df["close"].iloc[-1]/df["close"].iloc[0] - 1
    ann_vol = r.std()*np.sqrt(525_600)   # 1m bars/yr
    return bh, ann_vol, days

def correct_replay(df4h, sigs):
    """Long-only, NEXT-BAR-OPEN entry, stop/tp first-touch with slippage,
    correctly-annualized Sharpe via realized trade frequency."""
    o = df4h["open"].to_numpy(float); h = df4h["high"].to_numpy(float)
    l = df4h["low"].to_numpy(float);  c = df4h["close"].to_numpy(float)
    atr = df4h["atr"].to_numpy(float)
    t = df4h.index.to_numpy()
    n = len(c); pos = 0; rets = []; ein = -1; entry=sl=tp=0.0
    i = 0
    while i < n-1:
        if pos == 0 and sigs[i] and np.isfinite(atr[i]) and atr[i] > 0:
            entry = o[i+1] * (1+SLIP)          # fill NEXT bar open + slippage
            sl = entry - SL_MULT*atr[i]; tp = entry + TP_MULT*atr[i]
            pos = 1; ein = i+1; i += 1; continue
        if pos == 1:
            if l[i] <= sl:
                ex = sl*(1-SLIP); rets.append((ex/entry-1)-FEE_RT); pos=0
            elif h[i] >= tp:
                ex = tp; rets.append((ex/entry-1)-FEE_RT); pos=0
            elif (i-ein) >= MAX_HOLD:
                ex = c[i]; rets.append((ex/entry-1)-FEE_RT); pos=0
        i += 1
    r = np.array(rets, float)
    if r.size == 0: return None
    wins = r[r>0]; losses = r[r<0]
    pf = wins.sum()/(-losses.sum()) if losses.size else float("inf")
    win = wins.size/r.size
    eq = np.cumprod(1+r); peak = np.maximum.accumulate(eq)
    maxdd = ((eq-peak)/peak).min()
    # realized trades/year for correct annualization
    span_yrs = (df4h.index[-1]-df4h.index[0]).days/365.25
    tpy = r.size/span_yrs
    sharpe = (r.mean()/r.std(ddof=1))*np.sqrt(tpy) if r.std(ddof=1)>0 else 0.0
    return dict(trades=r.size, win=win, pf=pf, net=eq[-1]-1, maxdd=maxdd,
                sharpe=sharpe, tpy=tpy)

def main():
    t0=time.time()
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "vector_store_1m_*.parquet")))
    print(f"[load] {len(files)} parquet files\n")
    print(f"{'sym':7} {'bars':>10} {'start':>12} {'end':>12} {'B&H%':>8} {'annVol%':>8}")
    dfs={}
    for f in files:
        sym=os.path.basename(f).split('_')[-1].replace('.parquet','')
        df=load(f); dfs[sym]=df
        bh,av,days=buyhold_stats(df)
        print(f"{sym:7} {len(df):>10,} {str(df.index[0].date()):>12} "
              f"{str(df.index[-1].date()):>12} {bh*100:>7.1f} {av*100:>7.1f}")
    print()
    # raw signal counts at 4h + corrected replay for ma_crossover
    print(f"{'sym':7} {'strat':14} {'raw 4h sigs':>12} {'4h bars':>9}")
    for sym,df in dfs.items():
        d4=resample(df,"4h")
        nbars=len(d4)
        for strat,fn in SIGNAL_FNS.items():
            s=fn(d4)
            print(f"{sym:7} {strat:14} {int(np.nansum(s)):>12} {nbars:>9,}")
    print()
    print("=== Corrected single-config replay: ma_crossover 4h, Intraday, long-only ===")
    print(f"{'sym':7} {'trades':>7} {'win%':>6} {'PF':>6} {'net%':>9} {'maxDD%':>8} {'Sharpe':>7} {'tr/yr':>6}")
    for sym,df in dfs.items():
        d4=resample(df,"4h"); sig=SIGNAL_FNS["ma_crossover"](d4)
        m=correct_replay(d4,sig)
        if m: print(f"{sym:7} {m['trades']:>7} {m['win']*100:>5.1f} {m['pf']:>6.2f} "
                    f"{m['net']*100:>+8.1f} {m['maxdd']*100:>7.1f} {m['sharpe']:>7.2f} {m['tpy']:>6.1f}")
    print(f"\n[done] {time.time()-t0:.1f}s")

if __name__=="__main__":
    main()
