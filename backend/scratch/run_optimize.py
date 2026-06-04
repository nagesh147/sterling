import time
from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.sterling_engine.config import default_config
from app.engines.sterling_engine.optimizer import optimize, DEFAULT_TF_PAIRS
def load(s,res,d):
    rows=ohlcv_store.get_candles(f"{s}USD",res,limit=500000,since=int(time.time())-d*86400)
    return [Candle(timestamp_ms=int(x["time"])*1000,open=x["open"],high=x["high"],low=x["low"],close=x["close"],volume=x["volume"]) for x in rows]
SYMS=["BTC","ETH","SOL"]; DAYS=45
res_needed=set()
for m,e in DEFAULT_TF_PAIRS: res_needed.add(m); res_needed.add(e)
cbr={r:{} for r in res_needed}
for s in SYMS:
    ok=True; tmp={}
    for r in res_needed:
        a=load(s,r,DAYS+(60 if r in ('2h','4h') else 20))
        if len(a)<250: ok=False; break
        tmp[r]=a
    if ok:
        for r in res_needed: cbr[r][s]=tmp[r]
t0=time.time()
res=optimize(cbr, default_config(), progress=lambda n,t: print(f"  {n}/{t}",flush=True))
print(f"\n=== DONE {time.time()-t0:.0f}s | corr={res.is_oos_corr} | recommend_change={res.recommend_change} ===")
print("NOTE:",res.note)
print("best_params:",res.best_params)
base=res.baseline
print(f"BASELINE 4h/15m: OOS pf={base['oos_pf']} exp={base['oos_exp']} n={base['n_oos']}")
print("\nTop 8 by OOS score:")
print(f"  {'TF':9} {'cb':>3} {'rr':>4} {'trend':>6} {'OOSpf':>6} {'OOSexp':>7} {'nOOS':>5} {'ISpf':>6}")
for c in res.combos[:8]:
    p=c['params']
    print(f"  {p['macro_timeframe']+'/'+p['execution_timeframe']:9} {p['pa_confirm_bars']:>3} {p['pa_min_rr']:>4} {str(p['macro_trend_filter']):>6} {c['oos_pf']:>6} {c['oos_exp']:>7} {c['n_oos']:>5} {c['is_pf']:>6}")
