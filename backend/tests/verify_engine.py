#!/usr/bin/env python3
"""verify_engine.py — Deterministic unit tests for updated 15m scalping strategies.

Run: cd /home/nageshmadaram/Sterling/backend && PYTHONPATH=. python tests/verify_engine.py
"""
from __future__ import annotations
import sys
from typing import Optional
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

try:
    from app.engines.sterling_engine.price_action import detect_double_bottom
    from app.engines.sterling_engine.ma_crossover import rolling_sma, rolling_ema, current_atr, evaluate_ma_crossover
    from app.engines.sterling_engine.smc import evaluate_smc, SMCESignal
    from app.engines.sterling_engine.levels import Level
    from app.engines.sterling_engine.config import ScalpingConfig
    from app.schemas.market import Candle
except ImportError as e:
    print(f"ERROR: {e}"); sys.exit(1)

PASS, FAIL = "  ✅ ", "  ❌ "

# ── helpers ──
def _c(ts, o, h, l, c): return Candle(timestamp_ms=ts, open=o, high=h, low=l, close=c, volume=10.0)
def _lvl(price, ltype): return Level(price=price, level_type=ltype, touches=3, first_touch_ts=1700000000000, last_touch_ts=1700000100000)

def _a(actual, expected, label, tol=1e-4):
    if abs(actual - expected) > tol:
        raise AssertionError(f"{label}: expected {expected:.6f}, got {actual:.6f}")

def _plot(o, h, l, c, title, entry=None, stop=None, neckline=None, sweep=None, imb=None):
    n = len(c); fig, ax = plt.subplots(figsize=(14, 5))
    for i in range(n):
        clr = "#26a69a" if c[i] >= o[i] else "#ef5350"
        ax.plot([i, i], [l[i], h[i]], color=clr, lw=0.8)
        bot = min(o[i], c[i]); ht = abs(c[i] - o[i])
        ax.bar(i, ht, 0.6, bottom=bot, color=clr, edgecolor=clr, lw=0.5)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Bar"); ax.set_ylabel("Price"); ax.grid(axis="y", alpha=0.2)
    if entry: ax.axhline(y=entry, c="#10b981", lw=1.5, ls="-", label=f"Entry {entry:.2f}")
    if stop: ax.axhline(y=stop, c="#ef4444", lw=1.2, ls="--", label=f"Stop {stop:.2f}")
    if neckline: ax.axhline(y=neckline, c="#3b82f6", lw=1.2, ls="-", label=f"Lvl {neckline:.2f}")
    if sweep is not None:
        ax.axvspan(sweep - 0.4, sweep + 0.4, color="#a78bfa", alpha=0.3)
        ax.annotate("SWEEP", (sweep, h[sweep]), xytext=(0, 10), textcoords="offset points", fontsize=8, color="#a78bfa", ha="center")
    if imb is not None:
        ax.axvspan(imb - 0.4, imb + 0.4, color="#f59e0b", alpha=0.3)
        ax.annotate("IMB", (imb, h[imb]), xytext=(0, 10), textcoords="offset points", fontsize=8, color="#f59e0b", ha="center")
    ax.legend(fontsize=8, loc="upper left"); fig.tight_layout()
    fname = f"verify_engine_{title.replace(' ', '_').replace('.', '')}.png"; fig.savefig(fname, dpi=120); plt.close(fig)
    print(f"  📊 {fname}")

# ═══════ A1: Double Bottom Chop Rejected ═══════
def test_a1():
    print("\n── A1: Double Bottom — Chop Rejected ──")
    n=30; base=100.0; rng=np.random.default_rng(42)
    noise=rng.normal(0,0.05,n).astype(np.float64)
    c=np.full(n,base,dtype=np.float64)+noise; h=c+0.1; l=c-0.1
    r=detect_double_bottom(h,l,c,lookback=30)
    assert r is None, f"Expected None, got {r}"
    print(f"{PASS}Chop correctly returns None.")

# ═══════ A2: Double Bottom W-Shape ═══════
def test_a2():
    print("\n── A2: Double Bottom — Valid W-Shape ──")
    n=30; c=np.full(n,100.0); h=np.full(n,100.0); l=np.full(n,100.0)
    for i in range(10): c[i]=102.0-i*0.2; h[i]=c[i]+0.15; l[i]=c[i]-0.15
    c[9]=100.5;h[9]=100.7;l[9]=100.1; c[10]=100.0;h[10]=100.2;l[10]=99.8
    c[11]=100.5;h[11]=100.7;l[11]=100.3; c[12]=101.0;h[12]=101.2;l[12]=100.8
    c[13]=101.5;h[13]=101.7;l[13]=101.3; c[14]=102.0;h[14]=102.2;l[14]=101.8
    c[15]=102.5;h[15]=102.7;l[15]=102.3; c[16]=102.8;h[16]=103.0;l[16]=102.6
    c[17]=103.2;h[17]=103.4;l[17]=102.9
    c[18]=102.5;h[18]=102.8;l[18]=102.2; c[19]=101.8;h[19]=102.0;l[19]=101.5
    c[20]=101.2;h[20]=101.5;l[20]=101.0; c[21]=100.8;h[21]=101.0;l[21]=100.5
    c[22]=100.5;h[22]=100.8;l[22]=100.3; c[23]=100.3;h[23]=100.5;l[23]=100.1
    c[24]=100.2;h[24]=100.5;l[24]=99.9
    c[25]=101.0;h[25]=101.3;l[25]=100.7; c[26]=101.8;h[26]=102.0;l[26]=101.5
    c[27]=102.5;h[27]=102.8;l[27]=102.2; c[28]=102.8;h[28]=103.0;l[28]=102.5
    c[29]=103.5;h[29]=103.7;l[29]=103.2
    r=detect_double_bottom(h,l,c,lookback=30)
    assert r is not None and r["pattern"]=="double_bottom_confirmed" and r["direction"]=="long"
    _a(r["neckline"],103.4,"neckline",0.01)
    _a(r["stop_below"],round(99.8*0.998,4),"stop_below")
    print(f"{PASS}Neckline={r['neckline']}, stop={r['stop_below']}")
    _plot(h,l,l,c,"A2 Valid Double Bottom",entry=103.5,stop=r["stop_below"],neckline=r["neckline"])

# ═══════ B1: SMC Stale Sweep ═══════
def test_b1():
    print("\n── B1: SMC — Stale Sweep Rejected ──")
    ts=1700000000000; candles=[_c(ts+5*900000,100.3,100.5,99.0,100.5)]
    for i in range(0,5): candles.insert(i,_c(ts+i*900000,100.5,100.7,100.2,100.4))
    for i in range(6,18): candles.append(_c(ts+i*900000,100.5,100.7,100.2,100.4))
    candles.append(_c(ts+18*900000,100.4,101.1,100.0,101.0))
    candles.append(_c(ts+19*900000,101.0,101.2,100.8,101.1))
    c4h=[_c(ts-i*14400000,99.0,102.0,98.0,100.0) for i in range(60)]
    cfg=ScalpingConfig(enable_smc=True,smc_imbalance_ratio=1.2,warmup_bars_15m=20,warmup_bars_4h=20)
    sig:SMCESignal=evaluate_smc("BTC",c4h,candles,[_lvl(100.0,"support")],cfg)
    assert not sig.entry_ok, f"Expected rejection, got ok: {sig.reason}"
    print(f"{PASS}Stale sweep rejected: {sig.reason}")
    hhh=np.array([c.high for c in candles]); lll=np.array([c.low for c in candles])
    _plot(hhh,lll,lll,np.array([c.close for c in candles]),"B1 Stale SMC Sweep",neckline=100.0,sweep=5,imb=18)

# ═══════ B2: SMC Immediate Snapback ═══════
def test_b2():
    print("\n── B2: SMC — Immediate Snapback ──")
    ts=1700000000000; candles=[]
    for i in range(20):
        ti=ts+i*900000
        if i==15: candles.append(_c(ti,100.1,100.3,99.3,100.2))
        elif i==16: candles.append(_c(ti,100.2,102.0,100.0,101.8))
        else: candles.append(_c(ti,100.5,100.7,100.2,100.5))
    c4h=[_c(ts-i*14400000,99.0,102.0,98.0,100.0) for i in range(60)]
    cfg=ScalpingConfig(enable_smc=True,smc_imbalance_ratio=1.2,warmup_bars_15m=20,warmup_bars_4h=20)
    sig:SMCESignal=evaluate_smc("BTC",c4h,candles,[_lvl(100.0,"support")],cfg)
    assert sig.entry_ok, f"Snapback should fire: {sig.reason}"
    assert sig.direction=="long"; assert sig.entry is not None; assert sig.stop_loss is not None
    _a(sig.entry,101.8,"entry"); _a(sig.stop_loss,round(99.3*0.999,4),"stop pinned to sweep low")
    print(f"{PASS}Entry={sig.entry}, stop={sig.stop_loss}")
    hhh=np.array([c.high for c in candles]); lll=np.array([c.low for c in candles])
    _plot(hhh,lll,lll,np.array([c.close for c in candles]),"B2 Immediate SMC Snapback",entry=sig.entry,stop=sig.stop_loss,neckline=100.0,sweep=15,imb=16)

# ═══════ C1: MA Crossover Localized Stop < 2% ═══════
def test_c1():
    print("\n── C1: MA Crossover — Localized Stop < 2% ──")
    ts=1700000000000; n=60
    c=np.full(n,100.0); hi=np.full(n,100.0); lo=np.full(n,100.0)
    # Engineered SMA<EMA cross at bar 57, SMA>EMA cross at bar 59 (within last 3)
    for i in range(10): c[i]=110.0-i*0.3; hi[i]=c[i]+0.5; lo[i]=c[i]-0.5
    for i in range(10,20): c[i]=107.0-(i-9)*1.5; hi[i]=c[i]+0.5; lo[i]=c[i]-0.5
    for i in range(20,55): c[i]=92.0+(i-19)*0.01; hi[i]=c[i]+0.3; lo[i]=c[i]-0.3
    c[55]=92.1; hi[55]=92.5; lo[55]=91.6
    c[56]=92.0; hi[56]=92.4; lo[56]=91.5
    c[57]=93.5; hi[57]=93.9; lo[57]=92.0
    c[58]=95.5; hi[58]=95.9; lo[58]=93.0
    c[59]=97.5; hi[59]=97.9; lo[59]=95.0

    sma=rolling_sma(c,5); ema=rolling_ema(c,9)
    cross=False
    for j in range(n-3,n):
        if sma[j]>0 and ema[j]>0 and sma[j-1]>0 and ema[j-1]>0:
            if sma[j]>ema[j] and sma[j-1]<=ema[j-1]:
                cross=True; print(f"  Cross at bar {j}: SMA={sma[j]:.4f}, EMA={ema[j]:.4f}"); break
    assert cross, f"No cross! SMA[-1]={sma[-1]:.4f} EMA[-1]={ema[-1]:.4f}"

    c15m=[_c(ts+i*900000,c[i],hi[i],lo[i],c[i]) for i in range(n)]
    c4h=[_c(ts-i*14400000,85.0,108.0,84.0,93.0) for i in range(60)]
    cfg=ScalpingConfig(enable_ma_crossover=True,ma_fast_period=5,ma_slow_period=9,
                       warmup_bars_15m=20,warmup_bars_4h=20,level_tolerance_pct=3.0)
    sig=evaluate_ma_crossover("BTC",c4h,c15m,[_lvl(92.5,"support"),_lvl(108.0,"resistance")],cfg)
    assert sig.entry_ok, f"MA cross should arm: {sig.reason}"
    assert sig.direction=="long"; entry=sig.entry; stop=sig.stop_loss
    assert entry is not None and stop is not None
    pct=(entry-stop)/entry*100
    assert pct<2.0, f"Stop {pct:.2f}% exceeds 2%. Entry={entry:.2f} Stop={stop:.2f}"
    ll10=float(np.min(lo[-10:])); atr=current_atr(c,hi,lo)
    expected=round(ll10-atr*0.5,4)
    _a(stop,expected,"stop=10bar low+ATR",0.5)
    print(f"{PASS}Entry={entry:.2f} stop={stop:.2f} ({pct:.2f}%) ll10={ll10:.2f} atr={atr:.4f}")
    last=c15m[-25:]
    _plot(np.array([x.high for x in last]),np.array([x.low for x in last]),
          np.array([x.low for x in last]),np.array([x.close for x in last]),
          "C1 MA Crossover Stop",entry=entry,stop=stop,neckline=92.5)

# ═══════ C2: MA No-Signal on Flat ═══════
def test_c2():
    print("\n── C2: MA Crossover — Flat No-Signal ──")
    ts=1700000000000; n=60
    c=np.full(n,100.5); hi=c+0.1; lo=c-0.1
    c15m=[_c(ts+i*900000,c[i],hi[i],lo[i],c[i]) for i in range(n)]
    c4h=[_c(ts-i*14400000,98.0,102.0,97.0,100.0) for i in range(60)]
    cfg=ScalpingConfig(enable_ma_crossover=True,ma_fast_period=5,ma_slow_period=9,
                       warmup_bars_15m=20,warmup_bars_4h=20,level_tolerance_pct=2.0)
    sig=evaluate_ma_crossover("BTC",c4h,c15m,[_lvl(100.0,"support")],cfg)
    assert not sig.entry_ok, f"Flat should not arm: {sig.reason}"
    print(f"{PASS}Flat data correctly non-armed: {sig.reason}")

# ═══════ Main ═══════
def main():
    print("="*72)
    print("  Sterling Scalping Engine — Verification Suite")
    print("="*72)
    tests=[("A1 DB Chop",test_a1),("A2 DB W-Shape",test_a2),
           ("B1 SMC Stale",test_b1),("B2 SMC Snapback",test_b2),
           ("C1 MA Stop<2%",test_c1),("C2 MA Flat",test_c2)]
    failed=[]
    for name,fn in tests:
        try: fn()
        except AssertionError as e: print(f"{FAIL}{name}: {e}"); failed.append(f"{name}: {e}")
        except Exception as e: print(f"{FAIL}{name}: {e}"); failed.append(f"{name}: {e}")
    p=len(tests)-len(failed)
    print(f"\n{'='*72}\n  RESULTS: {p}/{len(tests)} passed")
    if failed:
        for f in failed: print(f"    ❌ {f}")
        sys.exit(1)
    else:
        print("  All tests passed ✅"); sys.exit(0)

if __name__=="__main__":
    main()
